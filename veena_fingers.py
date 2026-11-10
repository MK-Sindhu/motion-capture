# -*- coding: utf-8 -*-
"""
Veena Finger Matching with Final Percentage Score

Plays a reference video of a veena player next to your webcam feed and
compares the finger joint angles of both hands frame by frame:
  - Left hand  = fretting hand (presses / pulls the strings on the neck)
  - Right hand = plucking hand (index/middle on the main strings, pinky on the tala strings)

How a session goes:
  1. WAITING   - the reference video loops. Show a thumbs up (or press SPACE).
  2. COUNTDOWN - the reference rewinds and pauses for COUNTDOWN_SEC seconds
                 while you put your hand back on the veena.
  3. RUNNING   - both videos play; every frame, each of your hands is compared
                 with the same hand in the reference and drawn green (close)
                 or red (far off).
  4. Press ESC - you get a match score, a score per hand and an error per finger.

Usage:
    python3 veena_fingers.py [path/to/reference_video]
"""

# sys          - sys.argv = the words typed after "python3 veena_fingers.py"
# time         - time.time() = current time in seconds, used for the countdown
# defaultdict  - a dict that creates an empty value (here: an empty list) the first time a key is used
# Path         - file paths that work the same on macOS, Linux and Windows
# cv2          - OpenCV: reads the camera/video, draws shapes and text, shows the window
# mediapipe    - Google's MediaPipe: finds hands and their 21 landmark points
# numpy        - number arrays and maths (dot products, means, ...)
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

# ---------------- CONFIG ----------------
# Settings you can change. Everything else in the file follows from these.

BASE_DIR = Path(__file__).resolve().parent          # the folder this script is in
REFERENCE_VIDEO_PATH = BASE_DIR / "veena_reference.mp4"   # default reference clip (a path typed
                                                          # on the command line replaces it)
ANGLE_THRESHOLD_DEG = 20          # average finger-joint error (degrees) that scores 0%.
                                  # Below it a hand is drawn green, at or above it red.
                                  # Raise it to be more forgiving, lower it to be stricter.
START_GESTURE_FRAMES = 3          # how many frames in a row the thumbs up must be seen before
                                  # starting (stops a single wrong detection from starting it)
COUNTDOWN_SEC = 3                 # seconds to put your hand back on the veena after the thumbs up
REFERENCE_IS_MIRRORED = False     # True only if the reference clip is already a mirrored selfie recording
CAMERA_INDEX = 0                  # which camera to use: 0 = first camera macOS lists, 1 = second, ...
                                  # A nearby iPhone (Continuity Camera) can take number 0 and push the
                                  # Mac's own camera to 1. Run "python3 hand_check.py 1" to try a number.
CAMERA_RESOLUTION = (1280, 720)   # (width, height) in pixels to ask the webcam for. Fingers are small,
                                  # so more pixels = sharper fingers = more accurate points.
                                  # The camera may give a different size if it doesn't support this one.
MAX_WINDOW_WIDTH = 1600           # the window starts at most this wide (pixels) so it fits on screen
WINDOW_NAME = "Reference (Left) | User (Right)"   # title of the video window
# ----------------------------------------

# ---------------- MEDIAPIPE INIT ----------------
mp_hands = mp.solutions.hands            # MediaPipe's hand-tracking module (the model + the list of
                                         # which landmark points are joined by "bones")
mp_drawing = mp.solutions.drawing_utils  # MediaPipe's helper for drawing those points and bones on an image

# Settings for the hand trackers, kept in one dict so both trackers get the same ones.
HANDS_KWARGS = dict(
    static_image_mode=False,       # False = video mode: find the hand once, then follow it from frame to
                                   # frame (faster and steadier). True would search every frame from scratch.
    max_num_hands=2,               # look for up to 2 hands (fretting + plucking)
    model_complexity=1,            # 0 = lite model (faster), 1 = full model (more accurate)
    min_detection_confidence=0.5,  # how sure (0..1) the model must be before it reports a NEW hand
    min_tracking_confidence=0.5,   # if its confidence in a hand it is following drops below this,
                                   # it treats the hand as lost and searches again
)

# One tracker per video stream: a Hands instance carries tracking state
# between calls, so sharing it between the webcam and the reference clip
# makes each prediction pollute the other.
hands_cam_tracker = mp_hands.Hands(**HANDS_KWARGS)   # tracks the webcam (you)
hands_ref_tracker = mp_hands.Hands(**HANDS_KWARGS)   # tracks the reference video (the teacher)

