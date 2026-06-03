from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import boto3
import shutil
import os
import uuid 
from pydantic import BaseModel # <-- Added this so we can make unique filenames!

from fastapi.security import OAuth2PasswordRequestForm
from app import models, schemas
from app.database import engine, get_db, Base
from app.auth import get_password_hash, get_current_user, verify_password, create_access_token 

# ==========================================
# 🛠️ APP SETUP & CLOUD CONNECTION
# ==========================================
class CommentCreate(BaseModel):
    content: str
# 1. Load your secret vault (.env file)
load_dotenv()

# 2. Build the bridge to Amazon S3
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),         # Leave it exactly like this!
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), # Leave it exactly like this!
    region_name=os.getenv('AWS_REGION')                       # Leave it exactly like this!
)
AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')  

# 👇 NEW: Wake up the AI Vision tool!
rekognition_client = boto3.client(
    'rekognition',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')

# This single line tells SQLAlchemy to create all tables in Neon if they don't exist yet
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Event & Media Management API")
# ==========================================
# 🚪 AUTHENTICATION ROUTES
# ==========================================

@app.post("/signup", status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    
    # 1. Check if a user with this email already exists
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # 2. Hash the password so we don't save raw text in the database
    hashed_password = get_password_hash(user.password)
    
    # 3. Create the new user and save them in Neon
    new_user = models.User(
        name=user.name, 
        email=user.email, 
        password_hash=hashed_password,
        role="Club Member" # Default role based on your PDF
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": f"Welcome {new_user.name}! Your account is created."}


@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    
    # 1. Look for the user in the database
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    # 2. If no user, or wrong password, kick them out
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 3. If the password matches, print their VIP Token!
    access_token = create_access_token(data={"sub": user.email})
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/")
def read_root():
    return {"status": "Online", "message": "The Event Platform Engine is running!"}

@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    
    # 1. Scramble the password!
    hashed_pwd = get_password_hash(user.password)
    # 1. Package the incoming data into a database object
    new_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=hashed_pwd, # We will do real security later!
        role=user.role
    )
    
    # 2. Save it to Neon
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 3. Return the saved user data
    return new_user

# --- NEW GET ROUTE START ---
@app.get("/users/", response_model=list[schemas.UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    # Fetch all users from the Neon database
    users = db.query(models.User).all()
    return users
# --- EVENT ROUTES START ---

@app.post("/events/", response_model=schemas.EventResponse)
def create_event(
    event: schemas.EventCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user) # <-- The Security Guard!
):
    new_event = models.Event(
        title=event.title,
        description=event.description,
        location=event.location,
        date=event.date,
        owner_id=current_user.id  # <-- Automatically grabbed from the logged-in user!
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

@app.get("/events/", response_model=list[schemas.EventResponse])
def get_all_events(db: Session = Depends(get_db)):
    # Fetch all events from the Neon database
    events = db.query(models.Event).all()
    return events
@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1. Find the user in Neon by their email
    # (Note: OAuth2 strictly uses the word 'username', but we will type our email into it)
    user = db.query(models.User).filter(models.User.email == form_data.username).first()

    # 2. If the user doesn't exist, or the password doesn't match the scrambled hash, reject them!
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Incorrect email or password"
        )

    # 3. If they pass, generate their digital VIP Pass!
    # We hide their email and their role inside the token.
    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    
    return {"access_token": access_token, "token_type": "bearer"}


os.makedirs("uploads", exist_ok=True)

# Notice how the URL now requires an event_id!
# ==========================================
# 📸 MEDIA UPLOAD ROUTES (AI CLOUD EDITION)
# ==========================================

@app.post("/events/{event_id}/upload", status_code=status.HTTP_201_CREATED)
def upload_event_image(
    event_id: str, 
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    try:
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"events/{event_id}/{uuid.uuid4()}.{file_extension}"
        
        # 1. Throw the file to the Amazon Cloud
        s3_client.upload_fileobj(
            file.file,
            AWS_BUCKET_NAME,
            unique_filename,
            ExtraArgs={"ContentType": file.content_type}
        )
        s3_url = f"https://{AWS_BUCKET_NAME}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{unique_filename}"
        
        # 2. 🧠 AI MAGIC: Ask Amazon Rekognition to look at the photo!
        ai_response = rekognition_client.detect_labels(
            Image={
                'S3Object': {
                    'Bucket': AWS_BUCKET_NAME,
                    'Name': unique_filename
                }
            },
            MaxLabels=5,       # Give us up to 5 tags
            MinConfidence=75   # Only give tags it is at least 75% confident about
        )
        
        # 3. Clean up the AI data into a simple list of words (e.g., ["Crowd", "Tech", "Person"])
        smart_tags = [label['Name'] for label in ai_response['Labels']]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloud/AI Process Failed: {str(e)}")
    tags_string = ", ".join(smart_tags) # Turns ["Crowd", "Tech"] into "Crowd, Tech"
    # 4. Save the photo link to the database
    new_media = models.Media(
        file_url=s3_url,
        ai_tags=tags_string, # Save the AI tags as a comma-separated string
        event_id=event.id,
        owner_id=current_user.id
    )
    
    db.add(new_media)
    db.commit()
    db.refresh(new_media)
        
    # 5. Return the URL AND the new AI tags to the user!
    return {
        "message": "Photo uploaded and analyzed by AI successfully!", 
        "file_url": s3_url,
        "ai_smart_tags": smart_tags
    }
# ==========================================
# 💬 SOCIAL FEATURES (LIKES, COMMENTS, SHARES)
# ==========================================

@app.post("/media/{media_id}/like", status_code=status.HTTP_201_CREATED)
def like_photo(media_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # 1. Check if they already liked it (no double-liking allowed!)
    existing_like = db.query(models.Like).filter(models.Like.media_id == media_id, models.Like.user_id == current_user.id).first()
    if existing_like:
        # If they already liked it, clicking it again "unlikes" it
        db.delete(existing_like)
        db.commit()
        return {"message": "Photo unliked!"}
        
    # 2. Add the new like!
    new_like = models.Like(media_id=media_id, user_id=current_user.id)
    db.add(new_like)
    db.commit()
    return {"message": "Photo liked! ❤️"}

@app.post("/media/{media_id}/comment", status_code=status.HTTP_201_CREATED)
def comment_on_photo(media_id: str, comment: CommentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    new_comment = models.Comment(
        content=comment.content,  # <-- Change these to 'content'
        media_id=media_id,
        user_id=current_user.id
    )
    db.add(new_comment)
    db.commit()
    return {"message": "Comment posted! 💬", "content": comment.content} # <-- Change this to 'content'

@app.post("/media/{media_id}/share", status_code=status.HTTP_201_CREATED)
def share_photo(media_id: str, platform: str = "copy_link", db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # 1. Log the share in the database so we can count it later
    new_share = models.Share(
        platform=platform,
        media_id=media_id,
        user_id=current_user.id
    )
    db.add(new_share)
    db.commit()
    
    # 2. Grab the photo URL so the user can send it to their friend
    photo = db.query(models.Media).filter(models.Media.id == media_id).first()
    
    return {
        "message": f"Tracked a share on {platform}! 🚀", 
        "share_link": photo.file_url if photo else "Photo not found"
    }
# ==========================================
# 🔍 READ & SEARCH ROUTES (THE WOW FACTOR)
# ==========================================

@app.get("/media/{media_id}", status_code=status.HTTP_200_OK)
def get_photo_details(media_id: str, db: Session = Depends(get_db)):
    # 1. Find the photo
    photo = db.query(models.Media).filter(models.Media.id == media_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
        
    # 2. Count the social stats
    like_count = db.query(models.Like).filter(models.Like.media_id == media_id).count()
    share_count = db.query(models.Share).filter(models.Share.media_id == media_id).count()
    
    # 3. Get all the comments
    comments = db.query(models.Comment).filter(models.Comment.media_id == media_id).all()
    
    return {
        "photo": photo,
        "likes": like_count,
        "shares": share_count,
        "comments": [{"text": c.content, "user_id": c.user_id} for c in comments]
    }

@app.get("/media/search/tags", status_code=status.HTTP_200_OK)
def search_photos_by_ai(tag: str, db: Session = Depends(get_db)):
    # 🧠 THE AI SEARCH MAGIC: Find any photo where the ai_tags column contains the search word!
    # The .ilike() function makes it case-insensitive, so "crowd", "Crowd", and "CROWD" all work.
    search_results = db.query(models.Media).filter(models.Media.ai_tags.ilike(f"%{tag}%")).all()
    
    if not search_results:
        return {"message": f"No photos found with the AI tag: {tag}", "results": []}
        
    return {
        "message": f"Found {len(search_results)} photos matching '{tag}'!",
        "results": search_results
    }
