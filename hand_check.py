# -*- coding: utf-8 -*-
"""
Hand Tracking Check - no reference video, no scoring.

Shows whether MediaPipe picks up both hands and how much each finger bends,
live, so you can check camera framing and lighting before using
veena_fingers.py.

What you see on screen:
  - each detected hand drawn as a skeleton (Left = blue, Right = orange)
  - a short trail behind every fingertip, so movement is easy to see
  - a panel per hand with one bar per finger showing how bent it is
  - at the bottom: frames per second and how often each hand was found

Usage:
    python3 hand_check.py              # webcam CAMERA_INDEX (0 unless changed below)
    python3 hand_check.py 1            # a different webcam (try this if your iPhone camera opens)
    python3 hand_check.py clip.mp4     # check how well a video (e.g. a reference clip) tracks

Press ESC to quit.
"""

# sys        - sys.argv = the words typed after "python3 hand_check.py"
# time       - time.time() = current time in seconds, used for FPS
# deque      - a list with a maximum length: adding to a full one drops the oldest item
# cv2        - OpenCV: reads the camera/video, draws shapes and text, shows the window
# mediapipe  - Google's MediaPipe: finds hands and their 21 landmark points
# numpy      - number arrays and maths (dot products, means, ...)
import sys
import time
from collections import deque

import cv2
import mediapipe as mp
import numpy as np

# ---------------- CONFIG ----------------
# Settings you can change. Everything else in the file follows from these.

CAMERA_INDEX = 0  # camera used when none is given on the command line: 0 = first camera
# macOS lists, 1 = second, ... A nearby iPhone (Continuity Camera) can
# take number 0 and push the Mac's own camera to 1.
CAMERA_RESOLUTION = (
    1280,
    720,
)  # (width, height) in pixels to ask the webcam for. Fingers are small,
# so more pixels = sharper fingers = more accurate points.
# The camera may give a different size if it doesn't support this one.
TRAIL_LENGTH = 10  # how many past positions of each fingertip to draw as a trail
# (20 frames is about 2/3 of a second at 30 FPS)
MAX_BEND_DEG = 120  # a finger bent this much (in degrees) fills its bar completely
WINDOW_NAME = "Hand tracking check (ESC to quit)"  # title of the video window
# ----------------------------------------

# ---------------- MEDIAPIPE INIT ----------------
mp_hands = (
    mp.solutions.hands
)  # MediaPipe's hand-tracking module (the model + the list of
# which landmark points are joined by "bones")
mp_drawing = (
    mp.solutions.drawing_utils
)  # MediaPipe's helper for drawing those points and bones on an image

# The hand tracker itself. Every call to hands.process(image) returns the hands it found.
hands = mp_hands.Hands(
    static_image_mode=False,  # False = video mode: find the hand once, then follow it from frame to
    # frame (faster and steadier). True would search every frame from scratch.
    max_num_hands=2,  # look for up to 2 hands (fretting + plucking)
    model_complexity=1,  # 0 = lite model (faster), 1 = full model (more accurate)
    min_detection_confidence=0.5,  # how sure (0..1) the model must be before it reports a NEW hand
    min_tracking_confidence=0.5,  # if its confidence in a hand it is following drops below this,
    # it treats the hand as lost and searches again
)

# ---------------- HAND LANDMARKS ----------------
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
# FINGER_JOINTS lists the 3 joints of every finger. Each joint is a triple
# (a, b, c) of point numbers: the angle is measured AT point b, between the
# bone going to a and the bone going to c. A straight joint is 180 degrees.
# Example: (5, 6, 7) is the index finger's middle joint (point 6), between
# the bone 6->5 (towards the knuckle) and the bone 6->7 (towards the tip).
FINGER_JOINTS = {
    "Thumb": [(0, 1, 2), (1, 2, 3), (2, 3, 4)],
    "Index": [(0, 5, 6), (5, 6, 7), (6, 7, 8)],
    "Middle": [(0, 9, 10), (9, 10, 11), (10, 11, 12)],
    "Ring": [(0, 13, 14), (13, 14, 15), (14, 15, 16)],
    "Pinky": [(0, 17, 18), (17, 18, 19), (18, 19, 20)],
}
FINGERTIPS = {
    "Thumb": 4,
    "Index": 8,
    "Middle": 12,
    "Ring": 16,
    "Pinky": 20,
}  # point number of each fingertip

