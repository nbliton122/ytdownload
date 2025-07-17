from flask import Flask, request, jsonify, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pytube import YouTube
import os
import uuid

app = Flask(__name__)

# Rate limiter setup using default global limiter
limiter = Limiter(get_remote_address, app=app, default_limits=["10 per hour"])

@app.route("/")
def home():
    return "YouTube Video Downloader API"

@app.route("/download", methods=["POST"])
@limiter.limit("5 per hour")
def download_video():
    data = request.json
    if not data or "url" not in data:
        return jsonify({"error": "No URL provided"}), 400

    url = data["url"]
    try:
        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc().first()

        if not stream:
            return jsonify({"error": "No downloadable streams found"}), 404

        filename = f"{uuid.uuid4()}.mp4"
        stream.download(filename=filename)

        response = send_file(filename, as_attachment=True)
        os.remove(filename)
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
