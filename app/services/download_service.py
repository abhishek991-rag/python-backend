# app/services/download_service.py
import re
import asyncio
import yt_dlp
import os
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from app.core.config import settings
from app.models.schemas import DownloadRequest, DownloadTask, MediaInfo, Progress # Progress को इम्पोर्ट करें ताकि यह सही ऑब्जेक्ट बना सके

logger = logging.getLogger(__name__)

download_tasks: Dict[str, DownloadTask] = {} # Stores current download task statuses, with type hint

# Mock WebSocket/Progress Reporter for CLI & API
class ProgressReporter:
    def __init__(self, task_id: str):
        self.task_id = task_id

    def update_progress(self, percent: float, eta: str, speed: str, status_message: str):
        task = download_tasks.get(self.task_id)
        if task:
            # Ensure task.progress is a Progress object before updating its fields
            if not isinstance(task.progress, Progress):
                task.progress = Progress(percent=0, eta="N/A", speed="N/A", status_message="Initializing")

            task.progress.percent = percent
            task.progress.eta = eta
            task.progress.speed = speed
            task.progress.status_message = status_message
            logger.info(f"Task {self.task_id[:8]}... Progress: {percent:.2f}% ETA: {eta} Speed: {speed}")

    def set_status(self, status: str, error: str = None, filepath: str = None):
        task = download_tasks.get(self.task_id)
        if task:
            task.status = status
            task.error = error
            # Store only the base filename in task.filepath as expected by frontend
            task.filepath = os.path.basename(filepath) if filepath else None
            task.endTime = datetime.utcnow()
            logger.info(f"Task {self.task_id[:8]}... Status: {status} Error: {error}. File: {task.filepath}")

