# Architecture

## Module map

```
                         cli/main.py   (argparse, settings, exit codes, opens everything)
                              │
              ┌───────────────┴───────────────┐
      apps/hand_check.py              apps/veena_match.py      (the frame loops)
              │                               │
   ┌──────────┼──────────┬─────────┬──────────┼───────────┬───────────┐
rendering/  tracking/  video/   gestures/  scoring/    session/    config/
 draw        hands*     sources  thumbs_up  compare     state       settings
 panels      sides      frames              report                  loader
 window      types
 colors           └──────── geometry/ (landmarks, angles) ───────┘

* tracking/hands.py is the only module that imports mediapipe.
```

**Dependency rules**

- `geometry`, `gestures`, `scoring`, `session`, `config`, and
  `tracking/types.py` + `tracking/sides.py` are **pure**: numpy and the
  standard library only. No camera, no window, no MediaPipe. They're
  covered by fast unit tests.
- `video` and `rendering` use OpenCV. `tracking/hands.py` uses MediaPipe and
  converts its results into numpy `Detection` / `Hand` objects straight away.
- `apps` depend on the interfaces `FrameSource`, `HandTracking` and `Window`,
  not on concrete classes. That's what lets the integration tests run them
  headless: they pass a video file, real trackers and a `HeadlessWindow` that
  replays scripted key presses.
- Only `cli` creates real resources (camera, files, trackers, window). It holds
  them in an `ExitStack`, so they're released even on errors or Ctrl+C.

## One frame of `motion-capture veena`

```
camera.read() ──► mirror ──► user tracker ──► {Left: Hand, Right: Hand} ─┐
                                                                          ├─► finger_errors() per side
reference.read() ─► mirror ─► reference tracker ─► {Left, Right} ─────────┘        │
   (held still during the countdown)                                         ScoreAccumulator
                                                                                    │
draw skeletons + labels (green < threshold, else red) ◄────────────────────────────┘
np.hstack([reference, you]) ──► window.show() ──► window.poll_key()  (ESC ends, SPACE starts)
```

Within each frame the steps run in the same order as in the original script,
which is why the restructured code reproduces its numbers exactly:

1. Read the webcam frame, then the reference frame (or the held first frame
   during the countdown).
2. Mirror both, track the reference at its own size, track the user, then
   resize the reference.
3. Update the start gesture or the countdown. Then, if running, compare and
   accumulate.
4. Draw, show, and read the keyboard.

## Design decisions

| Decision | Why |
|---|---|
| Angles from MediaPipe's 3D **world** landmarks | A finger bending toward the camera barely moves on the flat image; in 3D it still changes angle. A curled finger reads ~90° in 3D, but 1–22° from screen positions. |
| **Both** streams are mirrored before tracking | Tracking one mirrored and one not shows the model a left hand and a mirror-image "right" hand. Its estimates for the two differ by ~5° even for identical poses. |
| Left/right chosen by **position** when two hands are found | On a veena the fretting hand is always on the neck side. MediaPipe's handedness label often gives both hands the same name. |
| One tracker **per stream** | In video mode a tracker follows hands from frame to frame. Sharing one between two streams mixes them up. |
| MediaPipe isolated in `tracking/hands.py` | Moving to mediapipe 1.x (`HandLandmarker`, which also allows Python 3.13+) is a one-file change. |
| cv2-only drawing (`rendering/draw.py`) | Keeps MediaPipe's types out of rendering. A test checks it matches `drawing_utils.draw_landmarks` pixel for pixel. |
| Native log hiding in the CLI | MediaPipe's C++ code writes to file descriptor 2 from its own threads and ignores the GLOG/TF log-level variables. In a terminal the CLI points descriptor 2 at /dev/null and keeps Python's stderr on the terminal; `--verbose` turns this off. |

## Where to change things

| To change... | Edit |
|---|---|
| A default value | `config/settings.py` **and** `motion-capture.example.toml` (a test keeps them in sync) |
| A new setting | Add a field to the right dataclass in `config/settings.py`, then add it to the example TOML. Add a flag in `cli/main.py` (`build_parser` + `overrides_from_args`) if it should have one |
| How a hand is scored | `scoring/compare.py`, then regenerate `tests/golden/golden.json` and say why in the commit |
| The final summary / JSON report | `scoring/report.py` (`format_text`, `to_dict`) |
| On-screen text or layout | `rendering/panels.py` |
| The start gesture | `gestures/thumbs_up.py` |
| The hand tracker | `tracking/hands.py` (keep returning `Detection` / `HandsBySide`) |
| A new program | Add `apps/<name>.py` with a `run_<name>(...)` taking the interfaces above, and a subcommand in `cli/main.py` |

## Tests

- `tests/unit/`: pure logic with synthetic hands whose joint angles are known
  exactly (`tests/helpers.py`), plus the CLI's argument handling and error
  paths. No camera, no network.
- `tests/integration/`: the real programs with real MediaPipe on lossless
  sample clips. They're compared against `tests/golden/golden.json`, the
  numbers the original scripts produced, within 0.05° (the actual difference
  is around 1e-14°).
- Marker: `pytest -m "not integration"` skips the slower ones. If the sample
  images can't be downloaded, the integration tests are skipped, not failed.
