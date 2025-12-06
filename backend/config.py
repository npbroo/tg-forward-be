from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the path to the .env file (in the parent directory of backend/)
env_path = Path(__file__).parent.parent / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(env_path),
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra fields from .env file
    )
    REDIS_URL: str

    TG_API_ID: int
    TG_API_HASH: str
    TG_PHONE: str

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "password"

    JWT_SECRET: str = "super-long-random-string-change-me"
    JWT_ALGO: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

settings = Settings()