async def extract_media_info(url: str) -> MediaInfo:
    logger.info(f"Extracting info for URL: {url}")
    ydl_opts = {
        'dump_single_json': True,
        'flat_playlist': True,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = await asyncio.to_thread(ydl.extract_info, str(url), download=False)

            relevant_formats = []
            if 'formats' in info and info['formats']:
                for f in info['formats']:
                    if f.get('vcodec') != 'none' or (f.get('acodec') != 'none' and f.get('filesize')):
                        relevant_formats.append({
                            "format_id": f.get('format_id'),
                            "ext": f.get('ext'),
                            "resolution": f.get('resolution'),
                            "vcodec": f.get('vcodec'),
                            "acodec": f.get('acodec'),
                            "description": f.get('format_note') or f.get('format'),
                            "filesize": f.get('filesize') or f.get('filesize_approx'),
                        })
            return MediaInfo(
                title=info.get('title'),
                id=info.get('id'),
                thumbnail=info.get('thumbnail'),
                duration=info.get('duration'),
                uploader=info.get('uploader'),
                extractor=info.get('extractor'),
                available_formats=relevant_formats,
                webpage_url=info.get('webpage_url'),
                is_playlist=bool(info.get('entries')),
                playlist_count=len(info['entries']) if info.get('entries') else None
            )
        except yt_dlp.DownloadError as e:
            logger.error(f"yt-dlp info extraction error for {url}: {e}", exc_info=True)
            raise ValueError(f"Failed to extract info: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during info extraction for {url}: {e}", exc_info=True)
            raise ValueError(f"Failed to extract info due to an internal error: {e}")


async def initiate_download_task(request: DownloadRequest) -> str:
    task_id = str(uuid.uuid4())
    download_tasks[task_id] = DownloadTask(
        id=task_id,
        url=str(request.url),
        format=request.format,
        quality=request.quality,
        browser=request.browserForCookies,
        status="queued",
        progress=Progress(percent=0, eta="N/A", speed="N/A", status_message="Queued"), # Progress object यहाँ बनाएँ
        startTime=datetime.utcnow(),
    )
    logger.info(f"Download task added: {task_id} for URL: {request.url}")

    # Run the actual download in a background task
    asyncio.create_task(perform_download(task_id, request))
    return task_id

async def perform_download(task_id: str, request: DownloadRequest):
    task = download_tasks.get(task_id)
    if not task:
        logger.error(f"Task {task_id} not found during perform_download.")
        return

    logger.info(f"Starting download for task {task_id}: {request.url}")
    task.status = "downloading"
    reporter = ProgressReporter(task_id)

    # Compile the regex for ANSI escape codes once
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    final_info_dict = None # To store info_dict after successful download

    def progress_hook(d):
        nonlocal final_info_dict # Allow modifying outer scope variable

        # This hook is called by yt-dlp on progress updates
        if d['status'] == 'downloading':
            percent_raw = d.get('_percent_str', 'N/A')
            percent_cleaned = ansi_escape.sub('', percent_raw).replace('%', '').strip()

            percent = float(percent_cleaned) if percent_cleaned != 'N/A' and percent_cleaned != '' else 0.0
            eta = d.get('_eta_str', 'N/A').strip()
            speed = d.get('_speed_str', 'N/A').strip()
            reporter.update_progress(
                percent,
                eta,
                speed,
                f"Downloading: {d.get('filename', 'N/A')} {percent_cleaned}%"
            )
        elif d['status'] == 'finished':
            # This is called when download is complete, but before post-processing
            # The 'filename' here is usually the temporary file or the pre-processed file
            # We'll use final_info_dict to get the true final path after post-processing
            reporter.set_status("post-processing") # No filepath here yet
            logger.info(f"Task {task_id} finished download, starting post-processing.")
            # Store info_dict if available here, for post-processing info
            final_info_dict = d # d contains the info_dict after download

    # Get ffmpeg location from environment variable
    ffmpeg_path = os.getenv("YTDLP_FFMPEG_LOCATION")
    if not ffmpeg_path:
        logger.warning("YTDLP_FFMPEG_LOCATION environment variable not set. ffmpeg might not be found.")
        ffmpeg_path = 'ffmpeg' # Fallback to 'ffmpeg' in PATH if env var is empty

    # Construct yt-dlp options based on request
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best', # Default robust format
        'outtmpl': str(settings.DOWNLOAD_DIR / '%(title)s (%(id)s).%(ext)s'),
        'progress_hooks': [progress_hook],
        'ffmpeg_location': ffmpeg_path,
        'merge_output_format': 'mp4', # Default merge format
        'embed_metadata': True,
        'no_warnings': True,
        'quiet': True,
        'logger': logging.getLogger('yt_dlp'),
        'retries': 5, # Add some retries for robustness
        'socket_timeout': 30 # Timeout for network operations
    }

    # Apply format and quality from request
    if request.format and request.quality:
        if "audio" in request.format.lower():
            ydl_opts['format'] = request.quality # e.g., 'bestaudio/best'
            ydl_opts['extract_audio'] = True
            ydl_opts['audio_format'] = "mp3" # Or based on request.format
            ydl_opts['audio_quality'] = '192K'
            ydl_opts['outtmpl'] = str(settings.DOWNLOAD_DIR / '%(title)s (%(id)s).%(ext)s') # yt-dlp sets ext for audio
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            del ydl_opts['merge_output_format']

        elif request.format.lower() == 'image': # This branch should be handled carefully, yt-dlp is for video/audio
            ydl_opts['format'] = 'best'
            ydl_opts['writethumbnail'] = True
            ydl_opts['skip_download'] = True # Only download thumbnail
            ydl_opts['outtmpl'] = str(settings.DOWNLOAD_DIR / '%(title)s (%(id)s).%(ext)s')
            del ydl_opts['merge_output_format']

        else: # Video format
            ydl_opts['format'] = f"{request.quality}+bestaudio/bestvideo+bestaudio/best"
            ydl_opts['merge_output_format'] = request.format

    if request.browserForCookies:
        # yt-dlp expects a tuple for cookiesfrombrowser
        ydl_opts['cookiesfrombrowser'] = (request.browserForCookies, )
        logger.info(f"Using cookies from browser: {request.browserForCookies} for task {task_id}")

    # Add proxy if provided in the request
    if request.proxy:
        ydl_opts['proxy'] = request.proxy
        logger.info(f"Using proxy: {request.proxy} for task {task_id}")

    try:
        # Execute yt-dlp download in a separate thread
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # yt-dlp.download returns None on success, but the info_dict is passed through hooks
            # We need to explicitly extract info *after* download to get the final filepath reliably
            # A common pattern is to call extract_info with download=True and then use the returned info_dict
            # However, if using hooks, `ydl.download` just triggers the download.
            # To get the final_filepath after post-processing, we need to ensure it's captured correctly.
            
            # The most reliable way is to call extract_info again on the local file
            # or ensure the progress hook's 'd' dictionary (when status is 'finished') 
            # contains the final file path after all post-processing.
            # The 'filename' in the 'finished' status of the hook is often the pre-postprocessed file.
            
            # Let's try to get the info_dict directly from the download operation
            # This is often available in the info_dict passed to the 'finished' hook.
            # However, the info_dict from ydl.extract_info is more comprehensive for post-processed files.

            # We'll use the info_dict captured by the hook to determine the final filepath
            await asyncio.to_thread(ydl.download, [str(request.url)])

            # After download completes (and post-processing, if any)
            # final_info_dict should contain the info about the downloaded file
            if final_info_dict and final_info_dict.get('_filepath'):
                downloaded_file_full_path = final_info_dict['_filepath']
            elif final_info_dict and 'requested_downloads' in final_info_dict and final_info_dict['requested_downloads']:
                # For cases where multiple files are downloaded or post-processed
                downloaded_file_full_path = final_info_dict['requested_downloads'][0]['filepath']
            else:
                # Fallback: if _filepath is not set by hook, try to determine based on outtmpl
                # This is less reliable but can be a last resort.
                # Re-extract info on the URL to get the expected filename pattern
                # This is inefficient but necessary if hook doesn't provide it
                try:
                    re_extracted_info = await asyncio.to_thread(ydl.extract_info, str(request.url), download=False)
                    # Use the filename that yt-dlp *would* have used
                    predicted_filename = ydl.prepare_filename(re_extracted_info)
                    downloaded_file_full_path = os.path.join(settings.DOWNLOAD_DIR, predicted_filename)
                    if not os.path.exists(downloaded_file_full_path):
                        logger.warning(f"Predicted file path {downloaded_file_full_path} not found for task {task_id}.")
                        downloaded_file_full_path = None
                except Exception as e:
                    logger.error(f"Failed to predict filename for task {task_id}: {e}", exc_info=True)
                    downloaded_file_full_path = None

            if not downloaded_file_full_path:
                raise Exception("Could not determine final downloaded file path after completion.")

            reporter.set_status("completed", filepath=downloaded_file_full_path)
            logger.info(f"Task {task_id} completed successfully. File: {downloaded_file_full_path}")

    except yt_dlp.DownloadError as e:
        reporter.set_status("failed", error=str(e))
        logger.error(f"yt-dlp download error for {task_id}: {e}", exc_info=True)
    except Exception as e:
        reporter.set_status("failed", error=str(e))
        logger.error(f"Unexpected error during download for {task_id}: {e}", exc_info=True)

def get_download_status(task_id: str) -> Optional[DownloadTask]:
    return download_tasks.get(task_id)