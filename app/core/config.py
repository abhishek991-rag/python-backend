# app/core/config.py
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv() # Load environment variables from .env

class Settings:
    PROJECT_NAME: str = "Python Downloader Backend"
    PROJECT_DESCRIPTION: str = "A backend to download multimedia from various platforms."
    API_VERSION: str = "1.0.0"

    PORT: int = int(os.getenv("PORT", 8000))
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(',')

    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent # Root of the project
    DOWNLOAD_DIR: Path = BASE_DIR / os.getenv("DOWNLOAD_DIR", "downloads")

    # Ensure download directory exists
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()