SIDES = ("Left", "Right")  # the player's own left and right hand
HAND_ROLES = {"Left": "fretting", "Right": "plucking"}  # what each hand does on a veena

# Colours. OpenCV writes colours as (Blue, Green, Red), NOT (Red, Green, Blue).
SIDE_COLORS = {
    "Left": (255, 170, 0),
    "Right": (0, 200, 255),
}  # Left = blue, Right = orange
RED = (0, 0, 255)
WHITE = (255, 255, 255)

# Size of the finger-bend panel, in pixels:
#   PANEL_W = panel width, PANEL_H = panel height,
#   BAR_X   = how far from the panel's left edge the bars start (room for the finger name),
#   BAR_W   = length of a completely full bar.
PANEL_W, PANEL_H, BAR_X, BAR_W = 300, 190, 90, 150


# ---------------- UTILITIES ----------------
def angle(a, b, c):
    """Angle in degrees at point b, between the lines b->a and b->c.

    a, b, c are numpy arrays of coordinates (x, y, z). Uses the dot-product
    rule: cos(angle) = (ba . bc) / (|ba| * |bc|).
    """
    ba = a - b  # arrow from the joint b to point a
    bc = c - b  # arrow from the joint b to point c
    # + 1e-6 (0.000001) avoids dividing by zero if two points land on top of each other
    cosang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    # Rounding can push cosang slightly past 1.0 or -1.0, where arccos is undefined,
    # so clip it into range first. arccos gives radians; convert to degrees.
    return np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0)))


def finger_bends(world_landmarks):
    """How bent each finger is, in degrees: 0 = straight, larger = more curled.

    Returns a dict like {"Thumb": 25.0, "Index": 33.0, ...}. A finger's bend
    is 180 minus the average of its 3 joint angles.

    Uses MediaPipe's 3D world landmarks (x, y, z in metres), so a finger
    bending toward or away from the camera still counts.
    """
    # pts = a 21 x 3 table: row i holds the (x, y, z) of landmark point i
    pts = np.array([[p.x, p.y, p.z] for p in world_landmarks.landmark])
    return {
        finger: 180.0 - np.mean([angle(pts[a], pts[b], pts[c]) for a, b, c in joints])
        for finger, joints in FINGER_JOINTS.items()
    }


def hands_by_side(result):
    """Map the player's 'Left' / 'Right' hand to (landmarks, world_landmarks).

    result is what hands.process() returned. It has three parallel lists,
    one entry per hand found (or None if no hand was found):
      - multi_hand_landmarks:       points as fractions of the image size (for drawing)
      - multi_hand_world_landmarks: the same points in 3D, in metres (for angles)
      - multi_handedness:           MediaPipe's guess "Left" or "Right"

    Returns a dict, e.g. {"Left": (landmarks, world_landmarks)} or {} if no hands.

    Same rule as veena_fingers.py: expects a mirrored image; with two hands,
    the one further left on screen is the left hand; with one hand, trust
    MediaPipe's handedness label.
    """
    if not result.multi_hand_landmarks:  # no hands in this frame
        return {}

    # Glue the three lists together: found[i] = (landmarks, world_landmarks, handedness) of hand i
    found = list(
        zip(
            result.multi_hand_landmarks,
            result.multi_hand_world_landmarks,
            result.multi_handedness,
        )
    )

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


def put_text(frame, text, org, scale=0.6, color=WHITE, thickness=1):
    """Write text on the image. org = (x, y) pixel position of the text's bottom-left corner."""
    # cv2.LINE_AA = anti-aliased (smooth-edged) letters
    cv2.putText(
        frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA
    )


