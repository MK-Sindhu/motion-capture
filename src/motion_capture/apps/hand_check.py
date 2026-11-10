"""Hand tracking check: no reference video, no scoring.

Shows whether MediaPipe picks up both hands and how much each finger bends,
live, so you can check camera framing and lighting before `motion-capture veena`.

On screen:
  - each detected hand as a skeleton (Left = blue, Right = orange)
  - a short trail behind every fingertip, so movement is easy to see
  - a panel per hand with one bar per finger showing how bent it is
  - at the bottom: frames per second and how often each hand was found

Press ESC to quit.
"""

from __future__ import annotations

import sys
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO

from motion_capture.config.settings import HandCheckConfig
from motion_capture.geometry.angles import finger_bends
from motion_capture.geometry.landmarks import FINGER_NAMES, FINGERTIPS
from motion_capture.rendering.colors import SIDE_COLORS
from motion_capture.rendering.draw import (
    Style,
    draw_skeleton,
    draw_trail,
    put_label_at_wrist,
)
from motion_capture.rendering.panels import draw_bend_panel, draw_tracking_status
from motion_capture.rendering.window import KEY_ESC, Window
from motion_capture.tracking.types import HAND_ROLES, SIDES, HandTracking, Side
from motion_capture.video.frames import mirror
from motion_capture.video.sources import FrameSource

WINDOW_TITLE = "Hand tracking check (ESC to quit)"

# Below this % of frames tracked, the summary suggests improving the setup.
GOOD_TRACKING_PCT = 80


@dataclass
class HandCheckResult:
    """What happened during a hand-check run."""

    frames: int
    elapsed_sec: float
    # tracked[Side.LEFT] = number of frames the left hand was found in
    tracked: dict[Side, int]
    # bend_totals[side][finger] = sum of that finger's bend over the frames the
    # hand was found in (divide by tracked[side] for the average)
    bend_totals: dict[Side, dict[str, float]]

    def tracked_pct(self, side: Side) -> float:
        return 100.0 * self.tracked[side] / self.frames if self.frames else 0.0

    def mean_bends(self, side: Side) -> dict[str, float] | None:
        """Average bend of each finger, or None if the hand was never found."""
        if not self.tracked[side]:
            return None
        return {
            f: total / self.tracked[side] for f, total in self.bend_totals[side].items()
        }

    def format_text(self) -> str:
        """The summary printed in the terminal at the end."""
        fps = self.frames / self.elapsed_sec if self.elapsed_sec > 0 else 0.0
        lines = ["", f"{self.frames} frames in {self.elapsed_sec:.1f}s ({fps:.1f} FPS)"]
        for side in SIDES:
            pct = self.tracked_pct(side)
            hint = (
                ""
                if pct >= GOOD_TRACKING_PCT
                else "  <- move the camera closer or add light on this hand"
            )
            role = HAND_ROLES[side]
            lines.append(f"{side} hand ({role}) tracked in {pct:.0f}% of frames{hint}")
        return "\n".join(lines)


def run_hand_check(
    source: FrameSource,
    tracker: HandTracking,
    window: Window,
    config: HandCheckConfig,
    *,
    clock: Callable[[], float] = time.monotonic,
    out: TextIO | None = None,
) -> HandCheckResult:
    """Run until the source ends or ESC is pressed; print and return the summary.

    source: the webcam or a video file. tracker: finds the hands.
    window: where frames are shown (OpenCVWindow, or HeadlessWindow in tests).
    """
    out = out if out is not None else sys.stdout

    frames = 0
    tracked = {side: 0 for side in SIDES}
    bend_totals = {side: {f: 0.0 for f in FINGER_NAMES} for side in SIDES}
    # trails[(side, finger)] = the last `trail_length` pixel positions of that fingertip
    trails: dict[tuple[Side, str], deque[tuple[int, int]]] = {
        (side, f): deque(maxlen=config.trail_length)
        for side in SIDES
        for f in FINGERTIPS
    }
    fps = 0.0
    last_time = clock()
    start_time = last_time

    while True:
        frame = source.read()
        if frame is None:
            break

        # Mirror view (selfie), which MediaPipe's handedness labels assume.
        # A video file is mirrored too, the same as `motion-capture veena` does.
        frame = mirror(frame)
        height, width = frame.shape[:2]
        hands = tracker.process(frame)
        frames += 1

        for side in SIDES:
            hand = hands.get(side)
            if hand is None:
                # Hand lost: forget its trails, otherwise the next time it is
                # found a line would be drawn from where it used to be.
                for f in FINGERTIPS:
                    trails[(side, f)].clear()
                draw_bend_panel(frame, side, None, config.max_bend_deg)
                continue

            tracked[side] += 1
            color = SIDE_COLORS[side]

            # Fingertip trails, drawn under the skeleton.
            for f, tip in FINGERTIPS.items():
                x, y = hand.image_points[tip]
                trail = trails[(side, f)]
                trail.append((int(x * width), int(y * height)))
                draw_trail(frame, trail, color)

            style = Style(color, thickness=2, circle_radius=3)
            draw_skeleton(frame, hand.image_points, style, style)
            put_label_at_wrist(
                frame, hand.image_points, str(side), color, dx=-25, antialiased=True
            )

            bends = finger_bends(hand.world_points)
            for f, bend in bends.items():
                bend_totals[side][f] += bend
            draw_bend_panel(frame, side, bends, config.max_bend_deg)

        # Frames per second. 1 / (time this frame took) jumps around, so blend
        # 10% of the new value into 90% of the old one for a steady number.
        now = clock()
        fps = 0.9 * fps + 0.1 / max(now - last_time, 1e-6)
        last_time = now
        draw_tracking_status(frame, fps, {s: 100 * tracked[s] / frames for s in SIDES})

        window.show(frame)
        if window.poll_key() == KEY_ESC:
            break

    result = HandCheckResult(frames, clock() - start_time, tracked, bend_totals)
    if frames:
        print(result.format_text(), file=out)
    return result
