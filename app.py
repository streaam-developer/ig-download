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

COOKIES_FILE = "cookies.txt"  # optional

# ---- Helpers ----

def sanitize_filename(name: str) -> str:
    name = re.sub(r"[^\w\-. ]+", "_", name)
    return name.strip()[:120] or f"ig_{uuid.uuid4().hex[:8]}"

def ydl_opts_for_instagram(output_path: Path):
    # Fast + HQ
    opts = {
        "outtmpl": str(output_path / "%(title)s_%(id)s.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "concurrent_fragment_downloads": 4,
        "retries": 10,
        "fragment_retries": 10,
        "http_chunk_size": 10485760,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "geo_bypass": True,
        "skip_download": False,
        "writethumbnail": False,
        "nocheckcertificate": True,
        "overwrites": True,
    }
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    return opts

def extract_metadata_only(url: str):
    opts = ydl_opts_for_instagram(DL_DIR)
    opts["skip_download"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info

def download_instagram(url: str):
    opts = ydl_opts_for_instagram(DL_DIR)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if "requested_downloads" in info and info["requested_downloads"]:
            best = info["requested_downloads"][0]
            fp = best.get("filepath")
            if fp and os.path.exists(fp):
                return Path(fp), info
        filename = ydl.prepare_filename(info)
        if filename and not filename.endswith(".mp4"):
            mp4_candidate = Path(filename).with_suffix(".mp4")
            if mp4_candidate.exists():
                return mp4_candidate, info
        return Path(filename), info

def apply_edits(input_path: Path, *, start=None, end=None, watermark=None, scale=None) -> Path:
    output = EDITED_DIR / f"edited_{input_path.stem}.mp4"

    # Build video filter chain string
    vf_filters = []
    if scale in ("1080x1920", "720x1280"):
        w, h = scale.split("x")
        vf_filters.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")
        vf_filters.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2")
    if watermark:
        text = watermark.replace(':', r'\:').replace("'", r"\'")
        vf_filters.append(
            f"drawtext=text='{text}':x=w-tw-20:y=h-th-20:fontsize=24:box=1:boxborderw=10:boxcolor=black@0.4"
        )
    vf_chain = ",".join(vf_filters) if vf_filters else None

    # Inputs (with optional trim)
    input_kwargs = {}
    if start is not None:
        input_kwargs["ss"] = start
    if end is not None and start is not None and end > start:
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

    out = ffmpeg.overwrite_output(out)
    ffmpeg.run(out, capture_stderr=True)
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

        mode = data.get("mode") or "normal"   # normal or edited
        start = data.get("start")
        end = data.get("end")
        watermark = data.get("watermark")
        scale = data.get("scale")

        # metadata first (exact description)
        info = extract_metadata_only(url)
        description = (info.get("description") or "").strip()

        # download media
        media_path, _ = download_instagram(url)
        final_path = media_path

        if mode == "edited":
            def to_float(x):
                try:
                    if x is None or x == "":
                        return None
                    return float(x)
                except Exception:
                    return None
            s = to_float(start)
            e = to_float(end)
            final_path = apply_edits(media_path, start=s, end=e, watermark=watermark, scale=scale)

        # prepare response
        rel = final_path.name
        if final_path.parent.name == "edited":
            file_url = f"/download/edited/{rel}"
        else:
            file_url = f"/download/{rel}"

        return jsonify({
            "ok": True,
            "file": file_url,
            "filename": rel,
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
    path = (DL_DIR / filename)
    if not path.exists():
        abort(404)
    return send_from_directory(DL_DIR, filename, as_attachment=True)

@app.route("/download/edited/<path:filename>", methods=["GET"])
def download_edited(filename):
    path = (EDITED_DIR / filename)
    if not path.exists():
        abort(404)
    return send_from_directory(EDITED_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

