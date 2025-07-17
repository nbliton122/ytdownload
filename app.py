from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import threading
import uuid
from datetime import datetime
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import time

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Rate limiter: 5 requests per minute per IP
limiter = Limiter(app, key_func=get_remote_address)

# Global dictionary to store download progress
download_progress = {}

downloads_dir = os.path.join(os.getcwd(), "downloads")
os.makedirs(downloads_dir, exist_ok=True)

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
@limiter.limit("5 per minute")
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
        # First check if video is public
        ydl_opts_info = {
            "quiet": True,
            "no_warnings": True,
            "no_playlist": True,
            "ignoreerrors": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
            availability = info.get("availability", "public")
            if availability != "public":
                download_progress[download_id] = {
                    "status": "error",
                    "error": "Video is not public or is restricted.",
                    "percent": "0%",
                    "speed": "N/A"
                }
                return
        
        ydl_opts = {
            "outtmpl": os.path.join(downloads_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [ProgressHook(download_id)],
            "no_playlist": True,
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
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            title = info.get("title", "Unknown")
            
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
            "no_playlist": True,
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
    filepath = os.path.join(downloads_dir, filename)
    
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

def cleanup_downloads():
    while True:
        now = time.time()
        for f in os.listdir(downloads_dir):
            filepath = os.path.join(downloads_dir, f)
            if os.path.isfile(filepath):
                if now - os.path.getmtime(filepath) > 3600:  # ১ ঘণ্টার বেশি পুরানো ফাইল
                    os.remove(filepath)
        time.sleep(3600)

if __name__ == "__main__":
    # Cleanup thread চালিয়ে দাও background-এ
    cleanup_thread = threading.Thread(target=cleanup_downloads, daemon=True)
    cleanup_thread.start()
    
    app.run(host="0.0.0.0", port=10000, debug=True)
