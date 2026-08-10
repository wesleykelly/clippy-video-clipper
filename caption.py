#!/usr/bin/env python3
"""Add captions to a video, into captioned.mov.

    python3 caption.py show.mov                 transcribe, then caption
    python3 caption.py show.mov --srt mine.srt  caption using your own subtitles

Speech is transcribed locally with Whisper -- nothing is uploaded. The captions
are burned into the picture and also written alongside as captions.srt, so you
have an editable copy.

Needs ffmpeg on PATH. Transcription additionally needs faster-whisper, which
lives in .venv here; this script re-runs itself with that interpreter when it
needs to, so plain `python3 caption.py` is always the right way to start it.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

OUTPUT = "captioned.mov"
SRT_OUT = "captions.srt"
MODEL = "base"


def ensure_whisper():
    """Re-exec inside .venv if faster-whisper isn't importable here."""
    try:
        import faster_whisper  # noqa: F401
        return
    except ImportError:
        pass
    venv_python = Path(__file__).resolve().parent / ".venv" / "bin" / "python3"
    # Guard the re-exec with an env var rather than by comparing interpreter
    # paths: .venv/bin/python3 is a symlink back to the base interpreter, so a
    # resolved-path comparison reports the two as identical and the re-exec
    # never fires.
    if venv_python.exists() and not os.environ.get("_CAPTION_REEXEC"):
        os.environ["_CAPTION_REEXEC"] = "1"
        os.execv(str(venv_python), [str(venv_python), *sys.argv])
    sys.exit("error: faster-whisper is not installed. Run:\n"
             "  python3 -m venv .venv && .venv/bin/pip install faster-whisper\n"
             "or pass an existing subtitle file with --srt.")


def srt_time(seconds):
    """SRT wants HH:MM:SS,mmm -- comma before the milliseconds, not a dot."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe(video):
    ensure_whisper()
    from faster_whisper import WhisperModel

    print(f"transcribing with Whisper ({MODEL})... this takes a few minutes")
    model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(video, vad_filter=True, language="en")

    lines, count = [], 0
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        count += 1
        lines.append(f"{count}\n{srt_time(seg.start)} --> {srt_time(seg.end)}\n{text}\n")
        print(f"\r  {count} captions ({seg.end:.0f}s)", end="", flush=True)
    print()
    if not count:
        sys.exit("error: no speech found in the audio")
    Path(SRT_OUT).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {SRT_OUT} ({count} captions)")
    return SRT_OUT


ap = argparse.ArgumentParser(description=f"Burn captions into a video, into {OUTPUT}.")
ap.add_argument("video")
ap.add_argument("--srt", help="use this subtitle file instead of transcribing")
args = ap.parse_args()

if not Path(args.video).exists():
    sys.exit(f"error: no such file: {args.video}")

if args.srt:
    if not Path(args.srt).exists():
        sys.exit(f"error: no such file: {args.srt}")
    srt_path = args.srt
else:
    srt_path = transcribe(args.video)

# The filter argument is escaped because ffmpeg parses ':' and ',' as its own
# separators, so a path containing either would otherwise split the filter.
escaped = srt_path.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
style = "FontSize=18,Outline=2,Shadow=1,MarginV=30"
result = subprocess.run([
    "ffmpeg", "-v", "error", "-y", "-i", args.video,
    "-vf", f"subtitles='{escaped}':force_style='{style}'",
    "-c:v", "h264_videotoolbox", "-b:v", "12M", "-c:a", "aac", "-b:a", "192k",
    OUTPUT,
])
if result.returncode != 0:
    sys.exit(result.returncode)
print(f"wrote {OUTPUT} (captions burned in; editable copy in {srt_path})")
