#!/usr/bin/env python3
"""Crop the sides off a video, into cropped.mov.

    python3 crop.py show.mov 25 75

LEFT and RIGHT are percentages of the full width marking the edges of the part
you keep, so the video is trimmed to the region between them:

    0 100   keeps everything
    25 75   drops the leftmost 25% and the rightmost 25%, keeping the middle 50%
    0 50    keeps the left half

Needs ffmpeg on PATH.
"""
import argparse
import math
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


ap = argparse.ArgumentParser(description="Crop the sides off a video into cropped.mov.")
ap.add_argument("video")
ap.add_argument("left", type=percent, help="left edge of the kept region, 0-100")
ap.add_argument("right", type=percent, help="right edge of the kept region, 0-100")
args = ap.parse_args()

if args.right <= args.left:
    sys.exit(f"error: right ({args.right}) must be greater than left ({args.left})")

# Expressed against ffmpeg's own iw, so no probing is needed. The crop filter
# rounds the result to a chroma-aligned width on its own, which keeps h264
# happy when a percentage lands on an odd pixel.
keep = args.right - args.left
crop = f"crop=iw*{keep}/100:ih:iw*{args.left}/100:0"

result = subprocess.run([
    "ffmpeg", "-v", "error", "-y", "-i", args.video, "-vf", crop,
    "-c:v", "h264_videotoolbox", "-b:v", "12M", "-c:a", "aac", "-b:a", "192k",
    "cropped.mov",
])
if result.returncode != 0:
    sys.exit(result.returncode)

# Read the size back off the finished file rather than predicting it: the crop
# filter rounds to a chroma-aligned width, so a percentage landing on an odd
# pixel comes out a pixel off from the obvious arithmetic.
size = subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0",
     "-show_entries", "stream=width,height", "-of", "csv=p=0", "cropped.mov"],
    stdout=subprocess.PIPE, text=True).stdout.strip()
w, h = (int(n) for n in size.split(","))
g = math.gcd(w, h)
print(f"wrote cropped.mov (kept {args.left}%-{args.right}%, {keep}% of the width)")
print(f"  {w}x{h}  aspect {w // g}:{h // g}  ({w / h:.3f}:1)")
