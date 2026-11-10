"""Bigger on-screen elements: the finger-bend panel, status lines, score overlays."""

from __future__ import annotations

from collections.abc import Mapping

import cv2
import numpy as np

from motion_capture.rendering.colors import GREEN, GREY, RED, SIDE_COLORS, WHITE, YELLOW
from motion_capture.rendering.draw import put_text
from motion_capture.scoring.report import Report
from motion_capture.tracking.types import HAND_ROLES, Side
from motion_capture.video.frames import Frame

# ---------------------------------------------------------------- hand check

# Size of the finger-bend panel, in pixels:
#   PANEL_W / PANEL_H = panel width / height
#   BAR_X = how far from the panel's left edge the bars start (room for the name)
#   BAR_W = length of a completely full bar
PANEL_W, PANEL_H, BAR_X, BAR_W = 300, 190, 90, 150


def draw_bend_panel(
    frame: Frame, side: Side, bends: Mapping[str, float] | None, max_bend_deg: float
) -> None:
    """Per-finger bend bars for one hand, top-left (Left) or top-right (Right).

    bends is {finger: degrees}, or None if the hand wasn't found (the panel
    then says NOT DETECTED). On a frame too narrow for two panels side by
    side, Right goes below Left.
    """
    width = frame.shape[1]
    side_by_side = width >= 2 * PANEL_W + 30
    # (x0, y0) = the panel's top-left corner; in images y = 0 is the TOP.
    x0 = 10 if side is Side.LEFT or not side_by_side else width - PANEL_W - 10
    y0 = 10 if side is Side.LEFT or side_by_side else PANEL_H + 20

    # A view onto the panel's rectangle (not a copy): darkening it darkens the frame.
    region = frame[y0 : y0 + PANEL_H, x0 : x0 + PANEL_W]
    region[:] = (region * 0.35).astype(np.uint8)

    color = SIDE_COLORS[side]
    title = f"{side} hand ({HAND_ROLES[side]})"
    put_text(frame, title, (x0 + 10, y0 + 25), 0.65, color, 2, antialiased=True)

    if bends is None:
        put_text(
            frame, "NOT DETECTED", (x0 + 10, y0 + 100), 0.9, RED, 2, antialiased=True
        )
        return

    # One row per finger: name, bar, number. Rows are 27 px apart.
    for i, (finger, bend) in enumerate(bends.items()):
        y = y0 + 55 + i * 27
        put_text(frame, finger, (x0 + 10, y), 0.6, WHITE, 1, antialiased=True)
        fill = int(np.clip(bend, 0, max_bend_deg) / max_bend_deg * BAR_W)
        # Grey outline of the full bar, then the coloured part (thickness -1 = filled)
        cv2.rectangle(frame, (x0 + BAR_X, y - 14), (x0 + BAR_X + BAR_W, y), GREY, 1)
        cv2.rectangle(frame, (x0 + BAR_X, y - 14), (x0 + BAR_X + fill, y), color, -1)
        value_org = (x0 + BAR_X + BAR_W + 10, y)
        put_text(frame, f"{bend:3.0f}", value_org, 0.6, WHITE, 1, antialiased=True)


def draw_tracking_status(
    frame: Frame, fps: float, tracked_pct: Mapping[Side, float]
) -> None:
    """Bottom line: frames per second and how often each hand has been found."""
    height = frame.shape[0]
    text = (
        f"FPS {fps:4.1f}   tracked so far: Left {tracked_pct[Side.LEFT]:3.0f}%"
        f"  Right {tracked_pct[Side.RIGHT]:3.0f}%"
    )
    put_text(frame, text, (10, height - 15), 0.65, WHITE, 2, antialiased=True)


# ---------------------------------------------------------------- veena match


def draw_waiting_message(frame: Frame) -> None:
    put_text(frame, "Show THUMBS UP (or press SPACE) to start", (40, 60))


def draw_countdown(frame: Frame, seconds_left: int) -> None:
    """'Hands on the veena...' plus a big number in the middle."""
    height, width = frame.shape[:2]
    put_text(frame, "Hands on the veena...", (40, 60))
    put_text(
        frame, str(seconds_left), (width // 2 - 40, height // 2 + 40), 4, YELLOW, 8
    )


def draw_no_hands_warning(frame: Frame) -> None:
    put_text(
        frame,
        "No hands visible - move closer / improve lighting",
        (40, 60),
        0.8,
        RED,
    )


def draw_final_scores(frame: Frame, report: Report) -> None:
    """The overall score in big letters, then one line per hand."""
    y = 220
    for hand in report.hands:
        text = f"{hand.side} hand ({HAND_ROLES[hand.side]}): {hand.score_pct:.1f}%"
        put_text(frame, text, (50, y), 1.2, GREEN, 3)
        y += 55
    put_text(frame, f"Match Score: {report.score_pct:.1f}%", (50, 140), 2.5, GREEN, 5)