# ---------------- FINGER JOINTS ----------------
# MediaPipe gives 21 points per hand, numbered like this:
#
#         8   12  16  20     <- fingertips
#         7   11  15  19     <- end joints
#         6   10  14  18     <- middle joints
#    4    5    9  13  17     <- knuckles
#     3
#      2        (thumb: 1-4)
#       1
#           0                <- wrist
#
# FINGER_JOINTS lists the 3 joints of every finger (15 joints per hand). Each
# joint is a triple (a, b, c) of point numbers: the angle is measured AT point
# b, between the bone going to a and the bone going to c. A straight joint is
# 180 degrees. Example: (5, 6, 7) is the index finger's middle joint (point 6),
# between the bone 6->5 (towards the knuckle) and the bone 6->7 (towards the tip).
FINGER_JOINTS = {
    "Thumb":  [(0, 1, 2), (1, 2, 3), (2, 3, 4)],
    "Index":  [(0, 5, 6), (5, 6, 7), (6, 7, 8)],
    "Middle": [(0, 9, 10), (9, 10, 11), (10, 11, 12)],
    "Ring":   [(0, 13, 14), (13, 14, 15), (14, 15, 16)],
    "Pinky":  [(0, 17, 18), (17, 18, 19), (18, 19, 20)],
}
SIDES = ("Left", "Right")                                # the player's own left and right hand
HAND_ROLES = {"Left": "fretting", "Right": "plucking"}   # what each hand does on a veena

# Colours. OpenCV writes colours as (Blue, Green, Red), NOT (Red, Green, Blue).
GREEN = (0, 255, 0)
RED = (0, 0, 255)
YELLOW = (0, 255, 255)
WHITE = (255, 255, 255)

# ---------------- UTILITIES ----------------
def angle(a, b, c):
    """Angle in degrees at point b, between the lines b->a and b->c.

    a, b, c are coordinates (x, y, z). Uses the dot-product rule:
    cos(angle) = (ba . bc) / (|ba| * |bc|).
    """
    ba = np.array(a) - np.array(b)  # arrow from the joint b to point a
    bc = np.array(c) - np.array(b)  # arrow from the joint b to point c
    # + 1e-6 (0.000001) avoids dividing by zero if two points land on top of each other
    cosang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    # Rounding can push cosang slightly past 1.0 or -1.0, where arccos is undefined,
    # so clip it into range first. arccos gives radians; convert to degrees.
    return np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0)))

def finger_angles(world_landmarks):
    """Joint angles per finger, from MediaPipe's 3D world landmarks.

    Returns a dict of finger name -> array of its 3 joint angles, e.g.
    {"Thumb": array([150., 160., 170.]), "Index": array([...]), ...}

    The world landmarks are metric 3D coordinates, so a finger bending toward
    or away from the camera is still measured correctly (the 2D image
    landmarks would flatten that out).
    """
    # pts = a 21 x 3 table: row i holds the (x, y, z) of landmark point i, in metres
    pts = np.array([[p.x, p.y, p.z] for p in world_landmarks.landmark])
    return {
        finger: np.array([angle(pts[a], pts[b], pts[c]) for a, b, c in joints])
        for finger, joints in FINGER_JOINTS.items()
    }

def hands_by_side(result):
    """Map the player's own 'Left' / 'Right' hand to (landmarks, world_landmarks).

    result is what a tracker's .process() returned. It has three parallel
    lists, one entry per hand found (or None if no hand was found):
      - multi_hand_landmarks:       points as fractions of the image size (for drawing)
      - multi_hand_world_landmarks: the same points in 3D, in metres (for angles)
      - multi_handedness:           MediaPipe's guess "Left" or "Right"

    Returns a dict, e.g. {"Left": (landmarks, world_landmarks)} or {} if no hands.

    Expects a mirrored (selfie-view) image, which is what MediaPipe's
    handedness labels assume; there the player's right hand is on the image's
    right.

    With two hands, sort by position instead of trusting the handedness
    classifier: on a veena the fretting hand is always on the neck side and the
    plucking hand on the resonator side, while the classifier often gives both
    hands the same label. With one hand, use the classifier's label.
    """
    if not result.multi_hand_landmarks:   # no hands in this frame
        return {}

    # Glue the three lists together: found[i] = (landmarks, world_landmarks, handedness) of hand i
    found = list(zip(
        result.multi_hand_landmarks,
        result.multi_hand_world_landmarks,
        result.multi_handedness,
    ))

    if len(found) == 2:
        # Sort by the wrist's (point 0) x position. x runs from 0 at the left edge
        # of the image to 1 at the right edge, so after sorting found[0] is the
        # hand further left on screen.
        found.sort(key=lambda f: f[0].landmark[0].x)
        # [:2] keeps (landmarks, world_landmarks) and drops the handedness guess
        return {"Left": found[0][:2], "Right": found[1][:2]}

    # Only one hand: we can't compare positions, so use MediaPipe's label
    lm, world, handedness = found[0]
    return {handedness.classification[0].label: (lm, world)}

