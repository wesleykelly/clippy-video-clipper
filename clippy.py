#!/usr/bin/env python3
"""Clippy -- a small web front end that chains the clipping tools together.

    python3 clippy.py            then open http://127.0.0.1:5001

Walks you through: pick a video, choose a clip, cut sections out of it, set the
crop against a live preview, then transcribe, correct the captions and render.

Each step shells out to the existing scripts (clip.py, remove.py, crop.py,
caption.py) rather than reimplementing them, so there is one implementation of
each operation and it is the one you already tested from the terminal. The
scripts write fixed filenames into the current directory, which is exactly what
we want here: each job runs in its own directory, so those fixed names never
collide between jobs.
"""
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOBS_DIR = HERE / "jobs"
VIDEO_SUFFIXES = {".mov", ".mp4", ".m4v"}


def ensure_flask():
    """Re-exec inside .venv if flask isn't importable here."""
    try:
        import flask  # noqa: F401
        return
    except ImportError:
        pass
    venv_python = HERE / ".venv" / "bin" / "python3"
    # Env-var guard rather than comparing interpreter paths: .venv/bin/python3
    # is a symlink back to the base interpreter, so a resolved-path comparison
    # reports them identical and the re-exec never fires.
    if venv_python.exists() and not os.environ.get("_CLIPPY_REEXEC"):
        os.environ["_CLIPPY_REEXEC"] = "1"
        os.execv(str(venv_python), [str(venv_python), *sys.argv])
    sys.exit("error: flask is not installed. Run:\n"
             "  .venv/bin/pip install flask")


ensure_flask()

from flask import Flask, Response, jsonify, request, send_file  # noqa: E402

app = Flask(__name__)
jobs = {}
jobs_lock = threading.Lock()


# --------------------------------------------------------------------------
# helpers


