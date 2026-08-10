# clippy-video-clipper

Got a show recording? Turn that into a cropped and captioned clip. This project is MacOS-only currently.

Everything runs on your own machine. The video work is ffmpeg; the transcription
is Whisper running locally, so no footage or audio is uploaded anywhere.

**Clippy** is a local web app that walks the whole job in five steps: pick a
video, choose the clip and mark any sections to drop, set the crop against a
live preview, correct the auto-generated captions, then render. Every step plays
the clip as it currently stands, and you can go back at any point without losing
work. Captions are shown over the video as you edit them.

Underneath are five single-purpose python scripts. Each does one thing and
writes one predictable file, so they chain together and are useful on their own:

| script | what it does |
| --- | --- | --- |
| `clip.py` | keep the part between two times |
| `remove.py` | drop the part between two times, join the rest |
| `crop.py` | trim the left and right edges |
| `caption.py` | transcribe and burn in captions |
| `smallify.py` | shrink to under 25 MB for sharing |

Times are always `HH:MM:SS`, optionally to a tenth of a second: `00:10:04.5`.

## Instructions

```bash
brew install ffmpeg
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 clippy.py
```

This serves up an application on http://127.0.0.1:5001
Requires Python 3.9+
