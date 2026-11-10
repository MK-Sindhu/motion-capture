# Motion Capture — Sports Motion Matching

Webcam-based motion matching tools built with [MediaPipe](https://developers.google.com/mediapipe) pose/hand tracking and OpenCV. Each script shows a reference sports clip side-by-side with your live webcam feed, tracks body joint angles, and scores how closely your motion matches the reference.

## Scripts

### `open_house4.py` — Live Angle-Threshold Matching
- Plays a reference video next to your webcam feed.
- Show a **thumbs up** gesture to start tracking.
- Compares 10 joint angles (elbows, shoulders, hips, knees, torso) between you and the reference clip frame-by-frame.
- Your skeleton overlay turns **green** when your average angle error is within `ANGLE_THRESHOLD_DEG` (default 22°), red otherwise.
- On exit (`ESC`), displays a final match percentage: 0° average error → 100%, error at or above the threshold → 0%.

### `open_house_dtw.py` — DTW-Based Shot Scoring
- Plays a reference video next to your webcam feed.
- Records your joint angles while you perform a single shot.
- Compares your angle sequence to the reference clip's using Dynamic Time Warping ([fastdtw](https://pypi.org/project/fastdtw/)), which tolerates differences in timing and speed.
- On first run it extracts the reference clip's angles and caches them to `reference_angles/*.npy`; later runs reuse the cache.
- Prints a final match score and verdict (`Good imitation!` / `Decent, needs improvement` / `Technique mismatch`).

### `veena_fingers.py` — Veena Finger Matching
- Plays a reference video of a veena player next to your webcam feed, tracking **both hands** (21 landmarks each) instead of the body.
- Show a **thumbs up** (or press `SPACE`) to start. You then get a `COUNTDOWN_SEC` countdown to put your hand back on the veena, and the reference restarts from the beginning.
- Compares 15 finger joint angles per hand (3 per finger), using MediaPipe's 3D hand world landmarks. A finger bending toward or away from the camera is still measured.
- Left hand = fretting hand, right hand = plucking hand. When both hands are visible, they are told apart by position (neck side vs resonator side), not by MediaPipe's handedness label.
- Each hand turns **green** when its average error is under `ANGLE_THRESHOLD_DEG` (default 20°).
- On exit (`ESC`), shows an overall match score, a score for each hand, a per-finger error breakdown, and how often each hand was tracked.
- Pass a different clip on the command line: `python3 veena_fingers.py path/to/clip.mp4`. Otherwise it uses `veena_reference.mp4` in this folder.

Both panels are shown as a mirror, so the teacher's fretting hand is on the same side of the screen as yours. Tracking both views with the same orientation also matters for accuracy. If one view were mirrored and the other not, MediaPipe's estimates for an identical hand pose would differ by about 5°.

Camera setup matters more here than for full-body tracking. Frame the shot from just above the veena's neck to just past the bridge so both hands are big in the image, keep the hands well lit, and film the reference from a similar angle. If the clip was recorded as a mirrored selfie, set `REFERENCE_IS_MIRRORED = True`.

### `hand_check.py` — Hand Tracking Check (no reference)
- Webcam only, no reference video and no scoring. Use it to check that your fingers are being tracked before running `veena_fingers.py`.
- Draws both hands with fingertip trails, and shows a live bend bar for each finger (0° = straight, larger = more curled).
- Shows FPS and the share of frames each hand was tracked in. On exit it warns about any hand tracked in under 80% of frames.
- `python3 hand_check.py` uses webcam 0. `python3 hand_check.py 1` picks another camera. `python3 hand_check.py clip.mp4` checks how well a video, such as a veena reference clip, tracks.

## Requirements

- **Python 3.9–3.12.** MediaPipe 0.10.21 has no wheels for 3.13+, so pip reports `No matching distribution found for mediapipe` there.
- A webcam.
- Reference video clips (`.avi`) — sample clips included in this folder:
  - `p10_bvolley_s1.avi` (the default reference for both scripts)
  - `p10_serflat_s1.avi`
  - `p10_serslice_s1.avi`
  - `p10_smash_s1.avi`
  - `p15_bslice_s1.avi`

## Setup from scratch

```bash
cd /home/agcl/Documents/motion-capture

# 1. Remove any previous environment
rm -rf venv

# 2. Create and activate a fresh virtual environment.
#    Name the Python version explicitly: plain `python3` may be 3.13+ (Homebrew
#    ships 3.14), and mediapipe 0.10.21 has no wheels for it.
python3.12 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

The install pulls roughly **200–300 MB** of wheels (mediapipe bundles native binaries and depends on jax/jaxlib and OpenCV), so allow time on a slow connection. To watch progress instead of waiting on a silent `-q` install, run it unquieted as above — pip prints a live progress bar per wheel.

Verify the install before running anything:

```bash
python3 -c "import cv2, mediapipe as mp, numpy, scipy, fastdtw; print(mp.__version__); mp.solutions.pose"
```

This must print a version no newer than `0.10.21` and not raise. If it fails with `module 'mediapipe' has no attribute 'solutions'`, you have mediapipe 0.10.30+ or 1.x installed. See [Why mediapipe is pinned](#why-mediapipe-is-pinned) below.

## Usage

Activate the environment first in every new shell:

```bash
cd /home/agcl/Documents/motion-capture
source venv/bin/activate
```

Run the live threshold-matching demo:

```bash
python3 open_house4.py
```

Run the DTW-based shot scoring demo:

```bash
python3 open_house_dtw.py
```

Run the veena finger-matching demo:

```bash
python3 veena_fingers.py path/to/veena_clip.mp4
```

Press `ESC` in the video window to stop tracking and see your score. For the body scripts, stand far enough back that your **whole body** is in frame. The scoring skips any frame where a tracked joint isn't confidently visible. For `veena_fingers.py`, do the opposite: frame just the instrument and your hands.

## Why mediapipe is pinned

Both scripts use MediaPipe's legacy **`mp.solutions`** API (`mp.solutions.pose`, `.hands`, `.drawing_utils`). That API was **removed in mediapipe 0.10.30** and is absent from all of 1.x, which exposes only `mp.tasks`. So `requirements.txt` pins `mediapipe>=0.10.14,<=0.10.21` (0.10.21 is the last release that ships `mp.solutions`; there is no 0.10.22–0.10.29), and transitively `numpy<2` (required by mediapipe 0.10.x) and `scipy<1.14` (for numpy 1.x ABI compatibility).

Note that `requirements.txt` lists **`opencv-contrib-python`**, not `opencv-python`. Both ship the same `cv2` module, and mediapipe 0.10.x already depends on the contrib build — installing both makes two distributions overwrite each other's `cv2`.

If you'd rather run on mediapipe 1.x / numpy 2.x, the scripts need porting to the new `mp.tasks.vision.PoseLandmarker` / `HandLandmarker` API, which also means downloading `.task` model bundles.

## Configuration

Both scripts resolve paths relative to their own location (`BASE_DIR`), so they work from any working directory. Tunables sit in the `CONFIG` block at the top of each file:

| Script | Variable | Purpose |
|---|---|---|
| `open_house4.py` | `REFERENCE_VIDEO_PATH` | Reference clip to compare against |
| `open_house4.py` | `ANGLE_THRESHOLD_DEG` | Angle error (degrees) that scores 0%; below it the skeleton turns green |
| `open_house4.py` | `START_GESTURE_FRAMES` | Consecutive thumbs-up frames needed to start |
| `open_house_dtw.py` | `REFERENCE_VIDEO_PATH` | Reference clip shown on screen and used to build the angle cache |
| `open_house_dtw.py` | `REFERENCE_ANGLES_PATH` | Where the extracted reference angles are cached (`.npy`) |
| both | `MIN_VISIBILITY` | Minimum landmark visibility for a joint to count |
| `veena_fingers.py` | `REFERENCE_VIDEO_PATH` | Default reference clip (a path given on the command line overrides it) |
| `veena_fingers.py` | `ANGLE_THRESHOLD_DEG` | Finger-joint error (degrees) that scores 0%; below it a hand turns green |
| `veena_fingers.py` | `COUNTDOWN_SEC` | Seconds between the start gesture and scoring |
| `veena_fingers.py` | `REFERENCE_IS_MIRRORED` | Set `True` if the reference clip is a mirrored selfie recording |
| `veena_fingers.py`, `hand_check.py` | `CAMERA_INDEX` | Which camera to open (0, 1, ...). On a Mac, a nearby iPhone (Continuity Camera) can take 0 |
| `veena_fingers.py` | `CAMERA_RESOLUTION` | Webcam resolution to request (higher = better finger detail) |

To switch reference clips in `open_house_dtw.py`, change **both** `REFERENCE_VIDEO_PATH` and `REFERENCE_ANGLES_PATH` (or delete the `reference_angles/` folder) so the cache is rebuilt for the new clip.
