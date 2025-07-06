# app/api/v1/endpoints/downloads.py
from fastapi import APIRouter, HTTPException, BackgroundTasks, status # Import status
from fastapi.responses import FileResponse
# Import the new schema
from app.models.schemas import DownloadRequest, InfoResponse, DownloadTask, DownloadInitiatedResponse, DownloadStatusResponse
from app.services import download_service # Assuming download_service is an instance or has static methods
from app.core.config import settings
import os
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/extract_info", response_model=InfoResponse)
async def extract_info(request: DownloadRequest):
    logger.info(f"Received info extraction request for URL: {request.url}")
    try:
        # Ensure request.url is converted to string for yt-dlp if it's HttpUrl type
        info = await download_service.extract_media_info(str(request.url))
        return {"status": "success", "info": info}
    except Exception as e:
        logger.error(f"Error extracting info for {request.url}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to extract info: {e}")


@router.post("/start", response_model=DownloadInitiatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_download(request: DownloadRequest):
    logger.info(f"Received download start request for URL: {request.url}")
    if not request.url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL is required.")

    try:
        # Ensure request.url is passed as a string if DownloadTask expects str
        task_id = await download_service.initiate_download_task(request)
        return DownloadInitiatedResponse( # Use the new schema here
            status="accepted",
            message="Download initiated",
            task_id=task_id,
            status_websocket_url=f"/ws/status/{task_id}"
        )
    except Exception as e:
        logger.error(f"Error initiating download: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/status/{task_id}", response_model=DownloadStatusResponse)
async def get_download_status(task_id: str):
    task = download_service.get_download_status(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    # --- FIX APPLIED HERE ---
    # Return the DownloadStatusResponse object directly
    # Ensure task.status is converted to its string value if it's an Enum
    return DownloadStatusResponse(
        status=task.status, # Assuming task.status is already a string ('completed', 'failed', 'downloading')
        task=task # Pass the DownloadTask object directly
    )
    # --- END FIX ---

@router.get("/downloaded/{filename}")
async def get_downloaded_file(filename: str):
    # Ensure settings.DOWNLOAD_DIR is a Path object or convert it
    file_path = settings.DOWNLOAD_DIR / filename # Assuming DOWNLOAD_DIR is a Path object

    if not file_path.is_file(): # Use .is_file() for Path objects
        logger.warning(f"Requested file not found: {filename}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    # Security check: Prevent path traversal
    # Ensure the requested filename is within the intended download directory
    # This is crucial for security
    resolved_file_path = file_path.resolve()
    if not str(resolved_file_path).startswith(str(settings.DOWNLOAD_DIR.resolve())):
        logger.error(f"Attempted path traversal detected: {filename}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path.")

    logger.info(f"Serving file: {filename}")
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")