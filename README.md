# motion-capture

Webcam finger-movement matching for veena practice, built on
[MediaPipe](https://developers.google.com/mediapipe) hand tracking and OpenCV.

- **`motion-capture hand-check`**: a live check that your hands and fingers are
  being tracked. It draws skeletons, fingertip trails and a bend bar for every
  finger, and does no scoring. Use it to get the camera framing and lighting
  right.
- **`motion-capture veena`**: a reference video of a veena player next to your
  webcam. It compares the 15 finger-joint angles of each hand frame by frame,
  then scores the match overall, per hand (left = fretting, right = plucking)
  and per finger.

The same two programs also run in the browser: [`website/`](website/) is a
static site, ready for Vercel, with the same logic (checked by shared tests)
and MediaPipe running on the visitor's device. See
[website/README.md](website/README.md).

The original full-body sports script is kept, unchanged, in
[`legacy/`](#legacy-full-body-script).

## Requirements

- **Python 3.9–3.12.** The hand tracker needs mediapipe 0.10.21, which has no
  builds for Python 3.13+. Homebrew's plain `python3` may be 3.14, so name the
  version explicitly (see below).
- A webcam.
- macOS or Linux.

## Install

```bash
cd motion-capture
python3.12 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"      # the app plus test/lint tools; `pip install .` for the app only
motion-capture --version
```

The install downloads about 200–300 MB (mediapipe bundles its models and
native code). If it fails, see [docs/troubleshooting.md](docs/troubleshooting.md).

## Quick start

1. **Check tracking:** run `./check_hands.sh` (the same as
   `motion-capture hand-check`). Wiggle each finger and check that its bar
   follows. Then sit with the veena and adjust the camera until both hands
   show as tracked in more than 80% of frames.
2. **Add a reference clip:** put a video of the teacher playing in
   `data/references/` (videos are not committed to git).
3. **Play along:** run `./start.sh data/references/teacher.mp4` (the same as
   `motion-capture veena --reference data/references/teacher.mp4`). If you
   name the clip `veena_reference.mp4`, plain `./start.sh` finds it.
   Show a thumbs up (or press SPACE), put your hand back on the veena during
   the 3-second countdown, play, then press ESC to see your score.

The two scripts work from any folder and don't need the venv activated. Any
extra options are passed on, e.g. `./check_hands.sh --camera 1` or
`./start.sh teacher.mp4 --threshold 25`.

## Commands

Both commands accept:

| Option | Meaning |
|---|---|
| `--camera N` | Webcam number (default 0). On a Mac, a nearby iPhone can take number 0, see [troubleshooting](docs/troubleshooting.md#the-iphone-camera-opens-instead-of-the-macs) |
| `--video PATH` | Use a recorded video of **your** hands instead of the webcam |
| `--resolution WxH` | Webcam resolution to ask for (default 1280x720) |
| `--config PATH` | Settings file (default: `./motion-capture.toml` if it exists) |
| `-v`, `--verbose` | Show detailed logs, including MediaPipe's own |

`motion-capture hand-check` also accepts:

| Option | Meaning |
|---|---|
| `--trail-length N` | Frames of fingertip trail to draw (default 10) |
| `--max-bend DEG` | Bend that fills a bar (default 120) |

`motion-capture veena` also accepts:

| Option | Meaning |
|---|---|
| `--reference PATH` | The reference clip |
| `--threshold DEG` | Average finger-joint error that scores 0% (default 20); below it a hand turns green |
| `--countdown SEC` | Seconds between the start gesture and scoring (default 3) |
| `--start-frames N` | Frames in a row the thumbs up must be seen (default 3) |
| `--reference-mirrored` | The reference is already a mirrored (selfie) recording |

The score is printed in the terminal and shown on the final screen. It isn't
saved to a file.

Examples:

```bash
motion-capture hand-check --camera 1
motion-capture hand-check --video data/references/teacher.mp4     # does the reference track well?
motion-capture veena --reference data/references/teacher.mp4 --threshold 25
motion-capture veena --reference data/references/teacher.mp4 \
    --video my-practice.mp4                                       # score a recording
python -m motion_capture veena ...                                # same as motion-capture
```

**How the score works:** a hand's error is the average difference, in degrees,
between your joint angles and the reference's. It is converted to a score with
`100 × (1 − error / threshold)`, so with the default 20° threshold an error of
5° scores 75%, 10° scores 50%, and 20° or more scores 0%.

Exit status: `0` success, `1` error (e.g. missing file or camera; printed as
`error: ...`), `2` invalid usage, `130` interrupted with Ctrl+C.

## Settings file

To keep your own defaults (say, always camera 1), copy the example file and
edit it:

```bash
cp motion-capture.example.toml motion-capture.toml
```

[`motion-capture.example.toml`](motion-capture.example.toml) lists every
setting with an explanation. Later sources override earlier ones:
**built-in defaults → settings file → command-line flags**. Unknown keys and
wrong types are reported as errors. `motion-capture.toml` is gitignored, since
it's personal.

## Project layout

```
src/motion_capture/
  cli/        the motion-capture command
  apps/       the programs: hand_check, veena_match
  config/     settings and loading them from TOML / flags
  geometry/   landmark numbering, joint-angle maths
  tracking/   the MediaPipe adapter (the only code that imports mediapipe)
  video/      cameras, video files, frame helpers
  gestures/   thumbs-up start gesture
  scoring/    comparing hands, the final report
  session/    waiting -> countdown -> running
  rendering/  drawing, panels, the window
tests/        unit/ (fast, no camera) and integration/ (runs MediaPipe on sample clips)
website/      the browser version (TypeScript, same folder layout as src/motion_capture/)
docs/         architecture.md, troubleshooting.md
legacy/       the original full-body script
```

[docs/architecture.md](docs/architecture.md) explains how the pieces fit
together and where to make common changes.

## Development

```bash
pip install -e ".[dev]"
pre-commit install            # run lint, format and type checks on every commit
                              # (activate the venv first: the mypy hook uses it)

pytest                        # everything (~15 s)
pytest -m "not integration"   # fast unit tests only
ruff check . && ruff format --check . && mypy
```

The integration tests download two of MediaPipe's public sample images once
(into `.cache/test-assets/`) and build short lossless clips from them. They
check that the programs still produce the numbers in
[`tests/golden/golden.json`](tests/golden/golden.json), which were captured
from the original scripts before the restructure. If you change how scoring
works on purpose, regenerate that file and explain why in the commit.

**Keeping the website in step:** the website re-implements the logic in
TypeScript. `python -m tests.parity_cases` writes shared test cases (inputs
plus the Python outputs) to `website/tests/fixtures/parity-cases.json`, and
the website's tests must reproduce them. If you change the logic on purpose,
regenerate the file and update the website to match.
`tests/unit/test_parity_cases.py` fails if the file is out of date.

CI (GitHub Actions, [`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs
these checks on Ubuntu and macOS with Python 3.9 and 3.12. It also checks,
tests and builds the website, and runs it in Chromium with a fake webcam.

## Known limitations

- Only **hand shape** is compared. Where your fretting hand is on the neck
  (which note) isn't checked, because that would need the instrument tracked
  too.
- The 3D points are MediaPipe's **estimates** from a single camera, not
  measurements. Fingers hidden behind the strings or neck are guessed.
- Joint angles have a small known bias: a straight joint reads about 177°, not
  180° (see the `xfail` test in `tests/unit/test_angles.py`). It affects you and
  the reference alike, and was kept so the restructure changed no scores.

## Legacy full-body script

`legacy/open_house4.py` is the original sports motion-matching script (body
pose, 10 joint angles, thumbs-up start), kept exactly as it was. It isn't part
of the package and isn't linted or tested. Run it with
`python3 legacy/open_house4.py`; it expects its reference clip
`p10_bvolley_s1.avi` in the `legacy/` folder.
