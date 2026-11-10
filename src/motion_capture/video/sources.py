"""Opening webcams and video files, with clear errors and guaranteed cleanup.

Every source is a context manager, so the camera / file is released even if
the program stops with an error:

    with open_camera(0, (1280, 720)) as camera:
        frame = camera.read()
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType
from typing import Protocol

import cv2

from motion_capture.errors import CameraError, VideoError
from motion_capture.video.frames import Frame, as_frame

log = logging.getLogger(__name__)


class FrameSource(Protocol):
    """Anything frames can be read from: a webcam, a video file, or a fake in tests."""

    def read(self) -> Frame | None:
        """The next frame, or None when there are no more."""
        ...


class VideoSource:
    """A webcam or video file. read() gives the next frame, or None at the end."""

    def __init__(self, capture: cv2.VideoCapture, description: str) -> None:
        self._capture = capture
        # e.g. "webcam 0" or the file path; used in messages
        self.description = description

    def read(self) -> Frame | None:
        """The next frame (BGR), or None when there are no more frames."""
        ok, frame = self._capture.read()
        return as_frame(frame) if ok else None

    def rewind(self) -> None:
        """Jump back to the first frame (video files only)."""
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def close(self) -> None:
        self._capture.release()

    def __enter__(self) -> VideoSource:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def open_camera(index: int, resolution: tuple[int, int]) -> VideoSource:
    """Open webcam number `index` and ask it for `resolution` (width, height)."""
    capture = cv2.VideoCapture(index)
    if not capture.isOpened():
        capture.release()
        raise CameraError(
            f"Cannot open webcam (device {index}). Try another number with "
            "--camera, and check the terminal has camera permission "
            "(see docs/troubleshooting.md)."
        )
    width, height = resolution
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    log.info(
        "Webcam %d: asked for %dx%d, got %dx%d",
        index,
        width,
        height,
        int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    )
    return VideoSource(capture, f"webcam {index}")


def open_video(path: Path) -> VideoSource:
    """Open a video file for reading."""
    if not path.is_file():
        raise VideoError(f"Video file not found: {path}")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise VideoError(f"Cannot open video (unsupported or damaged file?): {path}")
    return VideoSource(capture, str(path))


class LoopingVideo:
    """A video file that starts again from the beginning when it ends.

    Used for the reference clip, which loops while you wait and is rewound
    when a session starts.
    """

    def __init__(self, source: VideoSource) -> None:
        self.source = source

    def read(self) -> Frame | None:
        """The next frame, looping back to the start at the end.

        None only if the video can't be read even from the start.
        """
        frame = self.source.read()
        if frame is None:
            self.source.rewind()
            frame = self.source.read()
        return frame

    def restart(self) -> Frame:
        """Rewind and return the first frame (the next read() gives the second)."""
        self.source.rewind()
        frame = self.source.read()
        if frame is None:
            raise VideoError(f"Cannot read reference video: {self.source.description}")
        return frame

    def close(self) -> None:
        self.source.close()

    def __enter__(self) -> LoopingVideo:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
