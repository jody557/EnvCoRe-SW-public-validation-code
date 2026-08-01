#!/usr/bin/env python3
"""Create a deterministic, single-root source archive."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.update_source_checksums import distributable_files, sha256

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
ARCHIVE_ROOT = f"EnvCoRe-SW-public-validation-code_v{VERSION}"
LOCAL_PATH_PATTERNS = [
    re.compile(r"(?i)C:\\Users\\[0-9]+"),
    re.compile(r"(?i)E:" + r"\\codex\\"),
    re.compile(r"(?i)God " + r"bless me"),
]


def _read_expected_sums() -> Dict[str, str]:
    path = ROOT / "SHA256SUMS.txt"
    if not path.is_file():
        raise ValueError("SHA256SUMS.txt is missing; run update_source_checksums.py first")
    result: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        if rel in result or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Malformed or duplicate checksum entry: {line!r}")
        result[rel] = digest
    return result


def _validate_source_tree(files: List[Path]) -> None:
    expected = _read_expected_sums()
    actual_paths = {path.relative_to(ROOT).as_posix() for path in files}
    if set(expected) != actual_paths:
        raise ValueError(
            f"SHA256SUMS.txt file set is stale; missing={sorted(actual_paths - set(expected))}, extra={sorted(set(expected) - actual_paths)}"
        )
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if expected[rel] != sha256(path):
            raise ValueError(f"SHA256SUMS.txt is stale for {rel}")
        if any(part in {".git", "__pycache__", "outputs", "dist"} for part in path.relative_to(ROOT).parts):
            raise ValueError(f"Excluded build path reached archive: {rel}")
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in LOCAL_PATH_PATTERNS:
            if pattern.search(text):
                raise ValueError(f"Local workspace path found in {rel}")


def build_archive(output: Path) -> str:
    source_files = distributable_files()
    _validate_source_tree(source_files)
    archive_files = source_files + [ROOT / "SHA256SUMS.txt"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(archive_files, key=lambda item: item.relative_to(ROOT).as_posix()):
            rel = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{rel}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.flag_bits |= 0x800
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return sha256(output)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    digest = build_archive(args.out)
    print(f"Archive: {args.out.resolve()}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
