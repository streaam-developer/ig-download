import os
import re
import uuid
import traceback
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory, abort
import yt_dlp
import time
import random

# --- ffmpeg-python check ---
try:
    import ffmpeg  # Must be ffmpeg-python
    if not hasattr(ffmpeg, "input"):
        raise ImportError("Wrong ffmpeg package installed")
except ImportError as e:
    raise ImportError(
        "You have the wrong ffmpeg package. Run:\n"
        "  pip uninstall -y ffmpeg\n"
        "  pip install ffmpeg-python\n"
        "Also make sure system ffmpeg is installed:\n"
        "  apt install -y ffmpeg"
    )

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DL_DIR = BASE_DIR / "downloads"
EDITED_DIR = DL_DIR / "edited"
DL_DIR.mkdir(parents=True, exist_ok=True)
EDITED_DIR.mkdir(parents=True, exist_ok=True)

COOKIES_FILE = BASE_DIR / "cookies.txt"

# ---- Helpers ----

def sanitize_filename(name: str) -> str:
    """Sanitize filenames for safe saving."""
    name = re.sub(r"[^\w\-. ]+", "_", name)
    return name.strip()[:120] or f"ig_{uuid.uuid4().hex[:8]}"

def ydl_opts_for_instagram(output_path: Path):
    """Base yt-dlp options for Instagram."""
    opts = {
        "outtmpl": str(output_path / "%(title)s_%(id)s.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "concurrent_fragment_downloads": 8,
        "retries": 15,
        "fragment_retries": 15,
        "http_chunk_size": 10485760,
        "quiet": False,
        "no_warnings": False,
        "ignoreerrors": False,
        "geo_bypass": True,
        "skip_download": False,
        "writethumbnail": False,
        "nocheckcertificate": True,
        "overwrites": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            ),
        },
    }

    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    else:
        print(f"[WARNING] Cookies file not found: {COOKIES_FILE}")

    return opts

def extract_metadata_only(url: str):
    """Extract metadata only."""
    opts = ydl_opts_for_instagram(DL_DIR)
    opts["skip_download"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)

def download_instagram(url: str):
    """Download Instagram media."""
    time.sleep(random.uniform(1.0, 2.5))
    opts = ydl_opts_for_instagram(DL_DIR)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

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
        vf_filters.append(
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
        )
    if watermark:
        text = (
            watermark.replace("\\", "\\\\")
            .replace(":", r"\:")
            .replace("'", r"\'")
            .replace('"', r"\"")
        )
        vf_filters.append(
            f"drawtext=text='{text}':x=(w-tw)/2:y=h-th-40:fontsize=24:"
            f"box=1:boxborderw=10:boxcolor=black@0.4:fontcolor=white"
        )

    vf_chain = ",".join(vf_filters) if vf_filters else None

    input_kwargs = {}
    if start is not None:
        input_kwargs["ss"] = start
    if end is not None and (start is None or end > start):
        input_kwargs["to"] = end

    vin = ffmpeg.input(str(input_path), **input_kwargs)

    if vf_chain:
        out = ffmpeg.output(
            vin, str(output),
            vf=vf_chain,
            vcodec="libx264",
            preset="veryfast",
            tune="fastdecode",
            crf=18,
            acodec="aac",
            audio_bitrate="160k",
            movflags="+faststart"
        )
    else:
        out = ffmpeg.output(
            vin, str(output),
            vcodec="copy", acodec="copy",
            movflags="+faststart"
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

        info = extract_metadata_only(url)
        description = (info.get("description") or "").strip()
        thumb = info.get("thumbnail")
        if isinstance(thumb, list):
            thumb = thumb[0] if thumb else ""

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

        file_url = (
            f"/download/edited/{final_path.name}"
            if final_path.parent == EDITED_DIR
            else f"/download/{final_path.name}"
        )

        return jsonify({
            "ok": True,
            "file": file_url,
            "filename": final_path.name,
            "description": description,
            "title": info.get("title") or "",
            "uploader": info.get("uploader") or "",
            "duration": info.get("duration") or "",
            "thumbnail": thumb
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
    app.run(host="0.0.0.0", port=4567, debug=True)
