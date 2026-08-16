#!/usr/bin/env python3
"""Crop the edges off a video, into cropped.mov.

    python3 crop.py show.mov 25 75
    python3 crop.py show.mov 25 75 10 90

LEFT and RIGHT are percentages of the full width marking the edges of the part
you keep; TOP and BOTTOM do the same down the height, and default to the whole
frame if you leave them off:

    0 100         keeps everything
    25 75         drops the leftmost 25% and the rightmost 25%
    0 50          keeps the left half
    25 75 10 90   also drops the top 10% and the bottom 10%

Needs ffmpeg on PATH.
"""
import argparse
import math
import re
import subprocess
import sys


def percent(value):
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number")
    if not 0 <= n <= 100:
        raise argparse.ArgumentTypeError(f"{n} is not between 0 and 100")
    return n


ap = argparse.ArgumentParser(description="Crop the edges off a video into cropped.mov.")
ap.add_argument("video")
ap.add_argument("left", type=percent, help="left edge of the kept region, 0-100")
ap.add_argument("right", type=percent, help="right edge of the kept region, 0-100")
ap.add_argument("top", nargs="?", default=0, type=percent,
                help="top edge of the kept region, 0-100 (default 0)")
ap.add_argument("bottom", nargs="?", default=100, type=percent,
                help="bottom edge of the kept region, 0-100 (default 100)")
args = ap.parse_args()

if args.right <= args.left:
    sys.exit(f"error: right ({args.right}) must be greater than left ({args.left})")
if args.bottom <= args.top:
    sys.exit(f"error: bottom ({args.bottom}) must be greater than top ({args.top})")

# Expressed against ffmpeg's own iw/ih, so no probing is needed. The crop filter
# rounds the result to chroma-aligned dimensions on its own, which keeps h264
# happy when a percentage lands on an odd pixel.
keep_w = args.right - args.left
keep_h = args.bottom - args.top
crop = (f"crop=iw*{keep_w}/100:ih*{keep_h}/100"
        f":iw*{args.left}/100:ih*{args.top}/100")

result = subprocess.run([
    "ffmpeg", "-v", "error", "-y", "-i", args.video, "-vf", crop,
    "-c:v", "h264_videotoolbox", "-b:v", "12M", "-c:a", "aac", "-b:a", "192k",
    "cropped.mov",
])
if result.returncode != 0:
    sys.exit(result.returncode)

# Read the size back off the finished file rather than predicting it: the crop
# filter rounds to chroma-aligned dimensions, so a percentage landing on an odd
# pixel comes out a pixel off from the obvious arithmetic.
size = subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0",
     "-show_entries", "stream=width,height", "-of", "csv=p=0", "cropped.mov"],
    stdout=subprocess.PIPE, text=True).stdout.strip()

# Pull the numbers out rather than trusting the field count. Streams that carry
# side data -- phone recordings often tag an "Ambient viewing environment" --
# make ffprobe emit an extra empty CSV column, so the reply reads "1920,1080,".
# Splitting on commas then yields a third, empty field, and unpacking that into
# two names raises a confusing int('') error before it can report the mismatch.
numbers = [int(n) for n in re.findall(r"\d+", size)]
if len(numbers) < 2:
    sys.exit(f"error: could not read the size of cropped.mov (ffprobe said {size!r})")
w, h = numbers[0], numbers[1]
g = math.gcd(w, h)
print(f"wrote cropped.mov (kept {args.left}%-{args.right}% across, "
      f"{args.top}%-{args.bottom}% down)")
print(f"  {w}x{h}  aspect {w // g}:{h // g}  ({w / h:.3f}:1)")
