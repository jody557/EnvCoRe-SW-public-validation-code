#!/usr/bin/env python3
"""Regenerate SHA256SUMS.txt for all distributable source files except itself."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", "outputs", "dist"}
EXCLUDED_NAMES = {"SHA256SUMS.txt", ".coverage"}


def distributable_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Symlink is not distributable: {path.relative_to(ROOT)}")
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix.lower() == ".zip" or path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_checksum_file(path: Path, lines: list[str]) -> None:
    """Write a checksum register with deterministic LF endings on Python 3.9+."""

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    lines = [f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}" for path in distributable_files()]
    # Path.write_text() did not accept newline= on Python 3.9. Path.open()
    # did, and explicitly fixing LF keeps this file byte-identical on Windows
    # and POSIX systems.
    write_checksum_file(ROOT / "SHA256SUMS.txt", lines)
    print(f"Wrote {len(lines)} entries to {ROOT / 'SHA256SUMS.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
