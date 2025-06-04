from flask import Flask, request, jsonify, send_from_directory
from downloader import download_video, DOWNLOAD_DIR # Import our download function and directory
import os
import threading
import uuid # For unique filenames to avoid conflicts
from flask_cors import CORS # Import CORS for cross-origin requests

app = Flask(__name__)

# Enable CORS for all routes.
# IMPORTANT: For production, specify allowed origins explicitly for better security.
# Example: CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:5500"}})
CORS(app)

# This dictionary will store the status of ongoing downloads
# Key: task_id, Value: {"status": "pending/downloading/completed/failed", "info": {...}, "filepath": None, "error": None}
download_tasks = {}

@app.route('/')
def home():
    return "Video Downloader Backend is running!"

@app.route('/download', methods=['POST'])
def start_download():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400

    video_url = data['url']
    format_type = data.get('format', 'video') # 'video' or 'audio'

    task_id = str(uuid.uuid4()) # Generate a unique ID for this download task
    # Initialize the task status
    download_tasks[task_id] = {"status": "pending", "info": None, "filepath": None, "error": None}

    # Determine the yt-dlp format string based on format_type requested from frontend
    ydl_format_choice = "bestvideo+bestaudio/best"
    if format_type == 'audio':
        ydl_format_choice = "bestaudio/best"

    # Run the download in a separate thread to avoid blocking the main Flask thread
    # This is crucial for long-running operations like downloads.
    threading.Thread(target=perform_download_task, args=(task_id, video_url, ydl_format_choice)).start()

    # Return an immediate response indicating the download has started
    return jsonify({
        "message": "Download started",
        "task_id": task_id,
        "status_check_url": f"/status/{task_id}", # URL for client to poll for status
        "initial_status": "pending"
    }), 202 # 202 Accepted, indicating that the request has been accepted for processing

def perform_download_task(task_id, video_url, ydl_format_choice):
    """
    Function to be run in a separate thread to handle the download.
    Updates the global download_tasks dictionary based on download result.
    """
    print(f"Backend Thread: Starting download for task_id: {task_id} - URL: {video_url}")
    download_tasks[task_id]["status"] = "downloading" # Update status in dictionary

    # Call the core download function from downloader.py
    result = download_video(video_url, format_choice=ydl_format_choice)

    if result and result["status"] == "success":
        download_tasks[task_id]["status"] = "completed"
        # Store metadata (excluding the full local filepath)
        download_tasks[task_id]["info"] = {k: v for k, v in result.items() if k != 'filepath'}
        # Store only the filename (basename) which is needed for the download link
        download_tasks[task_id]["filepath"] = os.path.basename(result["filepath"])
        print(f"Backend Thread: Task {task_id} completed. File: {result['filepath']}")
    else:
        download_tasks[task_id]["status"] = "failed"
        download_tasks[task_id]["error"] = result.get("message", "Unknown download error")
        print(f"Backend Thread: Task {task_id} failed. Error: {result.get('message', 'Unknown error')}")

@app.route('/status/<task_id>', methods=['GET'])
def get_download_status(task_id):
    """
    Endpoint for the client to check the status of a download task.
    """
    task = download_tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task ID not found"}), 404

    # Prepare response data based on current task status
    response_data = {
        "task_id": task_id,
        "status": task["status"]
    }
    if task["status"] == "completed":
        response_data["download_link"] = f"/downloaded/{task['filepath']}" # Link to download the file
        response_data["info"] = task["info"] # Include metadata if available
    elif task["status"] == "failed":
        response_data["error"] = task["error"]
    elif task["status"] == "downloading":
        response_data["message"] = "Download in progress. Check back later."

    return jsonify(response_data)

@app.route('/downloaded/<path:filename>', methods=['GET']) # Use <path:filename> to handle slashes if any
def serve_downloaded_file(filename):
    """
    Serves the downloaded file to the client.
    Using send_from_directory ensures safe file serving.
    """
    if not filename:
        return jsonify({"error": "Filename missing"}), 400

    try:
        # Flask's send_from_directory is secure against directory traversal
        # It automatically handles the `as_attachment=True` to force download
        return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"error": "File not found on server. It might still be downloading or an error occurred during storage."}), 404
    except Exception as e:
        print(f"Error serving file {filename}: {e}") # Log unexpected serving errors
        return jsonify({"error": f"Could not serve file: {e}"}), 500

if __name__ == '__main__':
    # Create the downloads directory if it doesn't exist when the app starts
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    # Run the Flask app
    # debug=True provides helpful error messages during development but should be False in production
    # host='0.0.0.0' makes the server accessible from other devices on the network (useful for testing frontend on different machines)
    app.run(debug=True, host='0.0.0.0', port=5000)