from flask import Flask, request, jsonify
import subprocess
import os
import uuid

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route("/", methods=["GET"])
def home():
    return "YouTube Downloader is running"

@app.route("/download", methods=["POST"])
def download_video():
    data = request.get_json()
    url = data.get("url")
    
    if not url:
        return jsonify({"error": "URL is required"}), 400

    filename = f"{uuid.uuid4()}.mp4"
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)

    try:
        subprocess.run([
            "yt-dlp",
            "--no-playlist",
            "-f", "best",
            "-o", filepath,
            url
        ], check=True)

        return jsonify({"message": "Download successful", "file": filename})

    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Download failed", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
