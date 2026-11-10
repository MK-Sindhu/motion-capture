from __future__ import annotations

import pytest

from motion_capture.session.state import Phase, Session


def test_waits_until_started(clock):
    session = Session(countdown_sec=3, clock=clock)
    clock.advance(60)
    assert session.tick() is Phase.WAITING
    assert session.seconds_left() == 0.0


def test_countdown_then_running(clock):
    session = Session(countdown_sec=3, clock=clock)
    session.start_countdown()
    assert session.phase is Phase.COUNTDOWN
    assert session.seconds_left() == pytest.approx(3.0)

    clock.advance(2.5)
    assert session.tick() is Phase.COUNTDOWN
    assert session.seconds_left() == pytest.approx(0.5)

    clock.advance(0.5)
    assert session.tick() is Phase.RUNNING
    assert session.seconds_left() == 0.0


def test_zero_countdown_runs_on_the_next_tick(clock):
    session = Session(countdown_sec=0, clock=clock)
    session.start_countdown()
    assert session.phase is Phase.COUNTDOWN
    assert session.tick() is Phase.RUNNING


def test_cannot_start_twice(clock):
    session = Session(countdown_sec=1, clock=clock)
    session.start_countdown()
    with pytest.raises(RuntimeError):
        session.start_countdown()
