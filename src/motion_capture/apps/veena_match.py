"""Veena finger matching: your webcam next to a reference video, scored.

Compares the finger joint angles of both hands frame by frame:
  - Left hand  = fretting hand (presses / pulls the strings on the neck)
  - Right hand = plucking hand (index/middle on the main strings, pinky on the
                 tala strings)

A session goes:
  1. WAITING   - the reference loops. Show a thumbs up (or press SPACE).
  2. COUNTDOWN - the reference rewinds and pauses while you put your hand
                 back on the veena.
  3. RUNNING   - every frame, each of your hands is compared with the same
                 hand in the reference, and drawn green (close) or red (far off).
  4. ESC       - the match score, a score per hand and an error per finger.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import TextIO

import numpy as np

from motion_capture.config.settings import VeenaConfig
from motion_capture.gestures.thumbs_up import ThumbsUpDetector
from motion_capture.rendering.colors import GREEN, RED, WHITE
from motion_capture.rendering.draw import Style, draw_skeleton, put_label_at_wrist
from motion_capture.rendering.panels import (
    draw_countdown,
    draw_final_scores,
    draw_no_hands_warning,
    draw_waiting_message,
)
from motion_capture.rendering.window import KEY_ESC, KEY_SPACE, Window
from motion_capture.scoring.compare import finger_errors, hand_error
from motion_capture.scoring.report import Report, ScoreAccumulator
from motion_capture.session.state import Phase, Session
from motion_capture.tracking.types import SIDES, HandTracking, Side
from motion_capture.video.frames import Frame, mirror, resize
from motion_capture.video.sources import FrameSource, LoopingVideo

WINDOW_TITLE = "Reference (Left) | User (Right)"

NO_COMPARISON_MESSAGE = (
    "No finger comparison recorded - did you start with a THUMBS UP (or SPACE), "
    "and were your hands visible in both videos?"
)


def run_veena_match(
    camera: FrameSource,
    reference: LoopingVideo,
    user_tracker: HandTracking,
    reference_tracker: HandTracking,
    window: Window,
    config: VeenaConfig,
    *,
    clock: Callable[[], float] = time.monotonic,
    out: TextIO | None = None,
) -> Report | None:
    """Run a session until the camera stops or ESC is pressed.

    Prints the summary, shows the final score screen, and returns the report
    (None if no hand was ever compared).

    Use a separate tracker for each stream (see tracking/hands.py).
    """
    out = out if out is not None else sys.stdout

    session = Session(config.countdown_sec, clock)
    thumbs_up = ThumbsUpDetector(config.start_gesture_frames)
    scores = ScoreAccumulator()
    # The reference's first frame, shown frozen during the countdown
    held_reference: Frame | None = None
    # The last side-by-side image shown (reused for the final score screen)
    combined: Frame | None = None

    def start_countdown() -> None:
        nonlocal held_reference
        held_reference = reference.restart()
        session.start_countdown()

    while True:
        user_frame = camera.read()
        if user_frame is None:
            break

        if session.phase is Phase.COUNTDOWN and held_reference is not None:
            ref_frame = held_reference.copy()
        else:
            next_ref = reference.read()
            if next_ref is None:
                break
            ref_frame = next_ref

        # Both views are shown and tracked as a mirror. Tracking one stream
        # mirrored and the other not would show the model a left hand in one
        # and a (mirror-image) right hand in the other, and its estimates for
        # the two differ by several degrees even for an identical pose.
        user_frame = mirror(user_frame)
        if not config.reference_is_mirrored:
            ref_frame = mirror(ref_frame)
        height, width = user_frame.shape[:2]

        # Track the reference at its own size so its hands aren't stretched;
        # the points are fractions of the image size, so they still line up
        # after resizing it to match the webcam for display.
        ref_hands = reference_tracker.process(ref_frame)
        user_hands = user_tracker.process(user_frame)
        ref_frame = resize(ref_frame, (width, height))

        # ---- start gesture / countdown ----
        if session.phase is Phase.WAITING:
            if thumbs_up.update(hand.image_points for hand in user_hands.values()):
                start_countdown()
        elif session.phase is Phase.COUNTDOWN:
            session.tick()

        # ---- compare ----
        # frame_error[side] = that hand's error in THIS frame (colour + label)
        frame_error: dict[Side, float] = {}
        if session.phase is Phase.RUNNING:
            scores.start_frame()
            for side in SIDES:
                # Only a hand found in BOTH videos this frame can be compared
                if side in user_hands and side in ref_hands:
                    per_finger = finger_errors(user_hands[side], ref_hands[side])
                    frame_error[side] = hand_error(per_finger)
                    scores.add(side, per_finger, frame_error[side])

        # ---- draw ----
        for side, hand in ref_hands.items():
            draw_skeleton(ref_frame, hand.image_points)
            put_label_at_wrist(ref_frame, hand.image_points, str(side), WHITE)

        for side, hand in user_hands.items():
            err = frame_error.get(side)
            # Green if close to the reference this frame; red otherwise, or
            # when there was nothing to compare (e.g. before starting).
            ok = err is not None and err < config.angle_threshold_deg
            color = GREEN if ok else RED
            style = Style(color, thickness=2, circle_radius=3)
            draw_skeleton(user_frame, hand.image_points, style, style)
            label = str(side) if err is None else f"{side} {err:.0f} deg"
            put_label_at_wrist(user_frame, hand.image_points, label, color)

        if session.phase is Phase.WAITING:
            draw_waiting_message(user_frame)
        elif session.phase is Phase.COUNTDOWN:
            draw_countdown(user_frame, int(np.ceil(session.seconds_left())))
        elif not user_hands:
            draw_no_hands_warning(user_frame)

        # Reference on the left, you on the right
        combined = np.hstack([ref_frame, user_frame])
        window.show(combined)

        key = window.poll_key()
        if key == KEY_ESC:
            break
        if key == KEY_SPACE and session.phase is Phase.WAITING:
            start_countdown()

    report = scores.report(config.angle_threshold_deg)
    if report is None or combined is None:
        print(NO_COMPARISON_MESSAGE, file=out)
        return report

    print(report.format_text(), file=out)
    final = combined.copy()
    draw_final_scores(final, report)
    window.show(final)
    window.wait_for_key()
    return report
