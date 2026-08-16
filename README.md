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
| --- | --- |
| `clip.py` | keep the part between two times |
| `remove.py` | drop the part between two times, join the rest |
| `crop.py` | trim the left and right edges |
| `caption.py` | transcribe and burn in captions |
| `smallify.py` | shrink to under 25 MB for sharing |

Times are always `HH:MM:SS`, optionally to a tenth of a second: `00:10:04.5`.

## Instructions

Requires Python 3.9+.

```bash
brew install ffmpeg ffmpeg@7
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 clippy.py
```

This serves up an application on http://127.0.0.1:5001

### Starting it without the terminal

Double-click **`Start Clippy.command`** in Finder. It starts the server and
opens your browser once it's ready; close the Terminal window it opens (or press
Ctrl+C there) to stop it. Clicking it again while it's already running just
reopens the browser rather than failing on the busy port.

For quicker access, right-click it → *Make Alias* and drag the alias to your
Desktop or the right-hand side of the Dock.

If it opens in a text editor instead of running, it has lost its executable bit:

```bash
chmod +x "Start Clippy.command"
```

You don't need to activate the virtualenv — `clippy.py` and `caption.py` re-run
themselves with it. The Whisper model (~145 MB) downloads itself the first time
you transcribe something.

### Why two ffmpegs?

Burning captions into the picture needs the `subtitles` filter, which is only
built when ffmpeg is compiled against **libass**. Homebrew's current `ffmpeg`
(8.x) is not, so on its own it cannot draw captions at all — and it reports this
as a confusing `No option name near ...` parse error rather than saying the
filter is missing. `ffmpeg@7` is still built with libass and installs pre-built
in seconds, so it is used only for that one step.

`caption.py` finds a suitable ffmpeg by itself and prefers whatever is on your
PATH, so if you already have an ffmpeg with libass you can skip `ffmpeg@7`. To
check what you have:

```bash
ffmpeg -filters | grep subtitles
```

Nothing printed means that build can't burn in captions.

On Linux the stock distro ffmpeg includes libass, so `sudo apt install ffmpeg`
covers everything — though the other scripts are macOS-only for now (see below).

### macOS only, for now

Every script except `smallify.py` encodes with `h264_videotoolbox`, Apple's
hardware encoder. On Linux or Windows they fail with "Unknown encoder" until
that is swapped for `libx264`.
