"""Configuration loading and basic validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Union


class ConfigError(ValueError):
    """Raised when a release configuration is missing or malformed."""


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_config(path: Union[Path, str]) -> Dict[str, Any]:
    config_path = Path(path)
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration not found: {config_path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Cannot read configuration {config_path}: {exc}") from exc

    required = {
        "config_schema_version",
        "software_version",
        "validation_profile",
        "target_package_id",
        "expected_counts",
        "required_files",
        "payload_files",
        "pinned_sha256",
        "csv_headers",
        "csv_row_counts",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ConfigError(f"Configuration is missing keys: {', '.join(missing)}")

    if data["validation_profile"] not in {"public_payload", "candidate_qa"}:
        raise ConfigError(f"Unsupported validation_profile: {data['validation_profile']!r}")

    for name in ("required_files", "payload_files"):
        values = data[name]
        if not isinstance(values, list) or not values:
            raise ConfigError(f"{name} must be a non-empty list")
        if len(values) != len(set(values)):
            raise ConfigError(f"{name} contains duplicate paths")
        for value in values:
            _validate_relative_path(value, name)

    if not set(data["payload_files"]).issubset(data["required_files"]):
        raise ConfigError("payload_files must be a subset of required_files")

    for rel, digest in data["pinned_sha256"].items():
        _validate_relative_path(rel, "pinned_sha256")
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise ConfigError(f"Invalid SHA-256 for {rel}: {digest!r}")

    for rel, header in data["csv_headers"].items():
        _validate_relative_path(rel, "csv_headers")
        if not isinstance(header, list) or not header or len(header) != len(set(header)):
            raise ConfigError(f"Invalid or duplicate header fields for {rel}")

    for rel, count in data["csv_row_counts"].items():
        _validate_relative_path(rel, "csv_row_counts")
        if not isinstance(count, int) or count < 0:
            raise ConfigError(f"Invalid row count for {rel}: {count!r}")

    return data


def _validate_relative_path(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ConfigError(f"{field} contains a non-POSIX relative path: {value!r}")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.parts[0].endswith(":"):
        raise ConfigError(f"{field} contains an unsafe path: {value!r}")