def draw_panel(frame, side, bends):
    """Per-finger bend bars for one hand, top-left (Left) or top-right (Right).

    bends is the dict from finger_bends(), or None if this hand wasn't found
    (then the panel says NOT DETECTED).

    On a frame too narrow for two panels side by side, Right goes below Left.
    """
    w = frame.shape[1]  # image width in pixels (frame.shape = (height, width, 3))
    side_by_side = (
        w >= 2 * PANEL_W + 30
    )  # is there room for two panels next to each other?
    # (x0, y0) = the panel's top-left corner in pixels. In images, y = 0 is the TOP and grows downward.
    x0 = 10 if side == "Left" or not side_by_side else w - PANEL_W - 10
    y0 = 10 if side == "Left" or side_by_side else PANEL_H + 20

    # region is a window onto the panel's rectangle of the image (not a copy),
    # so scaling it to 35% brightness darkens that part of the frame itself.
    region = frame[y0 : y0 + PANEL_H, x0 : x0 + PANEL_W]
    region[:] = (region * 0.35).astype(np.uint8)  # darken behind the text

    color = SIDE_COLORS[side]
    put_text(
        frame, f"{side} hand ({HAND_ROLES[side]})", (x0 + 10, y0 + 25), 0.65, color, 2
    )

    if bends is None:
        put_text(frame, "NOT DETECTED", (x0 + 10, y0 + 100), 0.9, RED, 2)
        return

    # One row per finger: name, bar, number
    for i, (finger, bend) in enumerate(bends.items()):
        y = y0 + 55 + i * 27  # baseline of this row (rows are 27 px apart)
        put_text(frame, finger, (x0 + 10, y))
        # fill = how many pixels of the bar to colour in (bend limited to 0..MAX_BEND_DEG)
        fill = int(np.clip(bend, 0, MAX_BEND_DEG) / MAX_BEND_DEG * BAR_W)
        # empty grey outline of the full bar (thickness 1)...
        cv2.rectangle(
            frame, (x0 + BAR_X, y - 14), (x0 + BAR_X + BAR_W, y), (90, 90, 90), 1
        )
        # ...and the coloured part on top (thickness -1 = filled rectangle)
        cv2.rectangle(frame, (x0 + BAR_X, y - 14), (x0 + BAR_X + fill, y), color, -1)
        put_text(frame, f"{bend:3.0f}", (x0 + BAR_X + BAR_W + 10, y))


# ---------------- VIDEO SOURCE ----------------
# sys.argv[0] is the script name; sys.argv[1] (if given) is what to read from.
source = sys.argv[1] if len(sys.argv) > 1 else str(CAMERA_INDEX)
is_camera = (
    source.isdigit()
)  # "0", "1", ... = a webcam number; anything else = a video file
cap = cv2.VideoCapture(
    int(source) if is_camera else source
)  # cap = the open camera or video file

if not cap.isOpened():
    raise IOError(f"Cannot open {'webcam ' if is_camera else ''}{source}")

if is_camera:
    # Ask the webcam for the resolution set in CONFIG (a video file's size can't be changed)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])

cv2.namedWindow(
    WINDOW_NAME, cv2.WINDOW_NORMAL
)  # WINDOW_NORMAL = the window can be resized with the mouse

# ---------------- RUNNING TOTALS ----------------
frames = 0  # how many frames have been processed so far
tracked = {side: 0 for side in SIDES}  # how many of those frames each hand was found in
# trails[(side, finger)] = the last TRAIL_LENGTH pixel positions (x, y) of that fingertip
trails = {(side, f): deque(maxlen=TRAIL_LENGTH) for side in SIDES for f in FINGERTIPS}
fps = 0.0  # smoothed frames-per-second shown on screen
last_time = time.time()  # when the previous frame finished (for FPS)
start_time = last_time  # when the loop started (for the average FPS at the end)

