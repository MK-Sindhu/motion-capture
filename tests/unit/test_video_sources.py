from __future__ import annotations

import cv2
import numpy as np
import pytest

from motion_capture.errors import CameraError, VideoError
from motion_capture.video import sources
from motion_capture.video.sources import LoopingVideo, open_camera, open_video


@pytest.fixture
def numbered_clip(tmp_path):
    """A 3-frame lossless clip whose frames are filled with 0, 1 and 2."""
    path = tmp_path / "numbered.mkv"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"FFV1"), 30, (32, 24))
    for value in range(3):
        writer.write(np.full((24, 32, 3), value, dtype=np.uint8))
    writer.release()
    return path


def _value(frame):
    return int(frame[0, 0, 0])


def test_video_file_reads_every_frame_then_none(numbered_clip):
    with open_video(numbered_clip) as video:
        assert [_value(video.read()) for _ in range(3)] == [0, 1, 2]
        assert video.read() is None


def test_looping_video_starts_again_at_the_end(numbered_clip):
    with LoopingVideo(open_video(numbered_clip)) as video:
        assert [_value(video.read()) for _ in range(7)] == [0, 1, 2, 0, 1, 2, 0]


def test_restart_returns_the_first_frame_and_continues_from_the_second(numbered_clip):
    with LoopingVideo(open_video(numbered_clip)) as video:
        video.read()
        video.read()
        assert _value(video.restart()) == 0
        assert _value(video.read()) == 1


def test_missing_video_file(tmp_path):
    with pytest.raises(VideoError, match="not found"):
        open_video(tmp_path / "nope.mp4")


def test_unreadable_video_file(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_text("not a video")
    with pytest.raises(VideoError, match="Cannot open video"):
        open_video(bad)


class _ClosedCapture:
    released = False

    def __init__(self, *args):
        pass

    def isOpened(self):  # noqa: N802 - mirrors cv2's method name
        return False

    def release(self):
        _ClosedCapture.released = True


def test_camera_that_cannot_open_raises_and_is_released(monkeypatch):
    monkeypatch.setattr(sources.cv2, "VideoCapture", _ClosedCapture)
    with pytest.raises(CameraError, match=r"device 3.*--camera"):
        open_camera(3, (1280, 720))
    assert _ClosedCapture.released
