import os
import re
import uuid
import traceback
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory, abort
import yt_dlp
import ffmpeg

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DL_DIR = BASE_DIR / "downloads"
EDITED_DIR = DL_DIR / "edited"
DL_DIR.mkdir(parents=True, exist_ok=True)
EDITED_DIR.mkdir(parents=True, exist_ok=True)

# Path to cookies file in main directory
COOKIES_FILE = BASE_DIR / "cookies.txt"  # Now a Path object

# ---- Helpers ----

def sanitize_filename(name: str) -> str:
    """Sanitize filenames for safe saving."""
    name = re.sub(r"[^\w\-. ]+", "_", name)
    return name.strip()[:120] or f"ig_{uuid.uuid4().hex[:8]}"

import time
import random

# --- helpers ---
def ydl_opts_for_instagram(output_path: Path):
    """Base yt-dlp options for Instagram, always reload cookies."""
    opts = {
        "outtmpl": str(output_path / "%(title)s_%(id)s.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "concurrent_fragment_downloads": 4,
        "retries": 10,
        "fragment_retries": 10,
        "http_chunk_size": 10485760,
        "quiet": False,
        "no_warnings": False,
        "ignoreerrors": False,
        "geo_bypass": True,
        "skip_download": False,
        "writethumbnail": False,
        "nocheckcertificate": True,
        "overwrites": True,
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            )
        }
    }

    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    else:
        print(f"[WARNING] Cookies file not found: {COOKIES_FILE}")

    return opts


def extract_metadata_only(url: str):
    """Extract metadata only (fresh session)."""
    opts = ydl_opts_for_instagram(DL_DIR)
    opts["skip_download"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def download_instagram(url: str):
    """Download Instagram media with fresh cookies per request."""
    # Small random delay to avoid Instagram bot detection
    time.sleep(random.uniform(1.0, 2.5))

    opts = ydl_opts_for_instagram(DL_DIR)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

        # Get best downloaded file
        if "requested_downloads" in info and info["requested_downloads"]:
            fp = info["requested_downloads"][0].get("filepath")
            if fp and os.path.exists(fp):
                return Path(fp), info

        filename = ydl.prepare_filename(info)
        if filename and not filename.endswith(".mp4"):
            mp4_candidate = Path(filename).with_suffix(".mp4")
            if mp4_candidate.exists():
                return mp4_candidate, info

        return Path(filename), info

def apply_edits(input_path: Path, *, start=None, end=None, watermark=None, scale=None) -> Path:
    """Apply optional edits to the video."""
    output = EDITED_DIR / f"edited_{input_path.stem}.mp4"

    vf_filters = []
    if scale in ("1080x1920", "720x1280"):
        w, h = scale.split("x")
        vf_filters.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")
        vf_filters.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2")
    if watermark:
        text = watermark.replace(':', r'\:').replace("'", r"\'")
        vf_filters.append(
            f"drawtext=text='{text}':x=w-tw-20:y=h-th-20:fontsize=24:"
            f"box=1:boxborderw=10:boxcolor=black@0.4"
        )

    vf_chain = ",".join(vf_filters) if vf_filters else None

    # Input kwargs for trimming
    input_kwargs = {}
    if start is not None:
        input_kwargs["ss"] = start
    if end is not None and (start is None or end > start):
        input_kwargs["to"] = end

    vin = ffmpeg.input(str(input_path), **input_kwargs)
    ain = ffmpeg.input(str(input_path), **input_kwargs)

    if vf_chain:
        out = ffmpeg.output(
            vin.video, ain.audio, str(output),
            vf=vf_chain, vcodec="libx264", acodec="aac",
            movflags="+faststart", video_bitrate="3000k",
            audio_bitrate="160k", preset="veryfast"
        )
    else:
        out = ffmpeg.output(
            vin.video, ain.audio, str(output),
            vcodec="copy", acodec="copy", movflags="+faststart"
        )

    ffmpeg.run(ffmpeg.overwrite_output(out), capture_stderr=True)
    return output

# ---- Routes ----

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/api/instagram", methods=["POST"])
def api_instagram():
    try:
        data = request.get_json(force=True)
        url = (data.get("url") or "").strip()
        if not url:
            return jsonify({"ok": False, "error": "No URL provided"}), 400

        mode = data.get("mode", "normal")
        start = data.get("start")
        end = data.get("end")
        watermark = data.get("watermark")
        scale = data.get("scale")

        # Get metadata first
        info = extract_metadata_only(url)
        description = (info.get("description") or "").strip()

        # Download
        media_path, _ = download_instagram(url)
        final_path = media_path

        if mode == "edited":
            def to_float(x):
                try:
                    return float(x) if x not in (None, "") else None
                except ValueError:
                    return None

            final_path = apply_edits(
                media_path,
                start=to_float(start),
                end=to_float(end),
                watermark=watermark,
                scale=scale
            )

        # File URL
        if final_path.parent == EDITED_DIR:
            file_url = f"/download/edited/{final_path.name}"
        else:
            file_url = f"/download/{final_path.name}"

        return jsonify({
            "ok": True,
            "file": file_url,
            "filename": final_path.name,
            "description": description,
            "title": info.get("title") or "",
            "uploader": info.get("uploader") or "",
            "duration": info.get("duration") or "",
            "thumbnail": info.get("thumbnail") or ""
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/download/<path:filename>", methods=["GET"])
def download_raw(filename):
    path = DL_DIR / filename
    if not path.exists():
        abort(404)
    return send_from_directory(DL_DIR, filename, as_attachment=True)

@app.route("/download/edited/<path:filename>", methods=["GET"])
def download_edited(filename):
    path = EDITED_DIR / filename
    if not path.exists():
        abort(404)
    return send_from_directory(EDITED_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


