# app/models/schemas.py
from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
from typing import Optional, List, Dict, Any

# --- Input Schemas ---
class DownloadRequest(BaseModel):
    url: HttpUrl = Field(..., example="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    format: Optional[str] = Field("mp4", example="mp4", description="Output format (e.g., mp4, mp3, image)")
    quality: Optional[str] = Field("bestvideo+bestaudio/best", example="bestvideo[height<=720]", description="yt-dlp format selection string")
    browserForCookies: Optional[str] = Field(None, example="chrome", description="Browser to load cookies from (e.g., chrome, firefox)")
    proxy: Optional[str] = Field(None, example="http://user:password@proxy.example.com:8080", description="Proxy server to use (e.g., http://host:port or socks5://host:port)") # <-- Added this line

# --- Output Schemas ---
class Progress(BaseModel):
    percent: float = 0
    eta: str = "N/A"
    speed: str = "N/A"
    status_message: str = "Queued"

class FormatInfo(BaseModel):
    format_id: Optional[str] = None
    ext: Optional[str] = None
    resolution: Optional[str] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    description: Optional[str] = None
    filesize: Optional[float] = None

class MediaInfo(BaseModel):
    title: Optional[str] = None
    id: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    uploader: Optional[str] = None
    extractor: Optional[str] = None
    available_formats: List[FormatInfo] = []
    webpage_url: Optional[str] = None
    is_playlist: Optional[bool] = False
    playlist_count: Optional[int] = None

class DownloadTask(BaseModel):
    id: str
    url: str # This is now a string, as fixed previously
    format: Optional[str] = None
    quality: Optional[str] = None
    browser: Optional[str] = None
    status: str # queued, processing, downloading, completed, failed
    progress: Progress
    info: Optional[MediaInfo] = None
    filepath: Optional[str] = None # Relative path to downloaded file
    error: Optional[str] = None
    startTime: datetime
    endTime: Optional[datetime] = None

class InfoResponse(BaseModel):
    status: str
    info: MediaInfo

# NEW SCHEMA for the /api/v1/start endpoint's immediate response
class DownloadInitiatedResponse(BaseModel):
    status: str = "accepted"
    message: str = "Download initiated"
    task_id: str
    status_websocket_url: str

# This schema is for the /api/v1/status/{task_id} endpoint
class DownloadStatusResponse(BaseModel):
    status: str
    task: DownloadTask # This correctly includes the full task object