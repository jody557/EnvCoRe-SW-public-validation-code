#!/usr/bin/env python3
"""Create a deterministic, cross-platform ZIP with POSIX entry paths."""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional, Sequence


FIXED_TIMESTAMP = (2026, 7, 13, 0, 0, 0)
EXCLUDED_DIRECTORY_NAMES = {".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "outputs"}
EXCLUDED_FILE_NAMES = {".coverage", ".DS_Store", "Thumbs.db"}
EXCLUDED_FILE_SUFFIXES = {".pyc", ".pyo"}
PUBLIC_SNAPSHOT_PATHS = {
    ".github/workflows/tests.yml",
    ".gitignore",
    "CHANGELOG.md",
    "CITATION.cff",
    "config/release_config.yaml",
    "docs/local_validation_note.md",
    "docs/release_linkage.md",
    "LICENSE",
    "README.md",
    "RELEASE_NOTES_v1.1.0.md",
    "requirements.txt",
    "scripts/create_release_zip.py",
    "scripts/envcore_sw_public_release_tools.py",
    "scripts/summarize_dual_reviewer_qa.py",
    "tests/__init__.py",
    "tests/common.py",
    "tests/test_documentation_consistency.py",
    "tests/test_identifiers.py",
    "tests/test_manifest.py",
    "tests/test_qa_status.py",
    "tests/test_release_files.py",
    "tests/test_schema.py",
    "tests/test_unit_helpers.py",
    "tests/test_v5_corrections.py",
    "zenodo/code_citation_bibtex_template.bib",
    "zenodo/dataset_citation_bibtex_template.bib",
    "zenodo/version_doi_mapping_template.csv",
    "zenodo/zenodo_code_metadata_template.json",
    "zenodo/ZENODO_CODE_UPDATE_INSTRUCTIONS.md",
    "zenodo/zenodo_dataset_metadata_template.json",
    "zenodo/ZENODO_DATASET_UPDATE_INSTRUCTIONS.md",
}


def _is_generated_or_local_artifact(relative: Path) -> bool:
    return (
        any(part in EXCLUDED_DIRECTORY_NAMES for part in relative.parts[:-1])
        or relative.name in EXCLUDED_FILE_NAMES
        or relative.suffix.lower() in EXCLUDED_FILE_SUFFIXES
    )


def _git_tracked_paths(source: Path) -> Optional[list[Path]]:
    if not (source / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(source), "ls-files", "-z"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"Cannot enumerate tracked release files: {exc}") from exc
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Cannot enumerate tracked release files: {message}")
    paths = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode("utf-8"))
        candidate = source / relative
        if not candidate.is_file():
            raise ValueError(f"Tracked release file is missing from the working tree: {relative}")
        paths.append(candidate)
    return paths


def _fallback_path_is_public(relative: Path) -> bool:
    return relative.as_posix() in PUBLIC_SNAPSHOT_PATHS


def release_files(source: Path) -> list[Path]:
    """Return source files that belong in a clean repository release archive."""

    files = []
    tracked = _git_tracked_paths(source)
    candidates = tracked if tracked is not None else list(source.rglob("*"))
    unexpected = []
    for path in candidates:
        relative = path.relative_to(source)
        if not path.is_file():
            continue
        if _is_generated_or_local_artifact(relative):
            continue
        if tracked is None and not _fallback_path_is_public(relative):
            unexpected.append(relative.as_posix())
            continue
        files.append(path)
    if unexpected:
        raise ValueError(
            "Unexpected files outside the public source allowlist: " + ", ".join(sorted(unexpected))
        )
    return sorted(
        files,
        key=lambda path: path.relative_to(source).as_posix(),
    )


def build_zip(source: Path, output: Path) -> None:
    source = source.resolve()
    output = output.resolve()
    if not source.is_dir():
        raise NotADirectoryError(source)
    if output.exists():
        raise FileExistsError(f"Output ZIP already exists: {output}")
    if output.parent == source or source in output.parents:
        raise ValueError("Output ZIP must not be created inside the source directory.")
    files = release_files(source)
    if not files:
        raise ValueError(f"Source directory contains no files: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            if path.is_symlink():
                raise ValueError(f"Symbolic links are not allowed in release ZIPs: {path}")
            relative = path.relative_to(source).as_posix()
            if relative.startswith("/") or ".." in Path(relative).parts or ":" in Path(relative).parts[0]:
                raise ValueError(f"Unsafe archive path: {relative}")
            info = zipfile.ZipInfo(relative, FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a deterministic EnvCoRe-SW release ZIP")
    parser.add_argument("source", type=Path, help="Directory whose contents become the ZIP root")
    parser.add_argument("output", type=Path, help="New ZIP path; must not exist")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        build_zip(args.source, args.output)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