def score_from_error(err):
    """Turn an average angle error (degrees) into a percentage.

    0 deg of error -> 100%, error at/above the threshold -> 0%, in a straight
    line between. With ANGLE_THRESHOLD_DEG = 20: 5 deg -> 75%, 10 deg -> 50%.
    """
    return max(0.0, 100.0 * (1.0 - err / ANGLE_THRESHOLD_DEG))

def put_text(frame, text, org, scale=1.0, color=YELLOW, thickness=2):
    """Write text on the image. org = (x, y) pixel position of the text's bottom-left corner."""
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)

def draw_hand(frame, hand_landmarks, side, color=None, error=None):
    """Draw one hand's skeleton and a label ("Left" / "Right", plus the error if given).

    color=None uses MediaPipe's default style (red dots, white bones), which is
    how the reference hands are drawn. Your hands are drawn green or red.
    """
    if color is None:
        mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
    else:
        # DrawingSpec = style (colour, line thickness, dot radius); the same style is
        # used for the dots (1st spec) and the bones (2nd spec).
        spec = mp_drawing.DrawingSpec(color=color, thickness=2, circle_radius=3)
        mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS, spec, spec)

    h, w = frame.shape[:2]                 # image height and width in pixels
    wrist = hand_landmarks.landmark[0]     # wrist.x / wrist.y are fractions (0..1) of the image size
    label = side if error is None else f"{side} {error:.0f} deg"
    # Write the label just below the wrist (in images, y grows downward)
    put_text(frame, label, (int(wrist.x * w) - 40, int(wrist.y * h) + 30),
             0.7, color or WHITE)

# ---------------- THUMBS UP ----------------
def is_thumbs_up(hand_landmarks):
    """True if the hand looks like a thumbs up.

    In images y = 0 is the TOP, so a smaller y means higher up. A thumbs up
    has the thumb tip (4) above the thumb's own joint (3), and the index tip
    (8) and middle tip (12) below that joint (fingers curled into a fist).
    """
    lm = hand_landmarks.landmark
    return (
        lm[4].y < lm[3].y and
        lm[8].y > lm[3].y and
        lm[12].y > lm[3].y
    )

# ---------------- VIDEO CAPTURE ----------------
# sys.argv[0] is the script name; sys.argv[1] (if given) is the reference video path.
ref_path = Path(sys.argv[1]) if len(sys.argv) > 1 else REFERENCE_VIDEO_PATH
cap_ref = cv2.VideoCapture(str(ref_path))   # the reference video file
cap_cam = cv2.VideoCapture(CAMERA_INDEX)    # the webcam chosen in CONFIG

if not cap_ref.isOpened():
    raise IOError(f"Cannot open reference video: {ref_path}")

if not cap_cam.isOpened():
    raise IOError(f"Cannot open webcam (device {CAMERA_INDEX})")

# Ask the webcam for the resolution set in CONFIG
cap_cam.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
cap_cam.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])

def start_countdown():
    """Rewind the reference and hold its first frame until the countdown ends.

    Returns (first frame of the reference, time at which the countdown ends).
    """
    cap_ref.set(cv2.CAP_PROP_POS_FRAMES, 0)   # jump back to frame 0
    ok, frame = cap_ref.read()                # read it (the video is now positioned at frame 1)
    if not ok:
        raise IOError(f"Cannot read reference video: {ref_path}")
    return frame, time.time() + COUNTDOWN_SEC

cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)   # WINDOW_NORMAL = the window can be resized with the mouse

