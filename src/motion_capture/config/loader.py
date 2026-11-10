"""Build the final Settings: defaults < TOML file < command-line overrides.

A TOML file looks like this (see motion-capture.example.toml for every key):

    [camera]
    index = 1

    [veena]
    angle_threshold_deg = 25

Rules:
  - The file is `--config PATH` if given, otherwise ./motion-capture.toml if
    it exists, otherwise none (defaults only).
  - Unknown sections or keys are errors, so a typo like `angel_threshold_deg`
    is reported instead of silently ignored.
  - Values must have the right type (an int where an int is expected, ...).
  - Relative paths in the file are relative to the file's own folder.
"""

from __future__ import annotations

import dataclasses
import sys
import typing
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from motion_capture.config.settings import Settings
from motion_capture.errors import ConfigError

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on Python 3.9/3.10 in CI
    import tomli as tomllib

DEFAULT_CONFIG_FILE = Path("motion-capture.toml")

# Overrides look like {"camera": {"index": 1}, "veena": {"countdown_sec": 0}}.
Overrides = Mapping[str, Mapping[str, Any]]


def find_config_file(explicit: Path | None, cwd: Path) -> Path | None:
    """The explicit config file (which must exist), else ./motion-capture.toml."""
    if explicit is not None:
        if not explicit.is_file():
            raise ConfigError(f"Config file not found: {explicit}")
        return explicit
    default = cwd / DEFAULT_CONFIG_FILE
    return default if default.is_file() else None


def read_toml(path: Path) -> dict[str, Any]:
    """Parse a TOML file, turning syntax errors into ConfigError."""
    try:
        with path.open("rb") as f:
            data: dict[str, Any] = tomllib.load(f)
            return data
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML: {exc}") from exc


def load_settings(
    config_file: Path | None = None,
    overrides: Overrides | None = None,
    *,
    cwd: Path | None = None,
) -> Settings:
    """Settings from the defaults, then the config file, then `overrides`.

    config_file: an explicit --config path (must exist), or None to look for
        ./motion-capture.toml in `cwd`.
    overrides: values from command-line flags; only flags the user actually
        gave should be included.
    """
    cwd = cwd if cwd is not None else Path.cwd()
    path = find_config_file(config_file, cwd)

    sections: dict[str, dict[str, Any]] = {}
    if path is not None:
        file_data = read_toml(path)
        _merge(sections, _from_file(file_data, source=str(path), base_dir=path.parent))
    if overrides:
        _merge(sections, {name: dict(values) for name, values in overrides.items()})

    return build_settings(sections, source=str(path) if path else "settings")


def build_settings(sections: Mapping[str, Mapping[str, Any]], source: str) -> Settings:
    """Create Settings from {section: {key: value}}, checking names and types."""
    groups: dict[str, Any] = {}
    section_types = _section_types()
    for section, values in sections.items():
        if section not in section_types:
            raise ConfigError(
                f"{source}: unknown section [{section}] "
                f"(valid: {', '.join(sorted(section_types))})"
            )
        group_cls = section_types[section]
        hints = typing.get_type_hints(group_cls)
        valid_keys = {f.name for f in dataclasses.fields(group_cls)}
        kwargs = {}
        for key, value in values.items():
            if key not in valid_keys:
                raise ConfigError(
                    f"{source}: unknown key '{key}' in [{section}] "
                    f"(valid: {', '.join(sorted(valid_keys))})"
                )
            kwargs[key] = _coerce(value, hints[key], f"{section}.{key}", source)
        try:
            # The dataclass checks ranges (e.g. countdown_sec >= 0) itself.
            groups[section] = group_cls(**kwargs)
        except ConfigError as exc:
            raise ConfigError(f"{source}: {exc}") from exc
    return Settings(**groups)


# ---------------------------------------------------------------- helpers


def _section_types() -> dict[str, type]:
    """{"camera": CameraConfig, "tracker": TrackerConfig, ...} from Settings."""
    hints = typing.get_type_hints(Settings)
    return {f.name: hints[f.name] for f in dataclasses.fields(Settings)}


def _from_file(
    data: Mapping[str, Any], source: str, base_dir: Path
) -> dict[str, dict[str, Any]]:
    """Check the file's top-level shape and make its relative paths absolute."""
    sections: dict[str, dict[str, Any]] = {}
    section_types = _section_types()
    for section, values in data.items():
        if not isinstance(values, dict):
            raise ConfigError(
                f"{source}: '{section}' must be a [section], not a single value"
            )
        if section in section_types:
            hints = typing.get_type_hints(section_types[section])
            values = {
                key: (base_dir / value)
                if hints.get(key) is Path and isinstance(value, str)
                else value
                for key, value in values.items()
            }
        sections[section] = dict(values)
    return sections


def _merge(
    into: dict[str, dict[str, Any]], new: Mapping[str, Mapping[str, Any]]
) -> None:
    for section, values in new.items():
        into.setdefault(section, {}).update(values)


def _coerce(value: Any, expected: Any, name: str, source: str) -> Any:
    """Check `value` against the type annotation `expected`, converting where safe."""

    def fail(what: str) -> ConfigError:
        return ConfigError(f"{source}: {name} must be {what}, got {value!r}")

    # bool is checked first because in Python True/False are also ints.
    if expected is bool:
        if not isinstance(value, bool):
            raise fail("true or false")
        return value
    if expected is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise fail("a whole number")
        return value
    if expected is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise fail("a number")
        return float(value)
    if expected is Path:
        if isinstance(value, Path):
            return value
        if isinstance(value, str):
            return Path(value)
        raise fail("a path (text)")
    if typing.get_origin(expected) is tuple:
        item_types = typing.get_args(expected)
        if not isinstance(value, (list, tuple)) or len(value) != len(item_types):
            raise fail(f"a list of {len(item_types)} values")
        return tuple(
            _coerce(item, item_type, name, source)
            for item, item_type in zip(value, item_types)
        )
    raise TypeError(
        f"Unsupported setting type {expected!r} for {name}"
    )  # pragma: no cover
