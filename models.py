from sqlalchemy import Column, String, DateTime, ForeignKey,TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID 
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
print("HELLO! PYTHON IS SUCCESSFULLY READING THE REAL MODELS.PY FILE!")
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="Club Member") # Default role from PDF requirements
    
    # The magical link: A user can own many events
    events = relationship("Event", back_populates="owner")

class Event(Base):
    __tablename__ = "events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(String)
    location = Column(String)
    date = Column(DateTime)
    
    # The Foreign Key: This column stores the exact ID of the User who made it
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # The magical link: The event belongs to one owner
    owner = relationship("User", back_populates="events")
    media_items = relationship("Media", back_populates="event")

class Media(Base):
    __tablename__ = "media"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    file_url = Column(String, nullable=False)
    ai_tags = Column(String, nullable=True) # <-- Add this line!
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"))
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)
    
    # Magical relationships
    event = relationship("Event", back_populates="media_items")
    owner = relationship("User")

class Comment(Base):
    __tablename__ = "comments"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    content = Column(String, nullable=False)
    
    # 👇 Changed back to standard UUID
    media_id = Column(UUID(as_uuid=True), ForeignKey("media.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)

class Like(Base):
    __tablename__ = "likes"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # 👇 Changed back to standard UUID
    media_id = Column(UUID(as_uuid=True), ForeignKey("media.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)

class Share(Base):
    __tablename__ = "shares"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    platform = Column(String, nullable=True) 
    
    # 👇 Changed back to standard UUID
    media_id = Column(UUID(as_uuid=True), ForeignKey("media.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)