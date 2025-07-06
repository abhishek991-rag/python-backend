# main.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints import downloads
from app.core.config import settings
from app.core.logger import setup_logging
from app.models.schemas import DownloadRequest # Make sure DownloadResponse is imported
from app.services.download_service import initiate_download_task, get_download_status # Removed get_downloaded_file
# Setup logging first
setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description=settings.PROJECT_DESCRIPTION,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(downloads.router, prefix="/api/v1", tags=["downloads"])

@app.get("/")
async def root():
    return {"message": "Welcome to the Python Downloader Backend!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
    