# ---------------- RUNNING STATE ----------------
state = "waiting"        # which stage we're in: "waiting" -> "countdown" -> "running"
thumb_counter = 0        # how many frames in a row a thumbs up has been seen
first_ref_frame = None   # the reference's first frame, shown frozen during the countdown
countdown_end = 0.0      # time (from time.time()) when the countdown finishes
frames_running = 0       # how many frames have been compared so far (in the "running" stage)
# hand_errors["Left"] = list of that hand's average error (degrees), one entry per frame it was compared
hand_errors = {side: [] for side in SIDES}
# finger_errors[("Left", "Index")] = list of that finger's error (degrees), one entry per frame
finger_errors = defaultdict(list)
combined = None          # the last side-by-side image shown (reused for the final score screen)

# ---------------- MAIN LOOP ----------------
# Runs once per webcam frame until the webcam stops or ESC is pressed.
while cap_cam.isOpened():

    # ret_cam = False when no frame could be read.
    # frame_cam = the image: a numpy array of shape (height, width, 3) in BGR colour.
    ret_cam, frame_cam = cap_cam.read()
    if not ret_cam:
        break

    if state == "countdown":
        # During the countdown, keep showing the reference's first frame
        frame_ref = first_ref_frame.copy()
    else:
        # Otherwise read the next reference frame; when the video ends,
        # rewind to frame 0 so it loops.
        ret_ref, frame_ref = cap_ref.read()
        if not ret_ref:
            cap_ref.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret_ref, frame_ref = cap_ref.read()
            if not ret_ref:
                break

    # Both views are shown and tracked as a mirror. Tracking one stream
    # mirrored and the other not would show the model a left hand in one and a
    # (mirror-image) right hand in the other, and its estimates for the two
    # differ by several degrees even for an identical pose.
    frame_cam = cv2.flip(frame_cam, 1)         # 1 = flip left <-> right
    if not REFERENCE_IS_MIRRORED:
        frame_ref = cv2.flip(frame_ref, 1)
    h, w, _ = frame_cam.shape                  # webcam image height and width in pixels

    # Track the reference at its native size so the hands aren't stretched;
    # landmarks are normalised, so they still line up after the resize.
    # MediaPipe expects RGB colour order, OpenCV gives BGR, so convert before tracking.
    res_ref = hands_ref_tracker.process(cv2.cvtColor(frame_ref, cv2.COLOR_BGR2RGB))
    res_cam = hands_cam_tracker.process(cv2.cvtColor(frame_cam, cv2.COLOR_BGR2RGB))
    frame_ref = cv2.resize(frame_ref, (w, h))  # same size as the webcam so they fit side by side

    # e.g. {"Left": (landmarks, world_landmarks), "Right": (...)}
    ref_hands = hands_by_side(res_ref)         # the teacher's hands
    cam_hands = hands_by_side(res_cam)         # your hands

    # ---- START GESTURE ----
    if state == "waiting":
        # multi_hand_landmarks is None when no hands are found, hence "or []"
        if any(is_thumbs_up(lm) for lm in (res_cam.multi_hand_landmarks or [])):
            thumb_counter += 1
        else:
            thumb_counter = 0                  # streak broken: start counting again

        if thumb_counter >= START_GESTURE_FRAMES:
            first_ref_frame, countdown_end = start_countdown()
            state = "countdown"

    elif state == "countdown" and time.time() >= countdown_end:
        state = "running"

    # ---- FINGER ANGLE COMPARISON ----
    # frame_error["Left"] = that hand's average error in THIS frame (used for the colour and label)
    frame_error = {}
    if state == "running":
        frames_running += 1
        for side in SIDES:
            # Only compare a hand that was found in BOTH videos this frame
            if side in cam_hands and side in ref_hands:
                # [1] picks the 3D world landmarks out of (landmarks, world_landmarks)
                ang_cam = finger_angles(cam_hands[side][1])   # your 15 joint angles
                ang_ref = finger_angles(ref_hands[side][1])   # the teacher's 15 joint angles
                # Error of each finger = average of |your angle - teacher's angle| over its 3 joints
                per_finger = {
                    f: float(np.mean(np.abs(ang_cam[f] - ang_ref[f])))
                    for f in FINGER_JOINTS
                }
                for f, err in per_finger.items():
                    finger_errors[(side, f)].append(err)
                # Error of the hand = average over its 5 fingers
                frame_error[side] = float(np.mean(list(per_finger.values())))
                hand_errors[side].append(frame_error[side])

    # ---- DRAW ----
    # The teacher's hands, in MediaPipe's default style
    for side, (lm, _) in ref_hands.items():
        draw_hand(frame_ref, lm, side)

    # Your hands: green if close to the teacher this frame, red otherwise
    # (also red when there was nothing to compare, e.g. before starting)
    for side, (lm, _) in cam_hands.items():
        err = frame_error.get(side)            # None if this hand wasn't compared this frame
        color = GREEN if err is not None and err < ANGLE_THRESHOLD_DEG else RED
        draw_hand(frame_cam, lm, side, color, err)

    # Instructions / status text on your side of the screen
    if state == "waiting":
        put_text(frame_cam, "Show THUMBS UP (or press SPACE) to start", (40, 60))
    elif state == "countdown":
        remaining = int(np.ceil(countdown_end - time.time()))   # whole seconds left, rounded up
        put_text(frame_cam, "Hands on the veena...", (40, 60))
        put_text(frame_cam, str(remaining), (w // 2 - 40, h // 2 + 40), 4, YELLOW, 8)   # big number, centred
    elif not cam_hands:
        put_text(frame_cam, "No hands visible - move closer / improve lighting", (40, 60), 0.8, RED)

    # Put the two images next to each other: reference on the left, you on the right
    first_frame = combined is None
    combined = np.hstack([frame_ref, frame_cam])
    cv2.imshow(WINDOW_NAME, combined)
    if first_frame:
        # Size the window once, shrinking it if it would be wider than MAX_WINDOW_WIDTH
        scale = min(1.0, MAX_WINDOW_WIDTH / combined.shape[1])
        cv2.resizeWindow(WINDOW_NAME, int(combined.shape[1] * scale), int(combined.shape[0] * scale))

    # waitKey(1) waits up to 1 ms for a key press (it also lets the window redraw).
    # It returns the key's code; "& 0xFF" keeps only the last 8 bits of it.
    key = cv2.waitKey(1) & 0xFF
    if key == 27:                              # 27 = ESC: stop and show the score
        break
    if key == 32 and state == "waiting":       # 32 = SPACE: start without the thumbs up
        first_ref_frame, countdown_end = start_countdown()
        state = "countdown"

# ---------------- FINAL SCORE ----------------
# The hands that were compared at least once
compared = [side for side in SIDES if hand_errors[side]]

if compared and combined is not None:
    print(f"\nCompared {frames_running} frames")

    final = combined.copy()        # the last frame, to write the scores on
    y = 220                        # pixel row for the first per-hand line on the final screen
    for side in compared:
        err = np.mean(hand_errors[side])           # this hand's average error over all compared frames
        score = score_from_error(err)
        # coverage = % of running frames in which this hand was found in both videos
        coverage = 100.0 * len(hand_errors[side]) / frames_running

        print(f"\n{side} hand ({HAND_ROLES[side]}): avg error {err:.1f} deg, "
              f"score {score:.1f}%  (tracked in {coverage:.0f}% of frames)")
        for finger in FINGER_JOINTS:
            print(f"    {finger:<7} {np.mean(finger_errors[(side, finger)]):5.1f} deg")

        put_text(final, f"{side} hand ({HAND_ROLES[side]}): {score:.1f}%", (50, y), 1.2, GREEN, 3)
        y += 55                                    # next line 55 px lower

    # Overall: average of every per-frame error from both hands together
    avg_error = np.mean(np.concatenate([hand_errors[side] for side in compared]))
    score = score_from_error(avg_error)
    # The (hand, finger) pair with the largest average error
    worst_side, worst_finger = max(finger_errors, key=lambda k: np.mean(finger_errors[k]))

    print(f"\nAverage finger-joint error: {avg_error:.1f} deg")
    print(f"Match Score: {score:.1f}%")
    print(f"Biggest difference: {worst_side} hand, {worst_finger}")

    put_text(final, f"Match Score: {score:.1f}%", (50, 140), 2.5, GREEN, 5)
    cv2.imshow(WINDOW_NAME, final)
    cv2.waitKey(0)                 # 0 = wait until any key is pressed
else:
    print("No finger comparison recorded - did you start with a THUMBS UP (or SPACE), "
          "and were your hands visible in both videos?")

# ---------------- CLEAN EXIT ----------------
cap_cam.release()            # free the webcam
cap_ref.release()            # close the reference video file
hands_cam_tracker.close()    # free the MediaPipe models
hands_ref_tracker.close()
cv2.destroyAllWindows()      # close the window