# ---------------- MAIN LOOP ----------------
# Runs once per video frame until the video ends or ESC is pressed.
while True:
    # ok = False when there are no more frames (video ended / camera unplugged).
    # frame = the image: a numpy array of shape (height, width, 3) in BGR colour.
    ok, frame = cap.read()
    if not ok:
        break

    # Mirror view (selfie), which MediaPipe's handedness labels assume.
    # A video file is flipped too, the same as veena_fingers.py does by default.
    frame = cv2.flip(frame, 1)  # 1 = flip left <-> right
    h, w = frame.shape[:2]  # image height and width in pixels

    # MediaPipe expects RGB colour order, OpenCV gives BGR, so convert before tracking
    result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    found = hands_by_side(result)  # e.g. {"Left": (...), "Right": (...)}
    frames += 1

    for side in SIDES:
        if side not in found:
            # Hand lost: forget its trails, otherwise the next time it is found a
            # line would be drawn from where it used to be.
            for f in FINGERTIPS:
                trails[(side, f)].clear()
            draw_panel(frame, side, None)  # panel shows NOT DETECTED
            continue  # go on to the other hand

        tracked[side] += 1
        lm, world = found[
            side
        ]  # lm = screen points (for drawing), world = 3D points (for angles)
        color = SIDE_COLORS[side]

        # Fingertip trails, thicker toward the newest point.
        for f, tip in FINGERTIPS.items():
            p = lm.landmark[
                tip
            ]  # this fingertip; p.x and p.y are fractions (0..1) of the image size
            trail = trails[(side, f)]
            trail.append(
                (int(p.x * w), int(p.y * h))
            )  # convert to pixels and remember it
            # Join consecutive positions with lines; i / len(trail) goes from ~0 (oldest)
            # to 1 (newest), so the line thickness grows from 1 to 4 pixels.
            for i in range(1, len(trail)):
                cv2.line(
                    frame,
                    trail[i - 1],
                    trail[i],
                    color,
                    1 + 3 * i // len(trail),
                    cv2.LINE_AA,
                )

        # Draw the hand: dots on the 21 points and lines along the bones.
        # DrawingSpec = style (colour, line thickness, dot radius); the same style is
        # used for the dots (1st spec) and the bones (2nd spec).
        spec = mp_drawing.DrawingSpec(color=color, thickness=2, circle_radius=3)
        mp_drawing.draw_landmarks(frame, lm, mp_hands.HAND_CONNECTIONS, spec, spec)

        wrist = lm.landmark[0]  # write "Left" / "Right" just below the wrist
        put_text(
            frame, side, (int(wrist.x * w) - 25, int(wrist.y * h) + 30), 0.7, color, 2
        )
        draw_panel(frame, side, finger_bends(world))

    # Frames per second. 1 / (time this frame took) jumps around a lot, so blend
    # 10% of the new value into 90% of the old one for a steady number.
    now = time.time()
    fps = 0.9 * fps + 0.1 / max(now - last_time, 1e-6)
    last_time = now
    put_text(
        frame,
        f"FPS {fps:4.1f}   tracked so far: Left {100 * tracked['Left'] / frames:3.0f}%"
        f"  Right {100 * tracked['Right'] / frames:3.0f}%",
        (10, h - 15),
        0.65,
        WHITE,
        2,  # bottom-left corner of the image
    )

    cv2.imshow(WINDOW_NAME, frame)  # show the finished frame in the window
    # waitKey(1) waits up to 1 ms for a key press (it also lets the window redraw).
    # It returns the key's code; "& 0xFF" keeps only the last 8 bits of it. 27 = ESC.
    if cv2.waitKey(1) & 0xFF == 27:
        break

# ---------------- SUMMARY ----------------
# Printed in the terminal after the window closes.
if frames:
    elapsed = time.time() - start_time  # total running time in seconds
    print(f"\n{frames} frames in {elapsed:.1f}s ({frames / elapsed:.1f} FPS)")
    for side in SIDES:
        pct = 100.0 * tracked[side] / frames  # % of frames this hand was found in
        hint = (
            "" if pct >= 80 else "  <- move the camera closer or add light on this hand"
        )
        print(f"{side} hand ({HAND_ROLES[side]}) tracked in {pct:.0f}% of frames{hint}")

# ---------------- CLEAN EXIT ----------------
cap.release()  # free the camera / close the video file
hands.close()  # free the MediaPipe model
cv2.destroyAllWindows()  # close the window
