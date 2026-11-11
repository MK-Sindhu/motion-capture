#!/usr/bin/env bash
# Check that hand and finger tracking works: webcam only, no reference video,
# no score. Use it to get the camera position and lighting right.
#
# Usage (from any folder):
#   ./check_hands.sh                    use the webcam
#   ./check_hands.sh --camera 1         use another camera (e.g. if your iPhone's opens)
#   ./check_hands.sh --video clip.mp4   check a recorded video instead of the webcam
#   ./check_hands.sh --help             list every option
#
# Wiggle each finger and watch its bar move. Press ESC to stop; the terminal
# then shows how often each hand was found (aim for more than 80%).

# Stop at the first command that fails (-e), treat a misspelt variable name as
# an error (-u), and count a pipeline as failed if any part of it fails.
set -euo pipefail

# The project folder is the folder this script is in, wherever it's run from.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The motion-capture command, installed inside the project's venv.
APP="$PROJECT_DIR/venv/bin/motion-capture"
# Your personal settings (optional; copy motion-capture.example.toml to make it).
SETTINGS_FILE="$PROJECT_DIR/motion-capture.toml"

if [ ! -x "$APP" ]; then
  cat >&2 <<EOF
motion-capture isn't installed yet. Set it up once (it needs Python 3.12):

  cd "$PROJECT_DIR"
  python3.12 -m venv venv
  source venv/bin/activate
  pip install -e .
EOF
  exit 1
fi

# Use the project's settings file even when the script is run from another
# folder. `set -- X "$@"` puts X in front of the arguments you typed; yours
# come last, so they win if you give the same option yourself.
if [ -f "$SETTINGS_FILE" ]; then
  set -- --config "$SETTINGS_FILE" "$@"
fi

# `exec` hands this terminal over to the app, so Ctrl+C and the exit status
# go straight to it.
exec "$APP" hand-check "$@"
