#!/usr/bin/env bash
# Veena practice: the reference video next to your webcam, scored.
#
# Usage (from any folder):
#   ./start.sh                          use the default reference video
#   ./start.sh path/to/teacher.mp4      use this reference video
#   ./start.sh teacher.mp4 --camera 1   extra options are passed on to the app
#   ./start.sh --help                   list every option
#
# The default reference video is data/references/veena_reference.mp4, or the
# one set under [veena] in motion-capture.toml if you have made that file.
#
# In the window: show a thumbs up (or press SPACE) to start, ESC to stop and
# see your score.

# Stop at the first command that fails (-e), treat a misspelt variable name as
# an error (-u), and count a pipeline as failed if any part of it fails.
set -euo pipefail

# The project folder is the folder this script is in, wherever it's run from.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The motion-capture command, installed inside the project's venv.
APP="$PROJECT_DIR/venv/bin/motion-capture"
# Your personal settings (optional; copy motion-capture.example.toml to make it).
SETTINGS_FILE="$PROJECT_DIR/motion-capture.toml"
DEFAULT_REFERENCE="$PROJECT_DIR/data/references/veena_reference.mp4"

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

# "$@" is the list of arguments you typed. Below, `set -- X "$@"` puts X in
# front of them. When an option is given twice the app uses the last one, so
# anything you type yourself always wins.

if [ $# -gt 0 ] && [[ "$1" != -* ]]; then
  # The first argument isn't an option (it doesn't start with "-"), so it's the
  # reference video: ./start.sh teacher.mp4
  reference="$1"
  shift
  set -- --reference "$reference" "$@"
elif [ ! -f "$SETTINGS_FILE" ]; then
  # No video named and no settings file: use the default reference video.
  if [ $# -eq 0 ] && [ ! -f "$DEFAULT_REFERENCE" ]; then
    {
      echo "No reference video given, and the default one isn't there:"
      echo "  data/references/veena_reference.mp4"
      echo
      echo "Put the teacher's video at that path, or name it:"
      echo "  ./start.sh path/to/teacher.mp4"
      echo
      echo "Videos in data/references/:"
      found=0
      for file in "$PROJECT_DIR"/data/references/*; do
        if [ -f "$file" ]; then
          echo "  data/references/$(basename "$file")"
          found=1
        fi
      done
      if [ "$found" -eq 0 ]; then
        echo "  (none yet)"
      fi
    } >&2
    exit 1
  fi
  set -- --reference "$DEFAULT_REFERENCE" "$@"
fi

# Use the project's settings file even when the script is run from another folder.
if [ -f "$SETTINGS_FILE" ]; then
  set -- --config "$SETTINGS_FILE" "$@"
fi

# `exec` hands this terminal over to the app, so Ctrl+C and the exit status
# go straight to it.
exec "$APP" veena "$@"
