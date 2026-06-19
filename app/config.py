from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "TikTok Creator"
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/tiktok_creator"

    # File storage
    UPLOAD_DIR: str = "app/static/uploads"
    MAX_UPLOAD_SIZE_MB: int = 500

    # Hugging Face (image generation)
    HUGGINGFACE_API_KEY: str = ""
    HF_IMAGE_MODEL: str = "black-forest-labs/FLUX.1-schnell"

    # Replicate (AI video generation)
    REPLICATE_API_TOKEN: str = ""

    # TikTok API
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    TIKTOK_ACCESS_TOKEN: str = ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
