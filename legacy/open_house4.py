# -*- coding: utf-8 -*-
"""
Motion Matching Game with Final Percentage Score
"""

import cv2
import mediapipe as mp
import numpy as np
from collections import deque
from pathlib import Path

# ---------------- CONFIG ----------------
BASE_DIR = Path(__file__).resolve().parent
REFERENCE_VIDEO_PATH = BASE_DIR / "p10_bvolley_s1.avi"
ANGLE_THRESHOLD_DEG = 22
MIN_VISIBILITY = 0.6
START_GESTURE_FRAMES = 3
WINDOW_NAME = "Reference (Left) | User (Right)"
# ----------------------------------------

# ---------------- MEDIAPIPE INIT ----------------
mp_pose = mp.solutions.pose
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

POSE_KWARGS = dict(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# One tracker per video stream: a single Pose instance carries tracking state
# between calls, so feeding it the webcam and the reference clip alternately
# makes each prediction pollute the other.
pose_cam_tracker = mp_pose.Pose(**POSE_KWARGS)
pose_ref_tracker = mp_pose.Pose(**POSE_KWARGS)

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# ---------------- UTILITIES ----------------
def angle(a, b, c):
    ba = np.array(a) - np.array(b)
    bc = np.array(c) - np.array(b)
    cosang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0)))

def get_point(lm, idx, h, w):
    return [lm[idx].x * w, lm[idx].y * h]

def visible(lm, idx):
    return lm[idx].visibility > MIN_VISIBILITY

# ---------------- ANGLES ----------------
ANGLE_DEFS = {
    "L_ELBOW": (11, 13, 15),
    "R_ELBOW": (12, 14, 16),
    "L_SHOULDER": (13, 11, 23),
    "R_SHOULDER": (14, 12, 24),
    "L_HIP": (11, 23, 25),
    "R_HIP": (12, 24, 26),
    "L_KNEE": (23, 25, 27),
    "R_KNEE": (24, 26, 28),
    "TORSO_L": (11, 23, 24),
    "TORSO_R": (12, 24, 23),
}

# ---------------- THUMBS UP ----------------
def is_thumbs_up(hand_landmarks):
    lm = hand_landmarks.landmark
    return (
        lm[4].y < lm[3].y and
        lm[8].y > lm[3].y and
        lm[12].y > lm[3].y
    )

# ---------------- VIDEO CAPTURE ----------------
cap_ref = cv2.VideoCapture(str(REFERENCE_VIDEO_PATH))
cap_cam = cv2.VideoCapture(0)

if not cap_ref.isOpened():
    raise IOError(f"Cannot open reference video: {REFERENCE_VIDEO_PATH}")

if not cap_cam.isOpened():
    raise IOError("Cannot open webcam (device 0)")

cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

started = False
thumb_counter = 0
angle_errors_history = deque()
combined = None

# ---------------- MAIN LOOP ----------------
while cap_cam.isOpened():

    ret_cam, frame_cam = cap_cam.read()
    if not ret_cam:
        break

    ret_ref, frame_ref = cap_ref.read()
    if not ret_ref:
        cap_ref.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret_ref, frame_ref = cap_ref.read()
        if not ret_ref:
            break

    frame_cam = cv2.flip(frame_cam, 1)
    h, w, _ = frame_cam.shape
    frame_ref = cv2.resize(frame_ref, (w, h))

    rgb_cam = cv2.cvtColor(frame_cam, cv2.COLOR_BGR2RGB)
    rgb_ref = cv2.cvtColor(frame_ref, cv2.COLOR_BGR2RGB)

    pose_cam = pose_cam_tracker.process(rgb_cam)
    pose_ref = pose_ref_tracker.process(rgb_ref)
    hand_res = hands.process(rgb_cam)

    # ---- START GESTURE ----
    if not started and hand_res.multi_hand_landmarks:
        if is_thumbs_up(hand_res.multi_hand_landmarks[0]):
            thumb_counter += 1
        else:
            thumb_counter = 0

        if thumb_counter >= START_GESTURE_FRAMES:
            started = True

    skeleton_color = (0, 0, 255)

    # ---- ANGLE COMPARISON ----
    if started and pose_cam.pose_landmarks and pose_ref.pose_landmarks:
        lm_cam = pose_cam.pose_landmarks.landmark
        lm_ref = pose_ref.pose_landmarks.landmark

        diffs = []
        for a, b, c in ANGLE_DEFS.values():
            if all(visible(lm_cam, i) and visible(lm_ref, i) for i in (a, b, c)):
                p_cam = [get_point(lm_cam, i, h, w) for i in (a, b, c)]
                p_ref = [get_point(lm_ref, i, h, w) for i in (a, b, c)]
                diffs.append(abs(angle(*p_cam) - angle(*p_ref)))

        if diffs:
            mean_diff = np.mean(diffs)
            angle_errors_history.append(mean_diff)
            if mean_diff < ANGLE_THRESHOLD_DEG:
                skeleton_color = (0, 255, 0)

    # ---- DRAW ----
    if pose_ref.pose_landmarks:
        mp_drawing.draw_landmarks(
            frame_ref, pose_ref.pose_landmarks,
            mp_pose.POSE_CONNECTIONS
        )

    if pose_cam.pose_landmarks:
        mp_drawing.draw_landmarks(
            frame_cam, pose_cam.pose_landmarks,
            mp_pose.POSE_CONNECTIONS,
            mp_drawing.DrawingSpec(color=skeleton_color, thickness=3),
            mp_drawing.DrawingSpec(color=skeleton_color, thickness=3),
        )

    if not started:
        cv2.putText(
            frame_cam,
            "Show THUMBS UP to start",
            (40, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 255),
            2,
        )

    combined = np.hstack([frame_ref, frame_cam])
    cv2.imshow(WINDOW_NAME, combined)
    cv2.resizeWindow(WINDOW_NAME, combined.shape[1], combined.shape[0])

    key = cv2.waitKey(1) & 0xFF
    if key == 27:
        break

# ---------------- FINAL SCORE ----------------
if angle_errors_history and combined is not None:
    avg_error = np.mean(angle_errors_history)
    # 0 deg of error -> 100%, error at/above the threshold -> 0%.
    score = max(0.0, 100.0 * (1.0 - avg_error / ANGLE_THRESHOLD_DEG))

    print(f"Average angle error: {avg_error:.1f} deg")
    print(f"Match Score: {score:.1f}%")

    final = combined.copy()
    cv2.putText(
        final,
        f"Match Score: {score:.1f}%",
        (50, 120),
        cv2.FONT_HERSHEY_SIMPLEX,
        2.5,
        (0, 255, 0),
        5,
    )
    cv2.imshow(WINDOW_NAME, final)
    cv2.waitKey(0)
else:
    print("No pose comparison recorded - did you show a THUMBS UP to start?")

# ---------------- CLEAN EXIT ----------------
cap_cam.release()
cap_ref.release()
pose_cam_tracker.close()
pose_ref_tracker.close()
hands.close()
cv2.destroyAllWindows()
