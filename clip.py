#!/usr/bin/env python3
"""Cut a single clip out of a video, into clip.mov.

    python3 clip.py show.mov 00:10:04.5 00:11:45.5

Times are HH:MM:SS with an optional tenth of a second. Needs ffmpeg on PATH.
"""
import argparse
import re
import subprocess
import sys

TIME_RE = re.compile(r"^(\d{1,2}):([0-5]\d):([0-5]\d(?:\.\d)?)$")


def parse_time(value):
    m = TIME_RE.match(value.strip())
    if not m:
        raise argparse.ArgumentTypeError(
            f"bad time {value!r} -- use HH:MM:SS[.s], for example 00:10:04.5")
    h, m_, s = m.groups()
    return int(h) * 3600 + int(m_) * 60 + float(s)


ap = argparse.ArgumentParser(description="Cut a clip from a video into clip.mov.")
ap.add_argument("video")
ap.add_argument("start", type=parse_time, help="HH:MM:SS[.s]")
ap.add_argument("end", type=parse_time, help="HH:MM:SS[.s]")
args = ap.parse_args()

length = args.end - args.start
if length <= 0:
    sys.exit("error: end must be after start")

result = subprocess.run([
    "ffmpeg", "-v", "error", "-y",
    "-ss", f"{args.start:.1f}", "-i", args.video, "-t", f"{length:.1f}",
    "-c:v", "h264_videotoolbox", "-b:v", "12M", "-c:a", "aac", "-b:a", "192k",
    "clip.mov",
])
if result.returncode != 0:
    sys.exit(result.returncode)
print(f"wrote clip.mov ({length:.1f}s)")
