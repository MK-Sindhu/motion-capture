"""Fixtures for the integration tests: sample clips and the golden numbers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests import assets

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "golden" / "golden.json"
GOLDEN = json.loads(GOLDEN_PATH.read_text())

# How close (degrees / percent) the restructured code must be to the numbers
# the original scripts produced. The inputs are lossless, so on the machine the
# goldens were captured on the match is exact; the margin allows for tiny
# floating-point differences between CPUs.
TOLERANCE = 0.05


@pytest.fixture(scope="session")
def clips() -> dict[str, Path]:
    assert GOLDEN["frames_per_clip"] == assets.FRAMES_PER_CLIP
    try:
        return assets.all_clips()
    except OSError as exc:  # offline, or the codec is missing
        pytest.skip(f"integration test assets unavailable: {exc}")


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    # The CLI reads ./motion-capture.toml if present; don't let a personal one
    # in the repo change test results.
    monkeypatch.chdir(tmp_path)
