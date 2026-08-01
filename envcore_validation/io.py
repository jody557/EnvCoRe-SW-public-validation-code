"""Safe opening of extracted or ZIP release candidates."""

from __future__ import annotations

import contextlib
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterator, List, Union


class ReleaseInputError(ValueError):
    """Raised when a release input cannot be opened safely."""


_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_MAX_MEMBERS = 10_000
_MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024


@contextlib.contextmanager
def open_release(source: Union[Path, str]) -> Iterator[Path]:
    """Yield a detected release root from a directory or a safely extracted ZIP."""

    path = Path(source)
    if path.is_dir():
        yield _detect_root(path)
        return
    if not path.is_file():
        raise ReleaseInputError(f"Release input not found: {path}")
    if path.suffix.lower() != ".zip":
        raise ReleaseInputError("Release input must be a directory or .zip file")

    temp = Path(tempfile.mkdtemp(prefix="envcore_release_"))
    try:
        _extract_zip_safely(path, temp)
        yield _detect_root(temp)
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def inspect_zip(path: Union[Path, str]) -> List[str]:
    """Validate ZIP member safety and return normalized file-member paths."""

    archive = Path(path)
    try:
        with zipfile.ZipFile(archive) as zf:
            return _validate_members(zf)
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ReleaseInputError(f"Cannot open ZIP {archive}: {exc}") from exc


def _validate_members(zf: zipfile.ZipFile) -> list[str]:
    infos = zf.infolist()
    if len(infos) > _MAX_MEMBERS:
        raise ReleaseInputError(f"ZIP contains too many members: {len(infos)}")
    total = sum(info.file_size for info in infos)
    if total > _MAX_UNCOMPRESSED_BYTES:
        raise ReleaseInputError(f"ZIP uncompressed size exceeds safety limit: {total}")

    normalized: set[str] = set()
    casefolded: set[str] = set()
    files: list[str] = []
    for info in infos:
        name = info.filename
        if "\\" in name or "\x00" in name:
            raise ReleaseInputError(f"Unsafe ZIP member path: {name!r}")
        pure = PurePosixPath(name)
        if pure.is_absolute() or not pure.parts or ".." in pure.parts:
            raise ReleaseInputError(f"Unsafe ZIP member path: {name!r}")
        if _DRIVE_RE.match(pure.parts[0]):
            raise ReleaseInputError(f"Drive-qualified ZIP member path: {name!r}")

        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(unix_mode):
            raise ReleaseInputError(f"Symlink ZIP member is not allowed: {name!r}")

        canonical = pure.as_posix().rstrip("/")
        folded = canonical.casefold()
        if canonical in normalized or folded in casefolded:
            raise ReleaseInputError(f"Duplicate or case-colliding ZIP member: {name!r}")
        normalized.add(canonical)
        casefolded.add(folded)
        if not info.is_dir():
            files.append(canonical)
    if not files:
        raise ReleaseInputError("ZIP contains no files")
    return files


def _extract_zip_safely(archive: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(archive) as zf:
            _validate_members(zf)
            base = destination.resolve()
            for info in zf.infolist():
                pure = PurePosixPath(info.filename)
                target = destination.joinpath(*pure.parts)
                resolved = target.resolve()
                if resolved != base and base not in resolved.parents:
                    raise ReleaseInputError(f"ZIP member escapes extraction root: {info.filename!r}")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ReleaseInputError(f"Cannot extract ZIP {archive}: {exc}") from exc


def _detect_root(base: Path) -> Path:
    if _is_release_root(base):
        return base
    matches = []
    for measurement in base.rglob("measurements_long_curated_public.csv"):
        if measurement.is_file() and measurement.parent.name == "data":
            candidate = measurement.parent.parent
            if _is_release_root(candidate):
                matches.append(candidate)
    unique = sorted(set(matches), key=lambda p: p.as_posix())
    if len(unique) == 1:
        return unique[0]
    if not unique:
        raise ReleaseInputError("Cannot locate an EnvCoRe-SW public payload or candidate root")
    raise ReleaseInputError("Multiple release roots found in input")


def _is_release_root(path: Path) -> bool:
    required_core = (
        "data/measurements_long_curated_public.csv",
        "data/report_inventory_public.csv",
        "metadata/public_file_manifest.csv",
    )
    return all((path / rel).is_file() for rel in required_core)
