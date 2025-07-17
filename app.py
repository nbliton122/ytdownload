from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import threading
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global dictionary to store download progress
download_progress = {}

# Path to the cookies file (removed space from filename)
# COOKIES_FILE = os.path.join(os.getcwd(), 'Youtube_cookies.txt') # Removed for public video download only

class ProgressHook:
    def __init__(self, download_id):
        self.download_id = download_id
    
    def __call__(self, d):
        if d["status"] == "downloading":
            percent = d.get("_percent_str", "N/A")
            speed = d.get("_speed_str", "N/A")
            download_progress[self.download_id] = {
                "status": "downloading",
                "percent": percent,
                "speed": speed,
                "filename": d.get("filename", "Unknown")
            }
        elif d["status"] == "finished":
            download_progress[self.download_id] = {
                "status": "finished",
                "percent": "100%",
                "speed": "Complete",
                "filename": d.get("filename", "Unknown"),
                "filepath": d.get("filename", "")
            }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/download", methods=["POST"])
def download_video():
    try:
        data = request.get_json()
        url = data.get("url")
        format_type = data.get("format", "mp3")
        
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        # Generate unique download ID
        download_id = str(uuid.uuid4())
        
        # Initialize progress
        download_progress[download_id] = {
            "status": "starting",
            "percent": "0%",
            "speed": "Initializing...",
            "filename": "Unknown"
        }
        
        # Start download in background thread
        thread = threading.Thread(target=download_worker, args=(url, format_type, download_id))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "success": True,
            "download_id": download_id,
            "message": "Download started"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def download_worker(url, format_type, download_id):
    try:
        # Create downloads directory if it doesn't exist
        downloads_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Configure yt-dlp options
        ydl_opts = {
            "outtmpl": os.path.join(downloads_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [ProgressHook(download_id)],
            # "cookiefile": COOKIES_FILE, # Removed for public video download only
        }

        if format_type == "mp3":
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:  # mp4
            ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]"
            ydl_opts["merge_output_format"] = "mp4"
        
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Unknown")
            
            # Update final status
            download_progress[download_id].update({
                "status": "completed",
                "title": title,
                "percent": "100%",
                "speed": "Complete"
            })
            
    except Exception as e:
        download_progress[download_id] = {
            "status": "error",
            "error": str(e),
            "percent": "0%",
            "speed": "Failed"
        }

@app.route("/api/progress/<download_id>")
def get_progress(download_id):
    progress = download_progress.get(download_id, {
        "status": "not_found",
        "error": "Download ID not found"
    })
    return jsonify(progress)

@app.route("/api/info", methods=["POST"])
def get_video_info():
    try:
        data = request.get_json()
        url = data.get("url")
        
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            # "cookiefile": COOKIES_FILE, # Removed for public video download only
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return jsonify({
                "success": True,
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown"),
                "view_count": info.get("view_count", 0),
                "thumbnail": info.get("thumbnail", "")
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/downloads")
def list_downloads():
    downloads_dir = os.path.join(os.getcwd(), "downloads")
    if not os.path.exists(downloads_dir):
        return jsonify({"downloads": []})
    
    files = []
    for filename in os.listdir(downloads_dir):
        filepath = os.path.join(downloads_dir, filename)
        if os.path.isfile(filepath):
            files.append({
                "filename": filename,
                "size": os.path.getsize(filepath),
                "modified": datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
            })
    
    return jsonify({"downloads": files})

@app.route("/api/download-file/<filename>")
def download_file(filename):
    downloads_dir = os.path.join(os.getcwd(), "downloads")
    filepath = os.path.join(downloads_dir, filename)
    
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
