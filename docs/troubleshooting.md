# Troubleshooting

## Installing

### `No matching distribution found for mediapipe<=0.10.21,>=0.10.14`

Your virtual environment uses Python 3.13 or newer, and mediapipe 0.10.21 only
has builds for Python 3.9–3.12. Recreate the environment with a supported
version:

```bash
deactivate 2>/dev/null; rm -rf venv
python3.12 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

On macOS with Homebrew, `brew install python@3.12` provides `python3.12`.

### `module 'mediapipe' has no attribute 'solutions'`

mediapipe 0.10.30 or newer is installed. Those versions (and all of 1.x)
removed the `mp.solutions` API that the hand tracker uses, which is why
`pyproject.toml` pins `mediapipe<=0.10.21`. Reinstall with
`pip install -e .` to get the pinned version. There is no release between
0.10.21 and 0.10.30.

### Two OpenCV packages

Only `opencv-contrib-python` should be installed. mediapipe 0.10.x depends on
it, and installing `opencv-python` as well makes the two fight over `cv2`.
Check with `pip list | grep -i opencv`.

## Camera

### The iPhone camera opens instead of the Mac's

That's macOS **Continuity Camera**: a nearby iPhone signed in to the same
Apple ID shows up as a webcam and can take number 0.

- **Permanent fix:** on the iPhone, go to Settings → General → AirPlay &
  Continuity (called *AirPlay & Handoff* on older iOS) and turn off
  **Continuity Camera**.
- **For one session:** lock the iPhone or move it away from the Mac.
- **Or pick a number:** `--camera 1`, or `index = 1` under `[camera]` in
  `motion-capture.toml`. The numbering changes when the iPhone appears, and
  without it number 1 may be the Mac's *Desk View* camera (a top-down view).

### `error: Cannot open webcam (device N)`

- Try another number: `--camera 1`.
- On macOS, the app you run it from (Terminal, iTerm, VS Code) needs camera
  permission: System Settings → Privacy & Security → Camera.
- Close other apps that are using the camera.

## Tracking

### "No hands visible", or a low "tracked in ...%" in hand-check

- Move the camera closer. Frame just the instrument, from the neck to the
  bridge, so the hands are big in the picture.
- Add light on your hands, and avoid a bright window behind you.
- A higher resolution can help small hands: `--resolution 1920x1080`. It
  costs some frames per second.
- The veena's neck and strings hide parts of the fretting hand, so some
  dropped frames are normal. Raising the camera a little often helps.

### "No finger comparison recorded"

The session never started, or no hand was found in both videos at the same
time.

- Start with a thumbs up held for a moment, or press SPACE while the window
  has focus.
- Check the reference clip itself:
  `motion-capture hand-check --video data/references/teacher.mp4`.

### Left and right are swapped on the reference

If the reference was recorded as a mirrored selfie video, pass
`--reference-mirrored`, or set `reference_is_mirrored = true` under `[veena]`.

## Output

### MediaPipe's `INFO` / `W0000` lines in the terminal

These are hidden when you run the command in a terminal, and shown with
`--verbose`. When stderr is redirected (to a file or CI logs) they're left
alone. They're harmless start-up messages.

### The window is too big or too small

It's resizable with the mouse. For `veena`, the starting width is capped by
`max_window_width` under `[veena]` in the settings file.

## Tests

### Integration tests are skipped

They need to download two sample images once (into `.cache/test-assets/`).
When offline they're skipped. Run them again once you're connected, or point
`MOTION_CAPTURE_TEST_ASSETS` at a folder that already holds the images.
