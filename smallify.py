#!/usr/bin/env python3
"""Shrink a video to under 25 MB, into smallified.mp4.

    python3 smallify.py clip.mov

The bitrate is worked out from the clip's length so the result lands under the
limit, and the picture is scaled down when the length demands a bitrate too low
to look reasonable at full size. Output is .mp4/H.264 because it plays anywhere.

Needs ffmpeg on PATH.
"""
import os
import subprocess
import sys
from pathlib import Path

LIMIT_MB = 25
OUTPUT = "smallified.mp4"
PASSLOG = ".smallify-passlog"

if len(sys.argv) != 2:
    sys.exit("usage: python3 smallify.py VIDEO")
video = sys.argv[1]
if not Path(video).exists():
    sys.exit(f"error: no such file: {video}")

duration = float(subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "csv=p=0", video],
    stdout=subprocess.PIPE, text=True, check=True).stdout.strip())
if duration <= 0:
    sys.exit("error: could not read the video's duration")

original_mb = Path(video).stat().st_size / 1e6
if original_mb < LIMIT_MB:
    print(f"{video} is already {original_mb:.1f} MB, under the {LIMIT_MB} MB limit")

# 0.93 leaves room for container overhead, which the bitrate maths ignores.
budget_kbit = LIMIT_MB * 8000 * 0.93
total_kbps = budget_kbit / duration
audio_kbps = 96 if total_kbps > 500 else 64
video_kbps = max(80, int(total_kbps - audio_kbps))

# Below roughly 2.5 Mbps a 1080p frame falls apart; spending those bits on a
# smaller frame looks far better than smearing them across a big one.
for threshold, height in ((2500, 1080), (1200, 720), (600, 540), (0, 360)):
    if video_kbps >= threshold:
        target_height = height
        break

print(f"{duration:.0f}s -> {video_kbps} kbps video + {audio_kbps} kbps audio, "
      f"{target_height}p")

for attempt in range(1, 4):
    common = ["-c:v", "libx264", "-preset", "medium", "-b:v", f"{video_kbps}k",
              "-vf", f"scale=-2:{target_height}", "-passlogfile", PASSLOG]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, *common,
                    "-pass", "1", "-an", "-f", "null", os.devnull], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, *common,
                    "-pass", "2", "-c:a", "aac", "-b:a", f"{audio_kbps}k",
                    OUTPUT], check=True)

    size_mb = Path(OUTPUT).stat().st_size / 1e6
    if size_mb < LIMIT_MB:
        break
    # Overshot: scale the bitrate back by however much we went over and retry.
    video_kbps = int(video_kbps * (LIMIT_MB / size_mb) * 0.95)
    print(f"  came out {size_mb:.1f} MB, retrying at {video_kbps} kbps")

for leftover in Path(".").glob(f"{PASSLOG}*"):
    leftover.unlink()

if size_mb >= LIMIT_MB:
    sys.exit(f"error: got {OUTPUT} down to {size_mb:.1f} MB but no further; "
             f"the clip is too long to fit {LIMIT_MB} MB at watchable quality. "
             f"Shorten it with clip.py first.")

print(f"wrote {OUTPUT}  {size_mb:.1f} MB "
      f"(was {original_mb:.1f} MB, {original_mb / size_mb:.0f}x smaller)")
