from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models import MediaType, PostType, PostStatus


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    tiktok_open_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class MediaOut(BaseModel):
    id: int
    filename: str
    original_name: Optional[str]
    file_path: str
    media_type: MediaType
    file_size: Optional[int]
    prompt: Optional[str]
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateImageRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    width: Optional[int] = 1024
    height: Optional[int] = 1024


class GenerateVideoRequest(BaseModel):
    prompt: str
    duration: Optional[int] = 5
    style: Optional[str] = "cinematic"


class SlideShowRequest(BaseModel):
    media_ids: List[int]
    duration_per_image: Optional[float] = 3.0
    fps: Optional[int] = 24
    transition: Optional[str] = "fade"


class TikTokPostCreate(BaseModel):
    post_type: PostType
    caption: str
    media_ids: List[int]
    title: Optional[str] = ""


class TikTokPostOut(BaseModel):
    id: int
    post_type: PostType
    status: PostStatus
    title: Optional[str]
    caption: Optional[str]
    tiktok_post_id: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    published_at: Optional[datetime]

    class Config:
        from_attributes = True
