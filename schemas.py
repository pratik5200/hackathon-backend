from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid
# What the user sends TO the server
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "Club Member"

# What the server sends BACK to the user (notice we hide the password!)
class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True



# What the user sends TO the server to create an event
class EventCreate(BaseModel):
    title: str
    description: str
    location: str
    date: datetime

# What the server sends BACK to the user
class EventResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    location: str
    date: datetime
    owner_id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True
# The VIP Token we send back to them when they log in
class Token(BaseModel):
    access_token: str
    token_type: str