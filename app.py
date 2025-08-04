import os
import ffmpeg
import yt_dlp
import threading
import time
from flask import Flask, request, render_template, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Directories
RAW_DIR = 'reels'
EDITED_DIR = 'edited'
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(EDITED_DIR, exist_ok=True)

latest_output_file = ""

def sanitize_filename(name):
    return "".join(c for c in name if c.isalnum() or c in "._- ").strip()

def schedule_file_delete(path, delay=300):
    def delete_later():
        time.sleep(delay)
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"🗑️ Deleted file: {path}")
        except Exception as e:
            print(f"❌ Failed to delete {path}: {e}")
    threading.Thread(target=delete_later, daemon=True).start()

def download_reel(reel_url):
    global latest_output_file
    try:
        ydl_opts = {
            'format': 'bv+ba/best',
            'outtmpl': os.path.join(RAW_DIR, '%(title).80s.%(ext)s'),
            'merge_output_format': 'mp4',
            'noplaylist': True,
            'quiet': True,
            'cookiefile': 'cookies.txt',  # <-- Use your cookies file here
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(reel_url, download=True)
            filename = ydl.prepare_filename(info)
            if not filename.endswith('.mp4'):
                filename = os.path.splitext(filename)[0] + '.mp4'

            safe_name = sanitize_filename(os.path.basename(filename))
            edited_output = os.path.join(EDITED_DIR, safe_name)

            add_styled_text(filename, edited_output, "Check Pin Comment")

            schedule_file_delete(filename)
            schedule_file_delete(edited_output)

            latest_output_file = safe_name
            return {
                "title": info.get('title', 'No Title'),
                "description": info.get('description', 'No Description'),
                "filename": safe_name
            }

    except Exception as e:
        return {"error": str(e)}


def add_styled_text(input_path, output_path, text, fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
    drawtext_filter = (
        f"drawtext=fontfile='{fontfile}':"
        f"text='{text}':"
        f"fontcolor=red:"
        f"fontsize=40:"
        f"box=1:boxcolor=black@0.4:boxborderw=10:"
        f"x=(w-text_w)/2:y=(h-text_h)-80"
    )
    ffmpeg.input(input_path).output(
        output_path,
        vf=drawtext_filter,
        vcodec='libx264',
        acodec='copy',
        preset='ultrafast',
        movflags='faststart'
    ).run(overwrite_output=True, quiet=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    info = None
    if request.method == 'POST':
        reel_url = request.form['url']
        info = download_reel(reel_url)
    return render_template('index.html', info=info)

@app.route('/download')
def download_file():
    global latest_output_file
    return send_from_directory(EDITED_DIR, latest_output_file, as_attachment=True)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=False)

