from flask import Flask, request, jsonify, send_file
import yt_dlp, os, uuid
import time

app = Flask(__name__)
os.makedirs("downloads", exist_ok=True)

@app.route("/download", methods=["POST"])
def download_audio():
    data = request.get_json()
    url = data.get("url")
    fmt = data.get("format", "mp3")
    
    file_id = str(uuid.uuid4()) + "." + fmt
    path = os.path.join("downloads", file_id)

    cookies_file = "youtube_cookies.txt"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": path,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": fmt,
        }],
        "cookiefile": cookies_file if os.path.exists(cookies_file) else None,
        "nocheckcertificate": True,
        "retries": 3,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        time.sleep(2)  # বট এড়ানোর জন্য ডিলে
        return jsonify(success=True, file=f"/files/{file_id}")
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route("/files/<filename>")
def serve_file(filename):
    return send_file(os.path.join("downloads", filename), as_attachment=True)

@app.route('/healthz')
def health_check():
    return jsonify(status="healthy"), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)