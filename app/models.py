from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class MediaType(str, enum.Enum):
    image = "image"
    video = "video"


class PostType(str, enum.Enum):
    image = "image"
    video = "video"
    slider = "slider"


class PostStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    failed = "failed"
    scheduled = "scheduled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    tiktok_access_token = Column(String, nullable=True)
    tiktok_open_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    media = relationship("Media", back_populates="owner")
    posts = relationship("TikTokPost", back_populates="owner")


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_name = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    media_type = Column(Enum(MediaType), nullable=False)
    file_size = Column(Integer, nullable=True)
    prompt = Column(Text, nullable=True)
    source = Column(String, default="upload")  # upload | generated
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="media")


class TikTokPost(Base):
    __tablename__ = "tiktok_posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_type = Column(Enum(PostType), nullable=False)
    status = Column(Enum(PostStatus), default=PostStatus.draft)
    title = Column(String, nullable=True)
    caption = Column(Text, nullable=True)
    media_ids = Column(Text, nullable=True)  # JSON list of media IDs
    tiktok_post_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="posts")
