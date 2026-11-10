from __future__ import annotations

import numpy as np

from motion_capture.config.settings import TrackerConfig
from motion_capture.rendering.window import KEY_ESC, KEY_SPACE, HeadlessWindow
from motion_capture.tracking.hands import HandTracker


def test_headless_window_plays_back_scripted_keys_and_keeps_frames():
    window = HeadlessWindow(keys={0: KEY_SPACE, 2: KEY_ESC})
    assert [window.poll_key() for _ in range(4)] == [KEY_SPACE, None, KEY_ESC, None]

    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    window.show(frame)
    frame[:] = 255  # the window keeps its own copy
    assert window.frames_shown == 1
    assert window.last_frame is not None and window.last_frame.max() == 0


def test_tracker_finds_no_hands_in_an_empty_frame():
    with HandTracker(TrackerConfig()) as tracker:
        blank = np.zeros((240, 320, 3), dtype=np.uint8)
        assert tracker.detect(blank) == []
        assert tracker.process(blank) == {}
