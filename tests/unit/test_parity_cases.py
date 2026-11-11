"""The shared Python/website test cases are up to date.

website/tests/fixtures/parity-cases.json holds inputs and the outputs the
Python code produced for them; the website's tests must reproduce those
outputs. These tests fail if the Python code no longer produces them, i.e. the
file needs regenerating (python -m tests.parity_cases) and the website
updating to match.
"""

from __future__ import annotations

import json

from tests.parity_cases import FIXTURE_PATH, compute_expected, differences, make_inputs

REGENERATE = "Regenerate with: python -m tests.parity_cases\n"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_saved_inputs_are_the_current_inputs():
    diffs = differences(make_inputs(), _fixture()["inputs"])
    assert diffs == [], REGENERATE + "\n".join(diffs[:20])


def test_python_still_produces_the_saved_outputs():
    fixture = _fixture()
    diffs = differences(fixture["expected"], compute_expected(fixture["inputs"]))
    assert diffs == [], REGENERATE + "\n".join(diffs[:20])


def test_differences_finds_changes():
    assert differences({"a": [1.0, "x"]}, {"a": [1.0 + 1e-12, "x"]}) == []
    assert differences({"a": [1.0]}, {"a": [1.1]}) == [".a[0]: 1.1 != 1.0"]
    assert differences({"a": True}, {"a": 1}) == [".a: 1 != True"]
    assert differences({"a": 1}, {"b": 1}) == [": keys ['b'] != ['a']"]
