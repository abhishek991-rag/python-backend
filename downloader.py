import yt_dlp
import os
import json # Added for potential debugging of info dictionary

# Define the directory where videos will be saved
DOWNLOAD_DIR = "downloads"

def download_video(url, format_choice="bestvideo+bestaudio/best", browser_for_cookies=None):
    """
    Downloads a video from the given URL using yt-dlp.

    Args:
        url (str): The URL of the video to download.
        format_choice (str): yt-dlp format string (e.g., 'bestvideo+bestaudio/best', 'mp4', 'webm', 'bestaudio').
                             'bestvideo+bestaudio/best' downloads the best quality video and audio
                             and merges them (requires ffmpeg).
        browser_for_cookies (str, optional): The browser to extract cookies from (e.g., 'chrome', 'firefox', 'edge').
                                             If provided, yt-dlp will attempt to use cookies for authentication.
    Returns:
        dict: A dictionary containing download status and info, or None on failure.
              Includes 'filepath' if successful.
    """
    # Ensure the download directory exists
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    # yt-dlp options
    ydl_opts = {
        'format': format_choice,
        # Output template: saves files in DOWNLOAD_DIR with title and original extension
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s (%(id)s).%(ext)s'),
        'noplaylist': True, # Ensure only single video downloads, not playlists by default
        # 'progress_hooks': [lambda d: print(f"YT-DLP Progress: {d['status']} - {d.get('_percent_str', '')} - {d.get('filename', '')}")], # Detailed progress (can be noisy)
        'quiet': False, # Set to False for more detailed yt-dlp output in console during development
        'no_warnings': False, # Show warnings from yt-dlp
        'log_file': 'yt_dlp_log.txt', # Log yt-dlp output to a file for review
        'merge_output_format': 'mp4', # Ensure final merged format is MP4 for broad compatibility
        'postprocessors': [], # Initialize empty, then conditionally add
    }

    # --- ADDED: Cookie handling for Instagram and other sites requiring login ---
    if browser_for_cookies:
        ydl_opts['cookiesfrombrowser'] = browser_for_cookies
        print(f"Using cookies from browser: {browser_for_cookies}")
    # --- END ADDED ---

    # Add audio extraction post-processor if format_choice is for audio
    if format_choice == 'bestaudio/best':
        ydl_opts['postprocessors'].append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192', # High quality MP3
        })
        # When extracting audio, the output extension should be mp3 or the preferredcodec
        ydl_opts['outtmpl'] = os.path.join(DOWNLOAD_DIR, '%(title)s (%(id)s).%(ext)s') # yt-dlp will handle changing ext to mp3

    print(f"\n--- Starting yt-dlp download for URL: {url} with format: {format_choice} ---")
    print(f"yt-dlp options being used: {ydl_opts}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info and download the video
            info = ydl.extract_info(url, download=True)

            # --- DEBUGGING OUTPUT ---
            print("\n--- yt-dlp Raw Info Dictionary (after download) ---")
            # print(json.dumps(info, indent=2)) # Uncomment if you have 'import json' and want pretty print
            print("--- End Raw Info ---")

            # Determine the final downloaded file path
            filepath = ydl.prepare_filename(info)

            print(f"Determined final filepath: {filepath}")
            # --- END DEBUGGING OUTPUT ---

            return {
                "status": "success",
                "title": info.get('title'),
                "id": info.get('id'),
                "filepath": filepath, # This is the full path on the server
                "thumbnail": info.get('thumbnail'),
                "duration": info.get('duration'),
                "uploader": info.get('uploader'),
                "extractor": info.get('extractor'),
            }
    except yt_dlp.utils.DownloadError as e:
        # Specific error for yt-dlp download failures (e.g., video unavailable, geo-restricted, login required)
        print(f"Download Error (yt-dlp): {e}")
        return {"status": "error", "message": f"Download Error: {str(e)}"}
    except Exception as e:
        # Catch any other unexpected errors
        print(f"An unexpected error occurred during download: {e}")
        return {"status": "error", "message": f"An unexpected server error occurred: {str(e)}"}

if __name__ == "__main__":
    # Ensure the DOWNLOAD_DIR exists for standalone testing
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    print("--- Running standalone tests for downloader.py ---")

    # IMPORTANT: Replace 'chrome' with your actual browser if different (e.g., 'firefox', 'edge', 'brave')
    # Make sure you are logged into Instagram in this browser.
    BROWSER_FOR_COOKIES = "chrome" # <--- SET YOUR BROWSER HERE!

    # TEST 1: YouTube Video Download
    print("\nAttempting YouTube video download...")
    youtube_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Rick Astley - Never Gonna Give You Up
    result_youtube_video = download_video(youtube_video_url, format_choice="bestvideo+bestaudio/best")
    if result_youtube_video and result_youtube_video["status"] == "success":
        print(f"YouTube Video Downloaded: {result_youtube_video['title']} to {result_youtube_video['filepath']}")
    else:
        print(f"YouTube Video Download failed: {result_youtube_video.get('message', 'Unknown error')}")

    # TEST 2: YouTube Audio Download
    print("\nAttempting YouTube audio download...")
    result_youtube_audio = download_video(youtube_video_url, format_choice="bestaudio/best")
    if result_youtube_audio and result_youtube_audio["status"] == "success":
        print(f"YouTube Audio Downloaded: {result_youtube_audio['title']} to {result_youtube_audio['filepath']}")
    else:
        print(f"YouTube Audio Download failed: {result_youtube_audio.get('message', 'Unknown error')}")

    # TEST 3: Instagram Reel (Requires public reel, private might fail)
    print("\nAttempting Instagram reel download with cookies...")
    # NOTE: Replace with a public Instagram reel URL. Private reels will likely fail if cookies don't grant access.
    # Make sure you are logged into Instagram in the browser specified by BROWSER_FOR_COOKIES.
    instagram_url = "https://www.instagram.com/reel/C71_B_TIZWk/" # Example, find a public one or one you can access when logged in
    result_instagram = download_video(instagram_url, format_choice="bestvideo+bestaudio/best", browser_for_cookies=BROWSER_FOR_COOKIES)
    if result_instagram and result_instagram["status"] == "success":
        print(f"Instagram Reel Downloaded: {result_instagram['title']} to {result_instagram['filepath']}")
    else:
        print(f"Instagram Reel Download failed: {result_instagram.get('message', 'Unknown error')}")

    # TEST 4: Facebook Video (Requires public video, private/gated might fail)
    print("\nAttempting Facebook video download with cookies...")
    # NOTE: Replace with a public Facebook video URL. Private/gated content will likely fail.
    # Search for "public facebook videos" on Google to find good test cases.
    facebook_url = "https://www.facebook.com/PewDiePie/videos/1234567890/" # Placeholder, find a public one
    result_facebook = download_video(facebook_url, format_choice="bestvideo+bestaudio/best", browser_for_cookies=BROWSER_FOR_COOKIES)
    if result_facebook and result_facebook["status"] == "success":
        print(f"Facebook Video Downloaded: {result_facebook['title']} to {result_facebook['filepath']}")
    else:
        print(f"Facebook Video Download failed: {result_facebook.get('message', 'Unknown error')}")

    print("\n--- End of standalone tests ---")
