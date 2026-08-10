#!/usr/bin/env python3
"""Cut a section out of a video, keeping the rest, into removed.mov.

    python3 remove.py show.mov 00:10:04.5 00:11:45.5

Everything between START and END is dropped and the two remaining pieces are
joined. Times are HH:MM:SS with an optional tenth of a second. Needs ffmpeg.
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


ap = argparse.ArgumentParser(description="Remove a section from a video into removed.mov.")
ap.add_argument("video")
ap.add_argument("start", type=parse_time, help="HH:MM:SS[.s]")
ap.add_argument("end", type=parse_time, help="HH:MM:SS[.s]")
args = ap.parse_args()

if args.end <= args.start:
    sys.exit("error: end must be after start")


def show(seconds):
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:04.1f}"


# Check the range actually lies inside the video. Without this the filter
# quietly matches nothing, and the script reports having removed a section
# while handing back a copy of the original.
duration = float(subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "csv=p=0", args.video],
    stdout=subprocess.PIPE, text=True, check=True).stdout.strip())

if args.start >= duration:
    sys.exit(f"error: start {show(args.start)} is past the end of the video "
             f"({show(duration)}), so there is nothing there to remove")
end = min(args.end, duration)
if end < args.end:
    print(f"note: end {show(args.end)} is past the end of the video; "
          f"removing through to {show(duration)}")
if args.start <= 0 and end >= duration:
    sys.exit("error: that range covers the whole video, leaving nothing")

# Dropping frames inside the range and then rebuilding timestamps, rather than
# cutting two pieces and concatenating them. It needs no temporary files and
# behaves correctly when the range runs to the very start or end of the video,
# where a concat would be joining against an empty piece.
between = f"between(t,{args.start:.1f},{end:.1f})"
result = subprocess.run([
    "ffmpeg", "-v", "error", "-y", "-i", args.video,
    "-vf", f"select='not({between})',setpts=N/FRAME_RATE/TB",
    "-af", f"aselect='not({between})',asetpts=N/SR/TB",
    "-c:v", "h264_videotoolbox", "-b:v", "12M", "-c:a", "aac", "-b:a", "192k",
    "removed.mov",
])
if result.returncode != 0:
    sys.exit(result.returncode)
print(f"wrote removed.mov (cut out {end - args.start:.1f}s, "
      f"{show(args.start)} to {show(end)})")
