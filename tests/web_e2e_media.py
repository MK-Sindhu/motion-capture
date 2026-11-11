"""Test videos for the website's browser tests (website/e2e/).

    python -m tests.web_e2e_media website/e2e/media

From MediaPipe's public sample picture of two hands (downloaded and checked by
tests/assets.py), writes:

  hands.y4m   raw frames for Chrome's fake webcam
              (--use-file-for-fake-video-capture; Chrome loops it)
  hands.webm  the same picture as a video file, for the reference-video picker

Only OpenCV and numpy are needed, not MediaPipe.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

from tests import assets

FRAMES = 30
FPS = 30


def write_media(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(assets.image("woman_hands")))
    if image is None:
        raise OSError("cannot read the sample picture")
    # Video with 4:2:0 colour needs an even width and height.
    height, width = (n - n % 2 for n in image.shape[:2])
    image = image[:height, :width]

    y4m = out_dir / "hands.y4m"
    i420 = cv2.cvtColor(image, cv2.COLOR_BGR2YUV_I420)
    with y4m.open("wb") as f:
        f.write(f"YUV4MPEG2 W{width} H{height} F{FPS}:1 Ip A1:1 C420jpeg\n".encode())
        for _ in range(FRAMES):
            f.write(b"FRAME\n" + i420.tobytes())

    webm = out_dir / "hands.webm"
    vp8 = cv2.VideoWriter_fourcc(*"VP80")
    writer = cv2.VideoWriter(str(webm), vp8, FPS, (width, height))
    if not writer.isOpened():
        raise OSError("this OpenCV can't write WebM (VP8) video")
    for _ in range(2 * FRAMES):
        writer.write(image)
    writer.release()
    return [y4m, webm]


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("website/e2e/media")
    for path in write_media(target):
        print(f"wrote {path}")
