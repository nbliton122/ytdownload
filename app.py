from flask import Flask, render_template, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import yt_dlp
import os

app = Flask(__name__)

# Initialize limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per hour"]
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
@limiter.limit("5 per minute")
def download():
    url = request.form.get('url')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    try:
        # Set download options
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': os.path.join('downloads', '%(title)s.%(ext)s'),
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            filename = ydl.prepare_filename(info_dict)
            ydl.download([url])

        return jsonify({'message': 'Download completed', 'filename': filename})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    os.makedirs('downloads', exist_ok=True)
    app.run(debug=True)