def timecode(seconds):
    """Seconds to the HH:MM:SS.s the command line tools accept."""
    seconds = max(0.0, float(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:04.1f}"


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        stdout=subprocess.PIPE, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def run_tool(script, args, cwd):
    """Run one of the sibling scripts, raising with its message if it fails."""
    proc = subprocess.run(
        [sys.executable, str(HERE / script), *args],
        cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{script}: {proc.stdout.strip() or 'failed'}")
    return proc.stdout


def job_folder(source: Path) -> Path:
    """A readable folder name: "10:43am 08.11.26 show.mov".

    This is only ever a folder name. The job id stays a plain hex string,
    because it also appears in URLs, where spaces and colons would have to be
    escaped at every use.
    """
    now = datetime.now()
    stamp = now.strftime("%I:%M%p").lstrip("0").lower()   # 10:43am
    base = f"{stamp} {now.strftime('%m.%d.%y')} {source.name}"
    name, n = base, 2
    while (JOBS_DIR / name).exists():   # same minute, same source
        name = f"{base} ({n})"
        n += 1
    return JOBS_DIR / name


def get_job(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None:
        raise KeyError(job_id)
    return job


def set_state(job, **fields):
    with jobs_lock:
        job.update(fields)


def background(job, step, fn):
    """Run fn on a thread, recording progress and any error on the job."""
    def target():
        try:
            fn()
            set_state(job, state="done", step=step, error=None)
        except Exception as exc:  # surfaced to the browser as-is
            set_state(job, state="error", step=step, error=str(exc))

    set_state(job, state="running", step=step, error=None)
    threading.Thread(target=target, daemon=True).start()


# --------------------------------------------------------------------------
# routes


@app.get("/")
def index():
    return send_file(HERE / "templates" / "index.html")


@app.get("/api/videos")
def list_videos():
    items = []
    for p in sorted(HERE.iterdir()):
        if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES:
            items.append({"name": p.name,
                          "mb": round(p.stat().st_size / 1e6, 1),
                          "duration": round(probe_duration(p), 1)})
    return jsonify(items)


@app.post("/api/jobs")
def create_job():
    name = (request.json or {}).get("source", "")
    source = HERE / name
    if not source.is_file() or source.suffix.lower() not in VIDEO_SUFFIXES:
        return jsonify({"error": f"no such video: {name}"}), 400

    job_id = uuid.uuid4().hex[:12]
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    job_dir = job_folder(source)
    job_dir.mkdir(parents=True, exist_ok=True)
    job = {"id": job_id, "dir": job_dir, "source": source,
           "state": "idle", "step": "created", "error": None,
           "duration": probe_duration(source), "files": {}}
    with jobs_lock:
        jobs[job_id] = job
    return jsonify({"id": job_id, "duration": job["duration"],
                    "name": source.name})


@app.get("/api/jobs/<job_id>")
def job_status(job_id):
    try:
        job = get_job(job_id)
    except KeyError:
        return jsonify({"error": "unknown job"}), 404
    return jsonify({"id": job["id"], "state": job["state"], "step": job["step"],
                    "error": job["error"], "duration": job["duration"],
                    "files": {k: True for k in job["files"]},
                    "clipDuration": job.get("clip_duration")})


@app.post("/api/jobs/<job_id>/clip")
def make_clip(job_id):
    job = get_job(job_id)
    body = request.json or {}
    start, end = float(body["start"]), float(body["end"])
    removals = [(float(a), float(b)) for a, b in body.get("removals", [])]

    def work():
        d = job["dir"]
        # Whole video, nothing removed: use the source where it lies. Skipping
        # this step should cost nothing, and re-encoding it to an identical
        # clip would be the slowest thing in the app.
        if start <= 0 and end >= job["duration"] - 0.05 and not removals:
            job["files"]["clip"] = job["source"]
            set_state(job, clip_duration=job["duration"])
            return

        run_tool("clip.py", [str(job["source"]), timecode(start), timecode(end)], d)
        current = d / "clip.mov"

        # Apply removals last-first. Each cut shortens the video, so working
        # backwards keeps the remaining ranges valid against the timeline the
        # user was looking at when they chose them.
        for a, b in sorted(removals, key=lambda r: r[0], reverse=True):
            run_tool("remove.py", [str(current), timecode(a), timecode(b)], d)
            staged = d / "staged.mov"
            (d / "removed.mov").replace(staged)
            staged.replace(d / "clip.mov")
            current = d / "clip.mov"

        job["files"]["clip"] = current
        set_state(job, clip_duration=probe_duration(current))

    background(job, "clip", work)
    return jsonify({"ok": True})


@app.post("/api/jobs/<job_id>/crop")
def do_crop(job_id):
    job = get_job(job_id)
    body = request.json or {}
    left, right = int(body["left"]), int(body["right"])
    top, bottom = int(body.get("top", 0)), int(body.get("bottom", 100))

    def work():
        d = job["dir"]
        if left == 0 and right == 100 and top == 0 and bottom == 100:
            # Nothing to trim, so skip a needless re-encode.
            job["files"]["cropped"] = job["files"]["clip"]
            return
        run_tool("crop.py", [str(job["files"]["clip"]), str(left), str(right),
                             str(top), str(bottom)], d)
        job["files"]["cropped"] = d / "cropped.mov"

    background(job, "crop", work)
    return jsonify({"ok": True})


@app.post("/api/jobs/<job_id>/transcribe")
def do_transcribe(job_id):
    job = get_job(job_id)

    def work():
        d = job["dir"]
        run_tool("caption.py", [str(job["files"]["cropped"])], d)
        job["files"]["srt"] = d / "captions.srt"

    background(job, "transcribe", work)
    return jsonify({"ok": True})


@app.post("/api/jobs/<job_id>/finish")
def finish_uncaptioned(job_id):
    """Finish without captions: the cropped clip is already the finished clip."""
    job = get_job(job_id)

    def work():
        job["files"]["final"] = job["files"]["cropped"]

    background(job, "render", work)
    return jsonify({"ok": True})


@app.get("/api/jobs/<job_id>/srt")
def read_srt(job_id):
    job = get_job(job_id)
    srt = job["files"].get("srt")
    if not srt or not Path(srt).exists():
        return jsonify({"error": "no captions yet"}), 404
    return Response(Path(srt).read_text(encoding="utf-8"), mimetype="text/plain")


@app.post("/api/jobs/<job_id>/render")
def do_render(job_id):
    job = get_job(job_id)
    text = (request.json or {}).get("srt", "")

    def work():
        d = job["dir"]
        srt = d / "captions.srt"
        srt.write_text(text, encoding="utf-8")
        run_tool("caption.py", [str(job["files"]["cropped"]), "--srt", "captions.srt"], d)
        job["files"]["final"] = d / "captioned.mov"

    background(job, "render", work)
    return jsonify({"ok": True})


@app.get("/media/<job_id>/<kind>")
def media(job_id, kind):
    job = get_job(job_id)
    path = job["source"] if kind == "source" else job["files"].get(kind)
    if not path or not Path(path).exists():
        return jsonify({"error": "not ready"}), 404
    # conditional=True gives byte-range replies, without which the browser
    # cannot seek within a video element.
    return send_file(str(path), conditional=True)


@app.get("/download/<job_id>")
def download(job_id):
    job = get_job(job_id)
    final = job["files"].get("final")
    if not final or not Path(final).exists():
        return jsonify({"error": "not ready"}), 404
    return send_file(str(final), as_attachment=True, download_name="clippy.mov")


if __name__ == "__main__":
    JOBS_DIR.mkdir(exist_ok=True)
    # 5000 is the obvious default but macOS runs AirPlay Receiver there, so it
    # is usually already taken. 5001 by default, overridable with PORT.
    port = int(os.environ.get("PORT", 5001))
    print(f"Clippy running at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, threaded=True)
