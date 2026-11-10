"""Shared pytest fixtures (helpers live in tests/helpers.py)."""

from __future__ import annotations

import pytest

from tests.helpers import FakeClock


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
