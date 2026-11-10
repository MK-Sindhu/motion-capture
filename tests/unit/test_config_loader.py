from __future__ import annotations

from pathlib import Path

import pytest

from motion_capture.config.loader import load_settings
from motion_capture.config.settings import CameraConfig, Settings, VeenaConfig
from motion_capture.errors import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[2]


def write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def test_defaults_without_a_config_file(tmp_path):
    assert load_settings(cwd=tmp_path) == Settings()


def test_example_file_lists_exactly_the_defaults(tmp_path):
    # Keeps motion-capture.example.toml in sync with config/settings.py.
    example = REPO_ROOT / "motion-capture.example.toml"
    settings = load_settings(example, cwd=tmp_path)
    expected_reference = REPO_ROOT / VeenaConfig().reference
    assert settings.veena.reference == expected_reference
    assert settings == Settings(
        veena=VeenaConfig(reference=expected_reference),
    )


def test_motion_capture_toml_in_cwd_is_used_automatically(tmp_path):
    write(tmp_path / "motion-capture.toml", "[camera]\nindex = 1\n")
    assert load_settings(cwd=tmp_path).camera.index == 1


def test_explicit_config_file_must_exist(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_settings(tmp_path / "missing.toml", cwd=tmp_path)


def test_flags_override_the_file_and_the_file_overrides_defaults(tmp_path):
    config = write(
        tmp_path / "c.toml",
        "[camera]\nindex = 1\n[veena]\nangle_threshold_deg = 25\n",
    )
    settings = load_settings(config, {"camera": {"index": 2}}, cwd=tmp_path)
    assert settings.camera.index == 2  # flag wins
    assert settings.veena.angle_threshold_deg == 25.0  # from the file
    assert settings.veena.countdown_sec == 3.0  # default


def test_relative_paths_in_the_file_are_relative_to_the_file(tmp_path):
    sub = tmp_path / "configs"
    sub.mkdir()
    config = write(sub / "c.toml", '[veena]\nreference = "clips/teacher.mp4"\n')
    settings = load_settings(config, cwd=tmp_path)
    assert settings.veena.reference == sub / "clips" / "teacher.mp4"


def test_resolution_list_becomes_a_tuple(tmp_path):
    config = write(tmp_path / "c.toml", "[camera]\nresolution = [640, 480]\n")
    assert load_settings(config, cwd=tmp_path).camera == CameraConfig(
        resolution=(640, 480)
    )


def test_whole_number_is_accepted_for_a_decimal_setting(tmp_path):
    config = write(tmp_path / "c.toml", "[veena]\ncountdown_sec = 5\n")
    value = load_settings(config, cwd=tmp_path).veena.countdown_sec
    assert value == 5.0
    assert isinstance(value, float)


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        ("[camra]\nindex = 1\n", r"unknown section \[camra\]"),
        ("[veena]\nangel_threshold_deg = 3\n", "unknown key 'angel_threshold_deg'"),
        ('[camera]\nindex = "one"\n', "camera.index must be a whole number"),
        ("[camera]\nindex = true\n", "camera.index must be a whole number"),
        ("[veena]\nreference_is_mirrored = 1\n", "must be true or false"),
        ("[camera]\nresolution = [640]\n", "must be a list of 2 values"),
        ("[veena]\ncountdown_sec = -1\n", "countdown_sec must be 0 or more"),
        ("[tracker]\nmax_num_hands = 3\n", "max_num_hands must be 1 or 2"),
        ("camera = 1\n", "must be a \\[section\\]"),
        ("[camera\n", "invalid TOML"),
    ],
)
def test_invalid_files_are_reported_clearly(tmp_path, toml, message):
    config = write(tmp_path / "c.toml", toml)
    with pytest.raises(ConfigError, match=message) as excinfo:
        load_settings(config, cwd=tmp_path)
    # Every message names the file it came from.
    assert str(config) in str(excinfo.value)
