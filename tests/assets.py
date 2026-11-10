"""Sample clips for the integration tests, built from MediaPipe's public sample images.

The two images are downloaded once (and checked against their SHA-256), then
turned into short lossless clips, the same way tests/golden/golden.json was
produced from the original scripts. Lossless (FFV1) matters: every decoded
frame is exactly the source image, so the numbers are reproducible.

Files are cached in .cache/test-assets/ (or $MOTION_CAPTURE_TEST_ASSETS).
"""

from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = Path(
    os.environ.get("MOTION_CAPTURE_TEST_ASSETS", REPO_ROOT / ".cache" / "test-assets")
)

IMAGES = {
    "woman_hands": (
        "https://storage.googleapis.com/mediapipe-tasks/hand_landmarker/woman_hands.jpg",
        "70cbeb38e198c9862202e0979c21a99b40ca980d3e7b250176c85b1636a40f12",
    ),
    "pointing_up": (
        "https://storage.googleapis.com/mediapipe-tasks/gesture_recognizer/pointing_up.jpg",
        "f4a701316b63dd8fa56e622f2b3042766369ccc189f0d89513f803cd985b993b",
    ),
}
# Must match "frames_per_clip" in tests/golden/golden.json
FRAMES_PER_CLIP = 40
FPS = 30


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image(name: str) -> Path:
    """Path to a sample image, downloading it the first time."""
    url, expected = IMAGES[name]
    path = CACHE_DIR / f"{name}.jpg"
    if path.is_file() and _sha256(path) == expected:
        return path
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https URL
        tmp.write_bytes(response.read())
    if _sha256(tmp) != expected:
        tmp.unlink()
        raise OSError(f"{url} changed (SHA-256 mismatch); update tests/assets.py")
    tmp.replace(path)
    return path


def clip(name: str, mirrored: bool = False) -> Path:
    """A lossless clip repeating the sample image (optionally mirrored)."""
    path = CACHE_DIR / f"{name}{'_mirrored' if mirrored else ''}.mkv"
    if path.is_file():
        return path
    img = cv2.imread(str(image(name)))
    if mirrored:
        img = cv2.flip(img, 1)
    height, width = img.shape[:2]
    tmp = path.with_name(path.stem + ".part.mkv")
    writer = cv2.VideoWriter(
        str(tmp), cv2.VideoWriter_fourcc(*"FFV1"), FPS, (width, height)
    )
    if not writer.isOpened():
        raise OSError("OpenCV cannot write FFV1 video on this system")
    for _ in range(FRAMES_PER_CLIP):
        writer.write(img)
    writer.release()
    tmp.replace(path)
    return path


def all_clips() -> dict[str, Path]:
    """{"woman_hands": ..., "woman_hands_mirrored": ..., "pointing_up": ..., ...}"""
    clips = {}
    for name in IMAGES:
        clips[name] = clip(name)
        clips[f"{name}_mirrored"] = clip(name, mirrored=True)
    return clips
