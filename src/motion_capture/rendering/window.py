"""The display window, behind a small interface so programs can also run headless.

OpenCVWindow is the real on-screen window. HeadlessWindow shows nothing:
it keeps the frames it is given and plays back scripted key presses, which
is how the integration tests drive the programs without a screen.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType
from typing import Protocol

import cv2

from motion_capture.video.frames import Frame

KEY_ESC = 27
KEY_SPACE = 32


class Window(Protocol):
    def show(self, frame: Frame) -> None:
        """Display a frame."""
        ...

    def poll_key(self) -> int | None:
        """The key pressed since the last call (waits ~1 ms), or None."""
        ...

    def wait_for_key(self) -> None:
        """Block until any key is pressed (used for the final score screen)."""
        ...

    def close(self) -> None: ...


class OpenCVWindow:
    """A resizable OpenCV window.

    max_width: if given, the window is sized once, on the first frame, so it
    is at most this many pixels wide (the image is scaled to fit).
    """

    def __init__(self, title: str, max_width: int | None = None) -> None:
        self.title = title
        self.max_width = max_width
        self._sized = False
        # WINDOW_NORMAL = the window can be resized with the mouse
        cv2.namedWindow(title, cv2.WINDOW_NORMAL)

    def show(self, frame: Frame) -> None:
        cv2.imshow(self.title, frame)
        if self.max_width is not None and not self._sized:
            height, width = frame.shape[:2]
            scale = min(1.0, self.max_width / width)
            cv2.resizeWindow(self.title, int(width * scale), int(height * scale))
            self._sized = True

    def poll_key(self) -> int | None:
        # waitKey(1) waits up to 1 ms for a key (and lets the window redraw).
        # "& 0xFF" keeps the last 8 bits of the key code; 0xFF means no key.
        key = cv2.waitKey(1) & 0xFF
        return None if key == 0xFF else key

    def wait_for_key(self) -> None:
        cv2.waitKey(0)

    def close(self) -> None:
        cv2.destroyWindow(self.title)
        # Let the GUI process the close (needed on some platforms).
        cv2.waitKey(1)

    def __enter__(self) -> OpenCVWindow:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class HeadlessWindow:
    """Shows nothing. keys = {n: key} presses `key` on the n-th poll (0 = first)."""

    def __init__(self, keys: Mapping[int, int] | None = None) -> None:
        self.keys = dict(keys or {})
        self.frames_shown = 0
        self.last_frame: Frame | None = None
        self._polls = 0

    def show(self, frame: Frame) -> None:
        self.frames_shown += 1
        self.last_frame = frame.copy()

    def poll_key(self) -> int | None:
        key = self.keys.get(self._polls)
        self._polls += 1
        return key

    def wait_for_key(self) -> None:
        return None

    def close(self) -> None:
        return None

    def __enter__(self) -> HeadlessWindow:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
