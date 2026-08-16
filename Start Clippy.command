#!/bin/bash
# Double-click this in Finder to start Clippy and open it in your browser.
# Close the Terminal window (or press Ctrl+C) to stop the server.

# A double-clicked script starts in your home folder, so move to the one this
# file lives in.
cd "$(dirname "$0")" || exit 1

PORT="${PORT:-5001}"
URL="http://127.0.0.1:$PORT"

if curl -s -o /dev/null --max-time 2 "$URL"; then
  echo "Clippy is already running — opening it."
  open "$URL"
  exit 0
fi

# Open the browser as soon as the server starts answering, not before.
( until curl -s -o /dev/null --max-time 1 "$URL"; do sleep 0.5; done; open "$URL" ) &

echo "Starting Clippy…"
echo "Close this window or press Ctrl+C to stop it."
echo
exec python3 clippy.py
