#!/usr/bin/env python3
"""Command-line validator for an EnvCoRe-SW public release candidate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from envcore_validation import ConfigError, ReleaseInputError, load_config, open_release, validate_release


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, type=Path, help="Release ZIP or extracted release root")
    parser.add_argument(
        "--config",
        type=Path,
        default=REPOSITORY_ROOT / "config" / "release_config.json",
        help="Validation configuration JSON",
    )
    parser.add_argument("--out", required=True, type=Path, help="Output directory for JSON and Markdown reports")
    parser.add_argument(
        "--allow-extra-files",
        action="store_true",
        help="Allow controlled audit directories to contain files beyond the 24-file distribution set",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        with open_release(args.release) as root:
            report = validate_release(root, config, allow_extra_files=args.allow_extra_files)
            report.write(args.out)
    except (ConfigError, ReleaseInputError, OSError, ValueError) as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Validation status: {report.status}")
    print(f"PASS checks: {sum(item.status == 'PASS' for item in report.checks)}")
    print(f"FAIL checks: {sum(item.status == 'FAIL' for item in report.checks)}")
    print(f"Reports: {args.out.resolve()}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
