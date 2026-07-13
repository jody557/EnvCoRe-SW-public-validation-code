#!/usr/bin/env python3
"""Validate and rebuild public products for the EnvCoRe-SW v5/v5.5 release.

The validator uses only the Python standard library. It operates on the exact
public ZIP (or an extracted copy) and never accesses private source reports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple, Union


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "release_config.yaml"
ALL_OUTPUT_MARKER = ".envcore_sw_validation_output"
ALL_OUTPUT_MARKER_CONTENT = "EnvCoRe-SW public validation output; safe for tool-managed cleanup.\n"
TEXT_EXTENSIONS = {".csv", ".md", ".json", ".txt", ".cff", ".yaml", ".yml", ".bib"}
ORIGINAL_REPORT_EXTENSIONS = {".doc", ".docx", ".pdf"}
DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
XLSX_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def _parse_yaml_scalar(value: str) -> object:
    value = value.strip()
    if value == "":
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.lower() in {"null", "none", "~"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def load_config(path: Union[Path, str] = DEFAULT_CONFIG) -> Dict[str, object]:
    """Load the deliberately simple two-level YAML configuration."""

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Release configuration not found: {path}")
    result: Dict[str, object] = {}
    current_section: Optional[str] = None
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if ":" not in raw:
            raise ValueError(f"Invalid configuration line {line_number}: {raw}")
        key, value = raw.strip().split(":", 1)
        if indent == 0:
            if value.strip() == "":
                result[key] = {}
                current_section = key
            else:
                result[key] = _parse_yaml_scalar(value)
                current_section = None
        elif indent == 2 and current_section is not None:
            section = result[current_section]
            if not isinstance(section, dict):
                raise ValueError(f"Configuration section is not a mapping: {current_section}")
            section[key] = _parse_yaml_scalar(value)
        else:
            raise ValueError(f"Only one nested mapping level is supported (line {line_number}).")
    required = {
        "dataset_title",
        "dataset_version",
        "dataset_correction_state",
        "main_measurement_file",
        "dual_qa_csv_file",
        "challenge_qa_csv_file",
        "pollutant_dictionary_file",
        "expected_counts",
        "data_doi",
        "code_doi",
        "geographic_scope",
        "temporal_start",
        "temporal_end",
    }
    missing = sorted(required - result.keys())
    if missing:
        raise ValueError(f"Configuration is missing required keys: {', '.join(missing)}")
    return result


def cfg_path(config: Mapping[str, object], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Configuration path {key!r} is missing or empty.")
    return value.replace("\\", "/")


def expected_counts(config: Mapping[str, object]) -> Mapping[str, int]:
    value = config.get("expected_counts")
    if not isinstance(value, dict):
        raise ValueError("expected_counts must be a mapping.")
    return {str(key): int(count) for key, count in value.items()}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_header_and_count(path: Path) -> Tuple[List[str], int]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return [], 0
        return header, sum(1 for _ in reader)


def iter_csv_rows(path: Path) -> Iterator[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"CSV contains duplicate column names: {path}")
        for row in reader:
            yield {str(key): (value if value is not None else "") for key, value in row.items()}


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    return list(iter_csv_rows(path))


def write_csv_rows(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_release_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def rel_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _all_output_allowed_paths() -> Tuple[set[str], set[str]]:
    directories = {"figure_source_data_rebuilt"}
    files = {
        ALL_OUTPUT_MARKER,
        "release_summary.json",
        "regenerated_manifest.csv",
        "validation_report.json",
        "validation_report.md",
    }
    files.update(
        f"figure_source_data_rebuilt/{Path(relative).name}"
        for relative in FIGURE_PATHS.values()
    )
    return directories, files


def _is_tool_managed_all_output(path: Path) -> bool:
    marker = path / ALL_OUTPUT_MARKER
    if not marker.is_file():
        return False
    try:
        if marker.read_text(encoding="utf-8") != ALL_OUTPUT_MARKER_CONTENT:
            return False
    except OSError:
        return False
    allowed_directories, allowed_files = _all_output_allowed_paths()
    for entry in path.rglob("*"):
        if entry.is_symlink():
            return False
        relative = entry.relative_to(path).as_posix()
        if entry.is_dir():
            if relative not in allowed_directories:
                return False
        elif relative not in allowed_files:
            return False
    return True


def prepare_all_output_directory(out: Path, clean: bool, release_root: Path) -> None:
    """Create or safely reset the output tree used by the integrated command."""

    resolved = out.resolve()
    release_resolved = release_root.resolve()
    protected = {Path.cwd().resolve(), Path.home().resolve(), REPO_ROOT.resolve(), release_resolved}
    if resolved == Path(resolved.anchor) or any(
        resolved == item or _is_inside(item, resolved) for item in protected
    ):
        raise ValueError(f"Refusing to use unsafe output path: {resolved}")
    if _is_inside(resolved, release_resolved):
        raise ValueError(f"Output path must not be inside the validated release: {resolved}")
    if out.is_symlink():
        raise ValueError(f"Output path must not be a symbolic link: {out}")
    if out.exists():
        if not out.is_dir():
            raise ValueError(f"Output path is not a directory: {out}")
        has_entries = any(out.iterdir())
        if has_entries and not _is_tool_managed_all_output(out):
            raise ValueError(
                f"Refusing to modify an unrecognized non-empty output directory: {resolved}"
            )
        if clean and has_entries:
            shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / ALL_OUTPUT_MARKER).write_text(ALL_OUTPUT_MARKER_CONTENT, encoding="utf-8")


def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            name = member.filename.replace("\\", "/")
            if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
                raise ValueError(f"Absolute path in ZIP: {member.filename}")
            target = destination / name
            if not _is_inside(target, destination):
                raise ValueError(f"Unsafe path in ZIP: {member.filename}")
        archive.extractall(destination)


def locate_release_root(path: Path, config: Mapping[str, object]) -> Path:
    path = path.resolve()
    manifest = cfg_path(config, "manifest_file")
    if (path / manifest).exists():
        return path
    matches = list(path.rglob(manifest))
    if len(matches) == 1:
        return matches[0].parent
    if not matches:
        raise FileNotFoundError(f"Could not find {manifest} under {path}")
    raise ValueError(f"Multiple release manifests found under {path}")


def prepare_release(
    path: Path, config: Mapping[str, object]
) -> Tuple[Path, Optional[tempfile.TemporaryDirectory], Optional[Dict[str, object]]]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_file():
        if path.suffix.lower() != ".zip":
            raise ValueError(f"Release file must be a ZIP: {path}")
        zip_info = {"path": str(path.resolve()), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
        temporary = tempfile.TemporaryDirectory(prefix="envcore_sw_release_")
        safe_extract_zip(path, Path(temporary.name))
        return locate_release_root(Path(temporary.name), config), temporary, zip_info
    return locate_release_root(path, config), None, None


def required_files(config: Mapping[str, object]) -> Dict[str, str]:
    keys = {
        "manifest": "manifest_file",
        "report_inventory": "report_inventory_file",
        "docx_metadata": "docx_metadata_file",
        "table_cells": "table_cells_file",
        "measurement_candidates": "measurement_candidates_file",
        "standardized_rows": "standardized_parameter_rows_file",
        "numeric_tokens": "numeric_tokens_file",
        "initial_measurements": "initial_measurement_file",
        "curated_measurements": "main_measurement_file",
        "pollutant_dictionary": "pollutant_dictionary_file",
        "schema": "schema_file",
        "controlled_vocabularies": "controlled_vocabulary_file",
        "frequency_removed": "frequency_removed_file",
        "ammonia_audit": "ammonia_audit_file",
        "column_hashes": "column_hash_file",
        "dual_qa_csv": "dual_qa_csv_file",
        "dual_qa_xlsx": "dual_qa_xlsx_file",
        "challenge_qa_csv": "challenge_qa_csv_file",
        "challenge_qa_xlsx": "challenge_qa_xlsx_file",
        "exclusion_audit": "exclusion_audit_file",
        "media_corrections": "media_correction_audit_file",
        "unit_corrections": "unit_correction_audit_file",
        "floating_value_audit": "floating_value_audit_file",
        "fecal_limit_unit_audit": "fecal_limit_unit_audit_file",
        "censored_compliance_audit": "censored_compliance_audit_file",
        "arsenic_normalization_audit": "arsenic_normalization_audit_file",
        "qa_stage_summary": "qa_stage_summary_file",
        "release_build_summary": "release_build_summary_file",
        "publication_readiness": "publication_readiness_file",
    }
    return {name: cfg_path(config, key) for name, key in keys.items()}


def expected_table_counts(config: Mapping[str, object]) -> Dict[str, Tuple[int, Optional[int]]]:
    files = required_files(config)
    counts = expected_counts(config)
    return {
        files["report_inventory"]: (counts["report_inventory"], 14),
        files["docx_metadata"]: (counts["parsed_docx_reports"], 14),
        files["table_cells"]: (counts["table_cells"], 7),
        files["measurement_candidates"]: (counts["measurement_candidates"], 7),
        files["standardized_rows"]: (counts["standardized_parameter_rows"], 23),
        files["numeric_tokens"]: (counts["numeric_tokens"], 21),
        files["initial_measurements"]: (counts["initial_measurements"], 31),
        files["curated_measurements"]: (counts["curated_measurements"], 31),
        files["pollutant_dictionary"]: (counts["parameter_codes"], 8),
        files["frequency_removed"]: (counts["frequency_false_accepts_removed"], 36),
        files["ammonia_audit"]: (counts["ammonia_parameter_recodes"], 38),
        files["dual_qa_csv"]: (counts["dual_qa_records"], 89),
        files["challenge_qa_csv"]: (counts["challenge_qa_records"], 58),
        files["exclusion_audit"]: (counts["excluded_measurements"], 17),
        files["media_corrections"]: (counts["media_group_corrections"], 15),
        files["unit_corrections"]: (counts["unit_corrections"], 15),
        files["floating_value_audit"]: (counts["floating_value_canonicalizations"], 15),
        files["fecal_limit_unit_audit"]: (counts["fecal_limit_unit_corrections"], 14),
        files["censored_compliance_audit"]: (counts["censored_records_reviewed"], 18),
        files["arsenic_normalization_audit"]: (counts["arsenic_value_normalizations"], 18),
        files["schema"]: (counts["schema_rows"], 19),
        files["controlled_vocabularies"]: (counts["controlled_vocabulary_rows"], 9),
        files["column_hashes"]: (31, 4),
    }


def count_values(rows: Iterable[Mapping[str, str]], field: str) -> Counter:
    return Counter(row.get(field, "") for row in rows)


def duplicate_count(values: Iterable[str]) -> int:
    seen = set()
    duplicates = 0
    for value in values:
        if value in seen:
            duplicates += 1
        else:
            seen.add(value)
    return duplicates


class ValidationReport:
    def __init__(self, config: Mapping[str, object]) -> None:
        self.config = config
        self.checks: List[Dict[str, object]] = []

    def add(self, name: str, ok: bool, detail: str, observed: object = None, expected: object = None) -> None:
        self.checks.append(
            {
                "name": name,
                "status": "PASS" if ok else "FAIL",
                "detail": detail,
                "observed": observed,
                "expected": expected,
            }
        )

    @property
    def passed(self) -> bool:
        return all(item["status"] == "PASS" for item in self.checks)

    def to_dict(self) -> Dict[str, object]:
        return {
            "dataset_title": self.config["dataset_title"],
            "dataset_version": self.config["dataset_version"],
            "dataset_correction_state": self.config["dataset_correction_state"],
            "configured_data_doi": self.config["data_doi"],
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "PASS" if self.passed else "FAIL",
            "checks": self.checks,
        }


MANIFEST_FIELDS = [
    "relative_path",
    "size_bytes",
    "sha256",
    "row_count",
    "column_count",
    "column_names",
    "description",
    "release_role",
]


def manifest_descriptions(root: Path, config: Mapping[str, object]) -> Dict[str, Tuple[str, str]]:
    path = root / cfg_path(config, "manifest_file")
    if not path.exists():
        return {}
    return {
        row["relative_path"].replace("\\", "/"): (row.get("description", ""), row.get("release_role", ""))
        for row in read_csv_rows(path)
    }


def generate_manifest_rows(
    root: Path, descriptions: Optional[Mapping[str, Tuple[str, str]]] = None
) -> List[Dict[str, object]]:
    descriptions = descriptions or {}
    rows: List[Dict[str, object]] = []
    for path in iter_release_files(root):
        relative = rel_path(root, path)
        if relative == "public_dataset_manifest.csv":
            continue
        row_count: object = ""
        column_count: object = ""
        column_names = ""
        if path.suffix.lower() == ".csv":
            header, count = csv_header_and_count(path)
            row_count = count
            column_count = len(header)
            column_names = ";".join(header)
        description, role = descriptions.get(relative, ("Release documentation or supporting data file.", "supporting"))
        rows.append(
            {
                "relative_path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "row_count": row_count,
                "column_count": column_count,
                "column_names": column_names,
                "description": description,
                "release_role": role,
            }
        )
    return rows


def _stringify_rows(rows: Iterable[Mapping[str, object]], fields: Sequence[str]) -> List[Dict[str, str]]:
    return [{field: str(row.get(field, "")) for field in fields} for row in rows]


def manifest_rows_equivalent(
    observed: Sequence[Mapping[str, object]], expected: Sequence[Mapping[str, object]]
) -> bool:
    """Compare manifest content independently of presentation row order."""

    def normalize(rows: Sequence[Mapping[str, object]]) -> List[Tuple[str, ...]]:
        return sorted(
            tuple(str(row.get(field, "")) for field in MANIFEST_FIELDS)
            for row in rows
        )

    return normalize(observed) == normalize(expected)


def validate_manifest(root: Path, report: ValidationReport, config: Mapping[str, object]) -> None:
    manifest_path = root / cfg_path(config, "manifest_file")
    rows = read_csv_rows(manifest_path)
    header, _ = csv_header_and_count(manifest_path)
    report.add("manifest columns", header == MANIFEST_FIELDS, "Manifest uses the required column order.", header, MANIFEST_FIELDS)
    listed = [row.get("relative_path", "").replace("\\", "/") for row in rows]
    report.add("manifest paths unique", len(listed) == len(set(listed)), "Manifest relative paths are unique.")
    report.add(
        "manifest entry count",
        len(rows) == expected_counts(config)["manifest_entries"],
        "Manifest contains the configured number of non-self entries.",
        len(rows),
        expected_counts(config)["manifest_entries"],
    )
    actual = {rel_path(root, path): path for path in iter_release_files(root)}
    manifest_rel = cfg_path(config, "manifest_file")
    report.add("manifest excludes itself", manifest_rel not in listed, "The manifest does not hash itself.")
    report.add("manifest files exist", not (set(listed) - set(actual)), "All manifest-listed files exist.", sorted(set(listed) - set(actual)), [])
    report.add("no unlisted files", not (set(actual) - set(listed) - {manifest_rel}), "Every release file except the manifest is listed.", sorted(set(actual) - set(listed) - {manifest_rel}), [])
    regenerated = generate_manifest_rows(root, manifest_descriptions(root, config))
    report.add(
        "manifest fully reproducible",
        manifest_rows_equivalent(rows, regenerated),
        "Paths, sizes, hashes, CSV metadata, descriptions, and roles match a fresh rebuild independent of row order.",
    )
    expected_hash = str(config.get("expected_manifest_sha256", ""))
    report.add("manifest exact v5.5 hash", sha256_file(manifest_path) == expected_hash, "Manifest is the exact Zenodo-uploaded v5.5 artifact.", sha256_file(manifest_path), expected_hash)


def validate_expected_counts(root: Path, report: ValidationReport, config: Mapping[str, object]) -> None:
    for relative, (wanted_rows, wanted_columns) in expected_table_counts(config).items():
        path = root / relative
        report.add(f"required file: {relative}", path.exists(), "Required release file exists.")
        if not path.exists():
            continue
        header, rows = csv_header_and_count(path)
        report.add(f"expected rows: {relative}", rows == wanted_rows, "Row count matches v5.5 configuration.", rows, wanted_rows)
        report.add(f"unique columns: {relative}", len(header) == len(set(header)), "CSV header contains no duplicate fields.")
        if wanted_columns is not None:
            report.add(f"expected columns: {relative}", len(header) == wanted_columns, "Column count matches v5.5 schema.", len(header), wanted_columns)
    for key in ("dual_qa_xlsx", "challenge_qa_xlsx", "qa_stage_summary", "release_build_summary", "publication_readiness"):
        relative = required_files(config)[key]
        report.add(f"required file: {relative}", (root / relative).is_file(), "Required v5.5 release artifact exists.")


def _parse_numeric(value: str) -> bool:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return False
    return number.is_finite()


def _numeric_equal(left: str, right: str) -> bool:
    try:
        return Decimal(left) == Decimal(right)
    except (InvalidOperation, ValueError):
        return False


def validate_curated_measurements(root: Path, report: ValidationReport, config: Mapping[str, object]) -> None:
    files = required_files(config)
    path = root / files["curated_measurements"]
    rows = read_csv_rows(path)
    required = {"measurement_id", "measurement_row_candidate_id", "report_id", "parameter_code", "value", "year"}
    header, _ = csv_header_and_count(path)
    report.add("curated required fields", required <= set(header), "Required curated-measurement fields exist.", sorted(required - set(header)), [])
    missing = {field: sum(not row.get(field, "").strip() for row in rows) for field in required}
    report.add("curated required fields complete", all(count == 0 for count in missing.values()), "Required fields are nonblank.", missing, {field: 0 for field in required})
    identifiers = [row.get("measurement_id", "") for row in rows]
    report.add("measurement_id unique", duplicate_count(identifiers) == 0, "Curated measurement identifiers are unique.")
    invalid_numeric = [row.get("measurement_id", "") for row in rows if not _parse_numeric(row.get("value", ""))]
    report.add("numeric values valid", not invalid_numeric, "All curated values are finite decimal numbers.", invalid_numeric[:10], [])
    invalid_years = [row.get("measurement_id", "") for row in rows if not str(config["temporal_start"]) <= row.get("year", "") <= str(config["temporal_end"])]
    report.add("measurement years in scope", not invalid_years, "All measurement years are within configured temporal coverage.", invalid_years[:10], [])
    invalid_dates: List[str] = []
    for row in rows:
        valid_flag = row.get("sample_date_valid", "").strip().lower()
        sample_date = row.get("sample_date", "").strip()
        if valid_flag not in {"true", "false", "not_applicable"}:
            invalid_dates.append(row.get("measurement_id", ""))
        elif valid_flag == "true":
            try:
                date.fromisoformat(sample_date)
            except ValueError:
                invalid_dates.append(row.get("measurement_id", ""))
        elif sample_date:
            invalid_dates.append(row.get("measurement_id", ""))
    report.add("sample date semantics", not invalid_dates, "Valid dates are ISO dates; invalid/not-applicable dates are blank.", invalid_dates[:10], [])
    expected_hash = str(config.get("expected_main_measurement_sha256", ""))
    observed_hash = sha256_file(path)
    report.add("main table exact v5.5 hash", observed_hash == expected_hash, "Main table is byte-identical to the Zenodo-uploaded v5.5 table.", observed_hash, expected_hash)


def validate_identifiers(root: Path, report: ValidationReport, config: Mapping[str, object]) -> None:
    files = required_files(config)
    counts = expected_counts(config)
    curated = read_csv_rows(root / files["curated_measurements"])
    exclusions = read_csv_rows(root / files["exclusion_audit"])
    inventory_ids = {row["report_id"] for row in iter_csv_rows(root / files["report_inventory"])}
    candidate_ids = {row["measurement_row_candidate_id"] for row in iter_csv_rows(root / files["standardized_rows"])}
    parameter_codes = {row["parameter_code"] for row in iter_csv_rows(root / files["pollutant_dictionary"])}
    measurement_ids = {row["measurement_id"] for row in curated}
    exclusion_ids = {row["measurement_id"] for row in exclusions}
    report.add("report_id foreign key", not ({row["report_id"] for row in curated} - inventory_ids), "All curated reports occur in the report inventory.")
    report.add("candidate foreign key", not ({row["measurement_row_candidate_id"] for row in curated} - candidate_ids), "All curated rows link to standardized candidate rows.")
    report.add("parameter dictionary coverage", not ({row["parameter_code"] for row in curated} - parameter_codes), "All curated parameter codes occur in the dictionary.")
    report.add("exclusion IDs unique", len(exclusion_ids) == len(exclusions), "The cumulative exclusion audit has unique measurement IDs.")
    report.add("retained/excluded disjoint", not (measurement_ids & exclusion_ids), "No excluded measurement remains in the v5 table.", sorted(measurement_ids & exclusion_ids)[:10], [])
    report.add("pre-v5 partition count", len(measurement_ids | exclusion_ids) == counts["pre_v5_curated_measurements"], "Retained and cumulatively excluded IDs partition the 20,514-record pre-v5 frame by count.", len(measurement_ids | exclusion_ids), counts["pre_v5_curated_measurements"])
    frequency_ids = {row["measurement_id"] for row in iter_csv_rows(root / files["frequency_removed"])}
    report.add("frequency false accepts absent", not (frequency_ids & measurement_ids), "All 559 earlier frequency-context false accepts remain absent from the current table.")
    duplicate_exclusion_ids = {row["measurement_id"] for row in exclusions if row["exclusion_reason"] == "duplicate_after_parameter_correction"}
    ammonia_ids = {row["measurement_id"] for row in iter_csv_rows(root / files["ammonia_audit"])}
    report.add("ammonia duplicate audit synchronized", ammonia_ids == duplicate_exclusion_ids, "The 1,096 ammonia recodes equal the duplicate-after-correction exclusions.", len(ammonia_ids ^ duplicate_exclusion_ids), 0)
    for label, key in (("stratified QA", "dual_qa_csv"), ("challenge QA", "challenge_qa_csv")):
        qa = read_csv_rows(root / files[key])
        missing = [row["measurement_id"] for row in qa if row["measurement_id"] not in measurement_ids | exclusion_ids]
        wrong_state = [
            row["measurement_id"]
            for row in qa
            if (row["final_correction_action"] == "exclude_record") != (row["measurement_id"] in exclusion_ids)
        ]
        report.add(f"{label} ID coverage", not missing, "Every QA ID resolves to a retained or cumulatively excluded measurement.", missing[:10], [])
        report.add(f"{label} final action applied", not wrong_state, "QA exclusion actions agree with current main/exclusion membership.", wrong_state[:10], [])


QA_AGREEMENT_FIELDS = [
    "parameter_supported",
    "value_supported",
    "unit_supported",
    "medium_supported",
    "date_supported",
    "compliance_supported",
    "accepted_measurement_supported",
    "false_accept",
    "error_category",
]


def _qa_needs_adjudication(row: Mapping[str, str]) -> bool:
    if row.get("reviewer_agreement") == "no":
        return True
    if any(row.get(f"{reviewer}_{field}") == "uncertain" for reviewer in ("r1", "r2") for field in QA_AGREEMENT_FIELDS):
        return True
    return any(
        row.get(f"{reviewer}_false_accept") == "yes"
        or row.get(f"{reviewer}_accepted_measurement_supported") == "no"
        or row.get(f"{reviewer}_error_category") != "none"
        for reviewer in ("r1", "r2")
    )


def qa_metrics(rows: Sequence[Mapping[str, str]]) -> Dict[str, object]:
    return {
        "records": len(rows),
        "reviewer_agreement": dict(Counter(row["reviewer_agreement"] for row in rows)),
        "human_adjudication_required": sum(row["adjudication_required"] == "yes" for row in rows),
        "human_confirmed_false_accepts": sum(row["adjudication_decision"] == "adjudicator_confirms_false_accept" for row in rows),
        "human_adjudicated_corrections": sum(row["adjudication_decision"] == "adjudicator_accepts_with_correction" for row in rows),
        "post_review_rule_exclusions": sum("exclude_record" in row["post_review_decision"] for row in rows),
        "final_total_exclusions": sum(row["final_correction_action"] == "exclude_record" for row in rows),
        "final_qa_decisions": dict(Counter(row["final_qa_decision"] for row in rows)),
        "final_correction_actions": dict(Counter(row["final_correction_action"] for row in rows)),
    }


def _validate_qa_table(
    rows: Sequence[Mapping[str, str]], label: str, id_field: str, report: ValidationReport
) -> None:
    ids = [row.get(id_field, "") for row in rows]
    measurement_ids = [row.get("measurement_id", "") for row in rows]
    report.add(f"{label} sample IDs complete and unique", all(ids) and len(ids) == len(set(ids)), "QA sample identifiers are nonblank and unique.")
    report.add(f"{label} measurement IDs unique", len(measurement_ids) == len(set(measurement_ids)), "A measurement appears at most once in this QA sample.")
    required_result_fields = [
        *(f"r1_{field}" for field in QA_AGREEMENT_FIELDS),
        "r1_review_status",
        "r1_notes",
        *(f"r2_{field}" for field in QA_AGREEMENT_FIELDS),
        "r2_review_status",
        "r2_notes",
        "reviewer_agreement",
        "adjudication_required",
        "adjudicator_id",
        "adjudication_decision",
        "final_qa_decision",
        "final_correction_action",
        "post_review_audit_status",
    ]
    missing = [(row.get(id_field, ""), field) for row in rows for field in required_result_fields if not row.get(field, "").strip()]
    report.add(f"{label} completed review fields", not missing, "All required human-review, adjudication, and final-action fields are complete.", missing[:10], [])
    status_bad = [row.get(id_field, "") for row in rows if row.get("r1_review_status") != "reviewed_human_independent_blinded" or row.get("r2_review_status") != "reviewed_human_independent_blinded"]
    report.add(f"{label} independent blinded status", not status_bad, "R1 and R2 statuses record independent blinded human review.", status_bad[:10], [])
    agreement_bad = [
        row.get(id_field, "")
        for row in rows
        if (row.get("reviewer_agreement") == "yes")
        != all(row.get(f"r1_{field}") == row.get(f"r2_{field}") for field in QA_AGREEMENT_FIELDS)
    ]
    report.add(f"{label} reviewer agreement recomputed", not agreement_bad, "reviewer_agreement equals a fresh field-level R1/R2 comparison.", agreement_bad[:10], [])
    adjudication_bad = [row.get(id_field, "") for row in rows if (row.get("adjudication_required") == "yes") != _qa_needs_adjudication(row)]
    report.add(f"{label} adjudication requirement recomputed", not adjudication_bad, "Human adjudication is required exactly for disagreement, uncertainty, or a reviewer-identified error.", adjudication_bad[:10], [])
    stage_bad: List[str] = []
    for row in rows:
        required = row.get("adjudication_required") == "yes"
        if required:
            ok = row.get("adjudicator_id") == "HUM_ADJ01" and row.get("adjudication_decision") != "not_required_reviewers_agree"
        else:
            ok = row.get("adjudicator_id") == "not_applicable" and row.get("adjudication_decision") == "not_required_reviewers_agree"
        human_fields = " ".join(row.get(field, "") for field in ("adjudicator_id", "adjudication_decision"))
        if not ok or "POST_REVIEW_RULE_AUDIT" in human_fields or "post_review_rule" in human_fields.lower():
            stage_bad.append(row.get(id_field, ""))
    report.add(f"{label} human/rule stage separation", not stage_bad, "Human adjudication fields contain only HUM_ADJ01/not_applicable outcomes; deterministic results remain in post_review_*.", stage_bad[:10], [])
    report.add(f"{label} post-review audit complete", all(row.get("post_review_audit_status") == "checked" for row in rows), "Every record has a completed post-review audit status.")
    final_bad = [
        row.get(id_field, "")
        for row in rows
        if (row.get("final_correction_action") == "exclude_record") != (row.get("final_qa_decision") == "confirmed_false_accept")
        or ("exclude_record" in row.get("post_review_decision", "") and row.get("final_correction_action") != "exclude_record")
        or (row.get("adjudication_decision") == "adjudicator_confirms_false_accept" and row.get("final_correction_action") != "exclude_record")
    ]
    report.add(f"{label} final decisions consistent", not final_bad, "Human and deterministic exclusions propagate to the final decision/action fields.", final_bad[:10], [])
    date_bad: List[str] = []
    for row in rows:
        value = row.get("sample_date", "")
        flag = row.get("sample_date_valid", "").lower()
        if flag in {"true", "1"}:
            try:
                date.fromisoformat(value)
            except ValueError:
                date_bad.append(row.get(id_field, ""))
        elif value:
            date_bad.append(row.get(id_field, ""))
    report.add(f"{label} ISO sample dates", not date_bad, "Only valid sample dates are populated and they use ISO YYYY-MM-DD.", date_bad[:10], [])


def _xlsx_column_number(reference: str) -> int:
    match = re.match(r"[A-Z]+", reference)
    if not match:
        raise ValueError(f"Invalid XLSX cell reference: {reference}")
    number = 0
    for character in match.group(0):
        number = number * 26 + ord(character) - 64
    return number


def read_xlsx_sheets(path: Path) -> Dict[str, List[List[str]]]:
    """Read cell values from an XLSX workbook with no third-party dependency."""

    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        shared: List[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("main:si", XLSX_NS):
                shared.append("".join(node.text or "" for node in item.findall(".//main:t", XLSX_NS)))
        result: Dict[str, List[List[str]]] = {}
        sheet_parent = workbook.find("main:sheets", XLSX_NS)
        if sheet_parent is None:
            raise ValueError(f"Workbook has no sheets: {path}")
        for sheet in sheet_parent:
            relationship_id = sheet.attrib[f"{{{XLSX_NS['rel']}}}id"]
            target = targets[relationship_id].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            sheet_root = ET.fromstring(archive.read(target))
            output_rows: List[List[str]] = []
            for row in sheet_root.findall(".//main:sheetData/main:row", XLSX_NS):
                values: Dict[int, str] = {}
                for cell in row.findall("main:c", XLSX_NS):
                    index = _xlsx_column_number(cell.attrib["r"])
                    cell_type = cell.attrib.get("t", "n")
                    if cell_type == "inlineStr":
                        value = "".join(node.text or "" for node in cell.findall(".//main:t", XLSX_NS))
                    else:
                        node = cell.find("main:v", XLSX_NS)
                        value = "" if node is None else (node.text or "")
                        if cell_type == "s" and value:
                            value = shared[int(value)]
                        elif cell_type == "b":
                            value = "true" if value == "1" else "false"
                    values[index] = value
                width = max(values, default=0)
                output_rows.append([values.get(column, "") for column in range(1, width + 1)])
            result[sheet.attrib["name"]] = output_rows
        return result


def _spreadsheet_values_equal(csv_value: str, xlsx_value: str) -> bool:
    if csv_value == xlsx_value:
        return True
    try:
        left = Decimal(csv_value)
        right = Decimal(xlsx_value)
    except (InvalidOperation, ValueError):
        return False
    tolerance = Decimal("1e-12") * max(Decimal(1), abs(left), abs(right))
    return abs(left - right) <= tolerance


def _validate_csv_xlsx_pair(
    csv_path: Path, xlsx_path: Path, first_sheet: str, required_sheets: Sequence[str], label: str, report: ValidationReport
) -> Dict[str, List[List[str]]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.reader(handle))
    sheets = read_xlsx_sheets(xlsx_path)
    report.add(f"{label} workbook sheets", list(sheets) == list(required_sheets), "Workbook contains the required sheets in order.", list(sheets), list(required_sheets))
    workbook_rows = sheets.get(first_sheet, [])
    differences: List[Tuple[int, int, str, str]] = []
    if len(csv_rows) != len(workbook_rows):
        differences.append((0, 0, str(len(csv_rows)), str(len(workbook_rows))))
    else:
        for row_number, (csv_row, workbook_row) in enumerate(zip(csv_rows, workbook_rows), start=1):
            if len(csv_row) != len(workbook_row):
                differences.append((row_number, 0, str(len(csv_row)), str(len(workbook_row))))
                continue
            for column_number, (csv_value, workbook_value) in enumerate(zip(csv_row, workbook_row), start=1):
                if not _spreadsheet_values_equal(csv_value, workbook_value):
                    differences.append((row_number, column_number, csv_value, workbook_value))
                    if len(differences) >= 20:
                        break
            if len(differences) >= 20:
                break
    report.add(f"{label} CSV/XLSX synchronization", not differences, "The primary workbook sheet semantically equals the CSV (allowing only binary floating representation noise).", differences, [])
    return sheets


def _sheet_dicts(sheet: Sequence[Sequence[str]]) -> List[Dict[str, str]]:
    if not sheet:
        return []
    header = list(sheet[0])
    return [{header[index]: row[index] if index < len(row) else "" for index in range(len(header))} for row in sheet[1:]]


def validate_overlap_audit(
    dual: Sequence[Mapping[str, str]], challenge: Sequence[Mapping[str, str]], sheets: Mapping[str, Sequence[Sequence[str]]], report: ValidationReport
) -> None:
    dual_by_id = {row["measurement_id"]: row for row in dual}
    challenge_by_id = {row["measurement_id"]: row for row in challenge}
    overlap_ids = set(dual_by_id) & set(challenge_by_id)
    audit = _sheet_dicts(sheets.get("OVERLAP_AUDIT", []))
    report.add("challenge overlap audit membership", {row.get("measurement_id", "") for row in audit} == overlap_ids, "OVERLAP_AUDIT is freshly tied to the actual eight-file intersection.", sorted({row.get("measurement_id", "") for row in audit} ^ overlap_ids), [])
    compared_fields = [
        "parameter_code", "value", "unit", "media", "parameter_group", "standard_limit", "limit_unit", "compliance_flag",
        "r1_compliance_supported", "r2_compliance_supported", "adjudication_required", "adjudicator_id", "adjudication_decision",
        "post_review_audit_status", "post_review_error_category", "post_review_decision", "final_qa_decision", "final_correction_action",
    ]
    bad: List[str] = []
    for row in audit:
        measurement_id = row.get("measurement_id", "")
        if measurement_id not in overlap_ids:
            continue
        left = dual_by_id[measurement_id]
        right = challenge_by_id[measurement_id]
        fields_ok = True
        for field in compared_fields:
            expected_equal = "yes" if left.get(field, "") == right.get(field, "") else "no"
            if row.get(f"dual_{field}") != left.get(field, "") or row.get(f"challenge_{field}") != right.get(field, "") or row.get(f"{field}_equal") != expected_equal:
                fields_ok = False
        if not fields_ok or row.get("all_compared_fields_equal") != "yes" or row.get("status") != "verified_equal_after_field_level_comparison":
            bad.append(measurement_id)
    report.add("challenge overlap audit recomputed", not bad and len(audit) == 8, "All 8 overlap rows and every compared field are recomputed as equal.", bad, [])


def validate_qa(root: Path, report: ValidationReport, config: Mapping[str, object]) -> None:
    files = required_files(config)
    counts = expected_counts(config)
    dual = read_csv_rows(root / files["dual_qa_csv"])
    challenge = read_csv_rows(root / files["challenge_qa_csv"])
    _validate_qa_table(dual, "stratified 800", "qa_sample_id", report)
    _validate_qa_table(challenge, "targeted challenge", "challenge_sample_id", report)
    report.add("stratified QA count", len(dual) == counts["dual_qa_records"], "Completed dual-human-review sample has 800 records.", len(dual), counts["dual_qa_records"])
    report.add("challenge QA count", len(challenge) == counts["challenge_qa_records"], "Completed targeted challenge sample has 200 records.", len(challenge), counts["challenge_qa_records"])
    report.add("stratified sampling seed", {row["qa_sampling_seed"] for row in dual} == {"20260705"}, "The public sampling seed is stable and explicit.")
    weight_sum = sum(Decimal(row["qa_audit_weight"]) for row in dual)
    report.add("stratified audit-weight target", abs(weight_sum - Decimal(counts["pre_v5_curated_measurements"])) < Decimal("0.00001"), "Design weights sum to the pre-v5 20,514-record frame within documented rounding tolerance.", str(weight_sum), counts["pre_v5_curated_measurements"])
    report.add("challenge scope", all(row["media"] == "water" and row["parameter_code"] in {"ph", "ammonia_nitrogen", "color"} for row in challenge), "Challenge records are the declared targeted water-parameter sample.")
    dual_metrics = qa_metrics(dual)
    challenge_metrics = qa_metrics(challenge)
    expected_dual = {"human_adjudication_required": 173, "human_confirmed_false_accepts": 16, "human_adjudicated_corrections": 2, "post_review_rule_exclusions": 38, "final_total_exclusions": 54}
    expected_challenge = {"human_adjudication_required": 41, "human_confirmed_false_accepts": 1, "human_adjudicated_corrections": 0, "post_review_rule_exclusions": 51, "final_total_exclusions": 52}
    report.add("stratified stage metrics", all(dual_metrics[key] == value for key, value in expected_dual.items()), "Human review, human adjudication, deterministic audit, and final exclusions retain their separate counts.", {key: dual_metrics[key] for key in expected_dual}, expected_dual)
    report.add("challenge stage metrics", all(challenge_metrics[key] == value for key, value in expected_challenge.items()), "Challenge human and deterministic stages retain their separate counts.", {key: challenge_metrics[key] for key in expected_challenge}, expected_challenge)
    duplicate_bad = [row["challenge_sample_id"] for row in challenge if "duplicate_after_parameter_correction" in row["post_review_error_category"] and (row["post_review_decision"] != "exclude_record" or row["final_correction_action"] != "exclude_record")]
    report.add("challenge duplicates excluded", not duplicate_bad, "Every deterministic duplicate-after-parameter-correction finding is excluded.", duplicate_bad[:10], [])
    dual_sheets = _validate_csv_xlsx_pair(
        root / files["dual_qa_csv"], root / files["dual_qa_xlsx"], "human_manual_qa_800_dual_review",
        ["human_manual_qa_800_dual_review", "CHANGE_LOG", "REVIEW_METADATA", "HUMAN_REVIEW_PROTOCOL"], "stratified QA", report,
    )
    challenge_sheets = _validate_csv_xlsx_pair(
        root / files["challenge_qa_csv"], root / files["challenge_qa_xlsx"], "historical_water_challenge",
        ["historical_water_challenge", "SCORING_AUDIT", "OVERLAP_AUDIT", "CHANGE_LOG", "REVIEW_METADATA", "HUMAN_REVIEW_PROTOCOL"], "challenge QA", report,
    )
    validate_overlap_audit(dual, challenge, challenge_sheets, report)
    protocol_text = " ".join(" ".join(row) for row in dual_sheets.get("HUMAN_REVIEW_PROTOCOL", []))
    report.add("reviewer identities and backgrounds documented", all(token in protocol_text for token in ("HUM_R01", "HUM_R02", "HUM_ADJ01", "environmental sciences", "computer science", "nine years")), "Workbook protocol documents the confirmed reviewer/adjudicator identities, professional backgrounds, blinding, and third-party adjudication.")
    forbidden_paths = [rel_path(root, path) for path in iter_release_files(root) if rel_path(root, path).startswith("qa_templates/") or "dual_review_template" in path.name or "challenge_sample_template" in path.name]
    report.add("blank QA templates omitted", not forbidden_paths, "The public v5 ZIP includes completed QA results and no blank QA templates.", forbidden_paths, [])


def _audit_current_mismatches(
    main_by_id: Mapping[str, Mapping[str, str]], rows: Sequence[Mapping[str, str]], field_map: Mapping[str, str]
) -> List[Tuple[str, str, str, str]]:
    bad: List[Tuple[str, str, str, str]] = []
    for row in rows:
        measurement_id = row.get("measurement_id", "")
        current = main_by_id.get(measurement_id)
        if current is None:
            bad.append((measurement_id, "membership", "missing", "retained"))
            continue
        for audit_field, main_field in field_map.items():
            expected = row.get(audit_field, "")
            observed = current.get(main_field, "")
            if audit_field in {"canonical_value", "corrected_value"}:
                equal = _numeric_equal(expected, observed)
            else:
                equal = expected == observed
            if not equal:
                bad.append((measurement_id, main_field, observed, expected))
    return bad


def _limit_number(value: str) -> Optional[Decimal]:
    match = re.fullmatch(r"\s*(?:<=|<|≥|>=|≤)?\s*(-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*", value)
    if not match:
        return None
    try:
        return Decimal(match.group(1))
    except InvalidOperation:
        return None


def validate_v5_corrections(root: Path, report: ValidationReport, config: Mapping[str, object]) -> None:
    files = required_files(config)
    main = read_csv_rows(root / files["curated_measurements"])
    main_by_id = {row["measurement_id"]: row for row in main}
    exclusions = read_csv_rows(root / files["exclusion_audit"])
    report.add("all cumulative exclusions applied", all(row["measurement_id"] not in main_by_id and row["final_action"] == "exclude_record" for row in exclusions), "All 1,392 exclusions are absent from the main table and explicitly marked exclude_record.")
    audits = [
        ("media/group corrections", files["media_corrections"], {"corrected_media": "media", "corrected_parameter_group": "parameter_group"}),
        ("unit corrections", files["unit_corrections"], {"corrected_unit": "unit", "corrected_limit_unit": "limit_unit"}),
        ("floating-value canonicalization", files["floating_value_audit"], {"canonical_value": "value"}),
        ("fecal limit-unit corrections", files["fecal_limit_unit_audit"], {"corrected_limit_unit": "limit_unit"}),
        ("censored-compliance review", files["censored_compliance_audit"], {"corrected_value": "value", "corrected_unit": "unit", "corrected_compliance_flag": "compliance_flag"}),
        ("arsenic normalization", files["arsenic_normalization_audit"], {"corrected_value": "value", "corrected_unit": "unit", "corrected_compliance_flag": "compliance_flag"}),
    ]
    for label, relative, mapping in audits:
        mismatches = _audit_current_mismatches(main_by_id, read_csv_rows(root / relative), mapping)
        report.add(f"{label} applied to main table", not mismatches, "Every public correction-audit outcome is present in the retained main fields.", mismatches[:10], [])
    heavy_gas = [row["measurement_id"] for row in main if row["media"] == "water" and row["parameter_code"] in {"mercury", "lead", "arsenic"} and row["unit"] in {"mg/m3", "mg/Nm3"}]
    report.add("heavy-metal gas units use air medium", not heavy_gas, "No water heavy-metal record retains a gas-volume concentration unit.", heavy_gas[:10], [])
    anomalous = [
        row["measurement_id"] for row in main
        if (row["parameter_code"], row["unit"]) in {
            ("fecal_coliform", "mg/L"), ("water_temperature", "MPN/L"), ("ph", "mg/L"), ("odor_concentration", "mg/m3")
        }
    ]
    report.add("targeted parameter-unit anomalies resolved", not anomalous, "The 23 source-reviewed parameter-unit anomalies no longer occur in the main table.", anomalous[:10], [])
    fecal_mismatch = [row["measurement_id"] for row in main if row["parameter_code"] == "fecal_coliform" and row["standard_limit"] and row["unit"] != row["limit_unit"]]
    report.add("fecal limit-unit mismatches resolved", not fecal_mismatch, "Fecal-coliform measurement and limit units are synchronized where a limit exists.", fecal_mismatch[:10], [])
    censored_ambiguity: List[str] = []
    for row in main:
        if row["qualifier"] not in {"<", "<="} or row["compliance_flag"] != "pass" or row["unit"] != row["limit_unit"]:
            continue
        threshold = _limit_number(row["value"])
        limit = _limit_number(row["standard_limit"])
        if threshold is not None and limit is not None and threshold > limit:
            censored_ambiguity.append(row["measurement_id"])
    report.add("censored-pass ambiguities resolved", not censored_ambiguity, "No retained censored pass has a reporting threshold above its same-unit standard limit.", censored_ambiguity[:10], [])
    floating_tails = [
        row["measurement_id"] for row in main
        if re.fullmatch(r"-?\d+\.\d{12,}", row["value"])
        and abs(Decimal(row["value"]) - Decimal(row["value"]).to_integral_value()) < Decimal("1e-9")
    ]
    report.add("noncanonical binary floating tails absent", not floating_tails, "No near-integer value retains a long binary floating-point tail.", floating_tails[:10], [])
    dictionary = {row["parameter_code"]: row for row in read_csv_rows(root / files["pollutant_dictionary"])}
    dictionary_bad = []
    for parameter in ("mercury", "lead", "arsenic"):
        row = dictionary.get(parameter, {})
        media = set(row.get("media", "").split(";"))
        units = set(row.get("expected_unit_patterns", "").split(";"))
        if not {"water", "air"} <= media or not {"mg/L", "mg/m3", "mg/Nm3"} <= units:
            dictionary_bad.append(parameter)
    report.add("heavy-metal dictionary is multi-media", not dictionary_bad, "Mercury, lead, and arsenic dictionary entries support water/air and liquid/gas units.", dictionary_bad, [])
    for label, key in (("stratified QA retained-field synchronization", "dual_qa_csv"), ("challenge QA retained-field synchronization", "challenge_qa_csv")):
        mismatches: List[Tuple[str, str, str, str]] = []
        common_fields = ["report_id", "table_id", "row_index", "measurement_row_candidate_id", "year", "media", "facility_type", "parameter_code", "parameter_group", "value", "unit", "qualifier", "standard_limit", "limit_unit", "compliance_flag", "sample_date", "sample_date_valid", "date_parse_note", "extraction_confidence", "qa_status", "row_text_hash"]
        for row in read_csv_rows(root / files[key]):
            current = main_by_id.get(row["measurement_id"])
            if current is None:
                continue
            for field in common_fields:
                if field not in row:
                    continue
                if field == "value":
                    equal = _numeric_equal(row[field], current[field])
                elif field == "standard_limit":
                    left_limit = _limit_number(row[field])
                    right_limit = _limit_number(current[field])
                    equal = row[field] == current[field] or (
                        left_limit is not None and right_limit is not None and left_limit == right_limit
                    )
                else:
                    equal = row[field] == current[field]
                if not equal:
                    mismatches.append((row["measurement_id"], field, row[field], current[field]))
        report.add(label, not mismatches, "All retained sampled fields reflect the corrected main table (numeric formatting may differ without changing value).", mismatches[:10], [])


FIGURE_PATHS = {
    "measurements_by_year": "docs/figure_source_data/figure_data_measurements_by_year.csv",
    "measurements_by_medium": "docs/figure_source_data/figure_data_measurements_by_medium.csv",
    "measurements_by_parameter": "docs/figure_source_data/figure_data_measurements_by_parameter.csv",
    "reports_by_year": "docs/figure_source_data/figure_data_reports_by_year.csv",
    "reports_by_facility_type": "docs/figure_source_data/figure_data_reports_by_facility_type.csv",
    "table_layer_scale": "docs/figure_source_data/figure_data_table_derived_layer_scale.csv",
}


def _sorted_counter_rows(counter: Counter, key_name: str, count_name: str, numeric_key: bool = False) -> List[Dict[str, object]]:
    if numeric_key:
        items = sorted(counter.items(), key=lambda item: int(item[0]))
    else:
        items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [{key_name: key, count_name: count} for key, count in items]


def figure_rows(root: Path, config: Mapping[str, object]) -> Dict[str, List[Dict[str, object]]]:
    files = required_files(config)
    measurements = list(iter_csv_rows(root / files["curated_measurements"]))
    inventory = list(iter_csv_rows(root / files["report_inventory"]))
    counts = expected_counts(config)
    scale = [
        {"layer": "Parsed DOCX reports", "count": counts["parsed_docx_reports"], "unit": "reports", "notes": "Reports with machine-readable DOCX table structures"},
        {"layer": "Public table-cell records", "count": counts["table_cells"], "unit": "records", "notes": "De-identified structural records with redacted placeholders or hashes"},
        {"layer": "Broad measurement candidate rows", "count": counts["measurement_candidates"], "unit": "rows", "notes": "Possible measurement evidence before conservative acceptance"},
        {"layer": "Numeric-token candidates", "count": counts["numeric_tokens"], "unit": "tokens", "notes": "Numeric expressions from candidate contexts"},
        {"layer": "Standardized parameter-row candidates", "count": counts["standardized_parameter_rows"], "unit": "records", "notes": "Candidate rows linked to standardized parameter codes"},
        {"layer": "Curated measurements", "count": counts["curated_measurements"], "unit": "records", "notes": "Corrected public long-form measurement layer after full scan and targeted source-report follow-up"},
        {"layer": "Pollutant dictionary", "count": counts["parameter_codes"], "unit": "parameter_codes", "notes": "Standard parameter codes used for harmonisation"},
    ]
    return {
        "measurements_by_year": _sorted_counter_rows(count_values(measurements, "year"), "year", "measurement_count", True),
        "measurements_by_medium": _sorted_counter_rows(count_values(measurements, "media"), "media", "measurement_count"),
        "measurements_by_parameter": _sorted_counter_rows(count_values(measurements, "parameter_code"), "parameter_code", "measurement_count"),
        "reports_by_year": _sorted_counter_rows(count_values(inventory, "year"), "name", "count", True),
        "reports_by_facility_type": _sorted_counter_rows(count_values(inventory, "facility_type"), "name", "count"),
        "table_layer_scale": scale,
    }


def write_figure_outputs(root: Path, out_dir: Path, config: Mapping[str, object]) -> None:
    products = figure_rows(root, config)
    fields = {
        "measurements_by_year": ["year", "measurement_count"],
        "measurements_by_medium": ["media", "measurement_count"],
        "measurements_by_parameter": ["parameter_code", "measurement_count"],
        "reports_by_year": ["name", "count"],
        "reports_by_facility_type": ["name", "count"],
        "table_layer_scale": ["layer", "count", "unit", "notes"],
    }
    for name, rows in products.items():
        write_csv_rows(out_dir / Path(FIGURE_PATHS[name]).name, fields[name], rows)


def validate_figures(root: Path, report: ValidationReport, config: Mapping[str, object]) -> None:
    for name, generated in figure_rows(root, config).items():
        existing = read_csv_rows(root / FIGURE_PATHS[name])
        normalized = [{key: str(value) for key, value in row.items()} for row in generated]
        report.add(f"figure rebuilt: {name}", existing == normalized, "Deposited figure source equals a fresh rebuild from v5.5 tables.")


def validate_schema_and_docs(root: Path, report: ValidationReport, config: Mapping[str, object]) -> None:
    files = required_files(config)
    counts = expected_counts(config)
    schema_rows = read_csv_rows(root / files["schema"])
    schema_by_file: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in schema_rows:
        schema_by_file[row["file_name"]].append(row)
    actual_csv = {
        path.name: path
        for path in iter_release_files(root)
        if path.suffix.lower() == ".csv" and path.name not in {Path(files["schema"]).name, Path(files["manifest"]).name}
    }
    report.add("schema active CSV coverage", set(schema_by_file) == set(actual_csv), "Schema covers every active release CSV except the circular schema and manifest files.", sorted(set(schema_by_file) ^ set(actual_csv)), [])
    mismatches: List[object] = []
    for name, path in actual_csv.items():
        header, row_count = csv_header_and_count(path)
        definitions = schema_by_file.get(name, [])
        fields = [row["field_name"] for row in definitions]
        documented_counts = {row["row_count"] for row in definitions}
        if fields != header or documented_counts != {str(row_count)} or len(fields) != len(set(fields)):
            mismatches.append({"file": name, "actual_rows": row_count, "documented_rows": sorted(documented_counts), "header_match": fields == header})
    report.add("schema headers and row counts", not mismatches, "Each active CSV has exact ordered field coverage and the correct row count.", mismatches[:10], [])
    report.add("schema represented file count", len(schema_by_file) == counts["schema_files"], "Schema represents 44 active CSV files.", len(schema_by_file), counts["schema_files"])
    vocab = read_csv_rows(root / files["controlled_vocabularies"])
    stale = [row["file_name"] for row in vocab if row["file_name"] not in {path.name for path in iter_release_files(root)} or "single_reviewer" in row["file_name"] or "template" in row["file_name"]]
    report.add("controlled vocabularies use active files", not stale, "Controlled-vocabulary entries contain no stale single-reviewer/template file references.", stale[:10], [])
    main_name = Path(files["curated_measurements"]).name
    dual_name = Path(files["dual_qa_csv"]).name
    challenge_name = Path(files["challenge_qa_csv"]).name
    texts = {
        "README.md": (root / "README.md").read_text(encoding="utf-8-sig"),
        files["schema"]: (root / files["schema"]).read_text(encoding="utf-8-sig"),
        files["manifest"]: (root / files["manifest"]).read_text(encoding="utf-8-sig"),
    }
    for label, text in texts.items():
        report.add(f"current files documented: {label}", all(name in text for name in (main_name, dual_name, challenge_name)), "Main table and both completed QA CSVs are documented.")
    for path in (root / "README.md", root / "docs" / "geographic_scope_and_representativeness.md"):
        content = path.read_text(encoding="utf-8-sig")
        report.add(f"geographic scope: {path.name}", str(config["geographic_scope"]) in content, "Guizhou scope is explicit.")
    inaccurate: List[str] = []
    corpus_pattern = re.compile(r"\breport corpus\b|\bprivate source corpus\b", re.IGNORECASE)
    for path in iter_release_files(root):
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
            if any(corpus_pattern.search(line) for line in handle):
                inaccurate.append(rel_path(root, path))
    report.add("no inaccurate corpus terminology", not inaccurate, "Formal release files avoid full-text-corpus implications.", inaccurate, [])
    report.add("current filename excludes draft", "draft" not in main_name.lower(), "The current main filename does not contain draft.")


def validate_table_row_semantics(root: Path, report: ValidationReport, config: Mapping[str, object]) -> None:
    files = required_files(config)
    counts = expected_counts(config)
    source_rows = {row["report_id"]: int(row["table_row_count"]) for row in iter_csv_rows(root / files["docx_metadata"])}
    # Cells belonging to one public (report, table, row) locator are contiguous
    # in the hash-pinned release table. Count locator transitions instead of
    # retaining 125,045 tuples, which substantially reduces peak memory.
    public_rows: Counter = Counter()
    previous_locator: Optional[Tuple[str, str, str]] = None
    for row in iter_csv_rows(root / files["table_cells"]):
        locator = (row["report_id"], row["table_id"], row["row_index"])
        if locator != previous_locator:
            public_rows[row["report_id"]] += 1
            previous_locator = locator
    differences = {report_id: total - public_rows.get(report_id, 0) for report_id, total in source_rows.items() if total > public_rows.get(report_id, 0)}
    negative = {report_id: total - public_rows.get(report_id, 0) for report_id, total in source_rows.items() if total < public_rows.get(report_id, 0)}
    ok = not negative and len(differences) == counts["table_row_count_difference_reports"] and sum(differences.values()) == counts["table_row_count_difference_rows"]
    report.add("table_row_count semantics recomputed", ok, "Source-parser totals exceed released nonblank row locators for exactly 41 reports and 146 rows, with no negative differences.", {"positive_reports": len(differences), "positive_rows": sum(differences.values()), "negative_reports": len(negative)}, {"positive_reports": 41, "positive_rows": 146, "negative_reports": 0})


def validate_summary_metadata(root: Path, report: ValidationReport, config: Mapping[str, object]) -> None:
    files = required_files(config)
    counts = expected_counts(config)
    build = json.loads((root / files["release_build_summary"]).read_text(encoding="utf-8-sig"))
    observed = build.get("counts", {})
    expected = {
        "report_inventory": counts["report_inventory"],
        "parsed_docx_reports": counts["parsed_docx_reports"],
        "table_cells": counts["table_cells"],
        "measurement_candidates": counts["measurement_candidates"],
        "standardized_parameter_rows": counts["standardized_parameter_rows"],
        "numeric_tokens": counts["numeric_tokens"],
        "initial_measurements": counts["initial_measurements"],
        "pre_v5_curated_measurements": counts["pre_v5_curated_measurements"],
        "v5_curated_measurements": counts["curated_measurements"],
        "stratified_dual_review_records": counts["dual_qa_records"],
        "targeted_challenge_records": counts["challenge_qa_records"],
        "parameter_codes": counts["parameter_codes"],
    }
    report.add("release-build summary counts", all(observed.get(key) == value for key, value in expected.items()), "Deposited build summary agrees with configured v5.5 counts.", {key: observed.get(key) for key in expected}, expected)
    correction = build.get("v5_correction", {})
    correction_expected = {"excluded_records": 1392, "output_records": 19122, "media_group_corrections": 58, "unit_corrections": 20, "floating_value_canonicalizations": 56, "limit_unit_corrections": 17, "censored_compliance_pass_to_uncertain": 37, "arsenic_microgram_value_normalizations": 8, "arsenic_compliance_flag_changes": 5}
    report.add("release-build correction counts", all(correction.get(key) == value for key, value in correction_expected.items()), "Deposited build summary records all v5/v5.5 corrections.", {key: correction.get(key) for key in correction_expected}, correction_expected)
    report.add("release-build main hash", build.get("main_measurement_v5_sha256") == config.get("expected_main_measurement_sha256"), "Build summary records the exact current-main SHA-256.")
    qa_summary = json.loads((root / files["qa_stage_summary"]).read_text(encoding="utf-8-sig"))
    qa_ok = qa_summary.get("stratified_800", {}).get("final_total_exclusions") == 54 and qa_summary.get("targeted_challenge", {}).get("final_total_exclusions") == 52 and qa_summary.get("v5_5_post_review_corrections", {}).get("frozen_r1_r2_fields_overwritten") is False
    report.add("QA stage summary synchronized", qa_ok, "Deposited QA summary preserves stage counts and confirms frozen R1/R2 fields were not overwritten.")
    readiness = json.loads((root / files["publication_readiness"]).read_text(encoding="utf-8-sig"))
    readiness_ok = readiness.get("current_measurement_records") == 19122 and readiness.get("cumulative_exclusions") == 1392 and readiness.get("remaining_fecal_limit_unit_mismatches") == 0 and readiness.get("remaining_censored_compliance_pass_ambiguities") == 0 and readiness.get("remaining_arsenic_microgram_value_normalization_issues") == 0
    report.add("publication-readiness logic synchronized", readiness_ok, "Deposited readiness report records zero remaining v5.5 logic issues and current counts.")


def validate_doi_values(report: ValidationReport, config: Mapping[str, object]) -> None:
    for key in ("data_doi", "code_doi"):
        value = str(config.get(key, ""))
        ok = not value or bool(DOI_RE.fullmatch(value))
        report.add(f"DOI value: {key}", ok, "DOI is either a valid assigned DOI or blank while unassigned.", value)


def validate_disclosure(root: Path, report: ValidationReport) -> None:
    """Stream disclosure checks without repeated regular expressions over large CSVs."""

    original_reports: List[str] = []
    sensitive_hits: List[Dict[str, object]] = []
    labels = (
        "private data directory",
        "private crosswalk",
        "raw report text field",
        "absolute Windows user path",
        "source file path field",
    )

    def matched_labels(line: str) -> List[str]:
        lowered = line.lower()
        normalized = lowered.replace("\\", "/")
        found: List[str] = []
        if "data_private/" in normalized or normalized.strip() == "data_private":
            found.append("private data directory")
        if "source_crosswalk_private" in lowered or "crosswalk_private" in lowered:
            found.append("private crosswalk")
        if any(token in lowered for token in ("raw_report_text", "report_text_raw", "row_text_private")):
            found.append("raw report text field")
        if ":/users/" in normalized:
            found.append("absolute Windows user path")
        if any(token in lowered for token in ("source_file_path", "original_file_path", "absolute_path")):
            found.append("source file path field")
        return found

    for path in iter_release_files(root):
        relative = rel_path(root, path)
        if path.suffix.lower() in ORIGINAL_REPORT_EXTENSIONS:
            original_reports.append(relative)
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        recorded_patterns: set[str] = set()
        with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
            for line_number, line in enumerate(handle, start=1):
                for label in matched_labels(line):
                    if label not in recorded_patterns:
                        sensitive_hits.append(
                            {"file": relative, "line": line_number, "pattern": label}
                        )
                        recorded_patterns.add(label)
                if len(recorded_patterns) == len(labels):
                    break
    report.add(
        "no original report files",
        not original_reports,
        "The public release contains no source DOC, DOCX, or PDF reports.",
        original_reports,
        [],
    )
    report.add(
        "no sensitive disclosure patterns",
        not sensitive_hits,
        "No private paths, crosswalks, or raw source-text fields were found.",
        sensitive_hits[:20],
        [],
    )


def validate_column_hashes(root: Path, report: ValidationReport, config: Mapping[str, object]) -> None:
    files = required_files(config)
    main = read_csv_rows(root / files["curated_measurements"])
    header, _ = csv_header_and_count(root / files["curated_measurements"])
    audit = read_csv_rows(root / files["column_hashes"])
    report.add("column-hash field coverage", [row["column_name"] for row in audit] == header, "Column-hash audit follows the exact main-table column order.")
    bad: List[str] = []
    for row in audit:
        column = row["column_name"]
        digest = hashlib.sha256(("\n".join(item[column] for item in main) + "\n").encode("utf-8")).hexdigest()
        identical = "true" if row["baseline_v4_sha256"] == row["corrected_v5_sha256"] else "false"
        if digest != row["corrected_v5_sha256"] or row["identical"] != identical or not SHA256_RE.fullmatch(row["baseline_v4_sha256"]):
            bad.append(column)
    report.add("main measurement column hashes", not bad, "Every corrected-v5 column hash is independently recomputed; baseline/current equality flags are truthful.", bad, [])


def validate_release(
    root: Path, config: Mapping[str, object], zip_info: Optional[Mapping[str, object]] = None
) -> ValidationReport:
    report = ValidationReport(config)
    if zip_info is not None:
        expected_zip = str(config.get("expected_release_zip_sha256", ""))
        report.add("release ZIP exact v5.5 hash", zip_info.get("sha256") == expected_zip, "Input ZIP is byte-identical to the confirmed Zenodo upload.", zip_info.get("sha256"), expected_zip)
    validate_manifest(root, report, config)
    validate_expected_counts(root, report, config)
    validate_curated_measurements(root, report, config)
    validate_identifiers(root, report, config)
    validate_qa(root, report, config)
    validate_v5_corrections(root, report, config)
    validate_figures(root, report, config)
    validate_schema_and_docs(root, report, config)
    validate_table_row_semantics(root, report, config)
    validate_summary_metadata(root, report, config)
    validate_doi_values(report, config)
    validate_disclosure(root, report)
    validate_column_hashes(root, report, config)
    return report


def release_summary(root: Path, config: Mapping[str, object], zip_info: Optional[Mapping[str, object]] = None) -> Dict[str, object]:
    table_counts: Dict[str, object] = {}
    for relative in expected_table_counts(config):
        header, rows = csv_header_and_count(root / relative)
        table_counts[relative] = {"rows": rows, "columns": len(header)}
    files = required_files(config)
    return {
        "dataset_title": config["dataset_title"],
        "dataset_version": config["dataset_version"],
        "dataset_correction_state": config["dataset_correction_state"],
        "configured_data_doi": config["data_doi"],
        "previous_data_version_doi": config.get("previous_data_version_doi", ""),
        "geographic_scope": config["geographic_scope"],
        "temporal_coverage": [config["temporal_start"], config["temporal_end"]],
        "zip": dict(zip_info) if zip_info else None,
        "main_measurement_sha256": sha256_file(root / files["curated_measurements"]),
        "manifest_sha256": sha256_file(root / files["manifest"]),
        "table_counts": table_counts,
        "qa": {
            "stratified_800": qa_metrics(read_csv_rows(root / files["dual_qa_csv"])),
            "targeted_challenge": qa_metrics(read_csv_rows(root / files["challenge_qa_csv"])),
        },
        "figure_source_data": figure_rows(root, config),
    }


def write_markdown_report(path: Path, report: ValidationReport) -> None:
    lines = [
        "# EnvCoRe-SW public release validation",
        "",
        f"Dataset version: {report.config['dataset_version']} ({report.config['dataset_correction_state']} correction state)",
        f"Configured data DOI: {report.config['data_doi'] or 'not assigned'}",
        f"Geographic scope: {report.config['geographic_scope']}",
        f"Generated at UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Validation status: {'PASS' if report.passed else 'FAIL'}",
        "",
        "## Checks",
        "",
    ]
    for check in report.checks:
        lines.append(f"- {check['status']}: {check['name']} — {check['detail']}")
        if check["status"] != "PASS":
            lines.append(f"  - observed: {check.get('observed')}")
            lines.append(f"  - expected: {check.get('expected')}")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _with_release(args: argparse.Namespace):
    config = load_config(args.config)
    root, temporary, zip_info = prepare_release(Path(args.release), config)
    return config, root, temporary, zip_info


def command_validate(args: argparse.Namespace) -> int:
    config, root, temporary, zip_info = _with_release(args)
    try:
        report = validate_release(root, config, zip_info)
        out = Path(args.out)
        write_json(out / "validation_report.json", report.to_dict())
        write_markdown_report(out / "validation_report.md", report)
        print(f"Validation status: {'PASS' if report.passed else 'FAIL'}")
        return 0 if report.passed else 1
    finally:
        if temporary is not None:
            temporary.cleanup()


def command_figures(args: argparse.Namespace) -> int:
    config, root, temporary, _zip_info = _with_release(args)
    try:
        write_figure_outputs(root, Path(args.out), config)
        print(f"Wrote regenerated figure source data to {args.out}")
        return 0
    finally:
        if temporary is not None:
            temporary.cleanup()


def command_summary(args: argparse.Namespace) -> int:
    config, root, temporary, zip_info = _with_release(args)
    try:
        write_json(Path(args.out), release_summary(root, config, zip_info))
        print(f"Wrote {args.out}")
        return 0
    finally:
        if temporary is not None:
            temporary.cleanup()


def command_manifest(args: argparse.Namespace) -> int:
    config, root, temporary, _zip_info = _with_release(args)
    try:
        rows = generate_manifest_rows(root, manifest_descriptions(root, config))
        write_csv_rows(Path(args.out), MANIFEST_FIELDS, rows)
        print(f"Wrote {args.out}")
        return 0
    finally:
        if temporary is not None:
            temporary.cleanup()


def command_all(args: argparse.Namespace) -> int:
    config, root, temporary, zip_info = _with_release(args)
    try:
        out = Path(args.out)
        prepare_all_output_directory(out, args.clean, root)
        write_figure_outputs(root, out / "figure_source_data_rebuilt", config)
        write_json(out / "release_summary.json", release_summary(root, config, zip_info))
        write_csv_rows(out / "regenerated_manifest.csv", MANIFEST_FIELDS, generate_manifest_rows(root, manifest_descriptions(root, config)))
        report = validate_release(root, config, zip_info)
        write_json(out / "validation_report.json", report.to_dict())
        write_markdown_report(out / "validation_report.md", report)
        print(f"Validation status: {'PASS' if report.passed else 'FAIL'}")
        print(f"Wrote all outputs to {out}")
        return 0 if report.passed else 1
    finally:
        if temporary is not None:
            temporary.cleanup()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EnvCoRe-SW v5/v5.5 public release validation and figure tools")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to release_config.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_release_out(command: argparse.ArgumentParser, default: str) -> None:
        command.add_argument("--release", required=True, help="Exact release directory or ZIP")
        command.add_argument("--out", default=default, help="Output path")

    validate = subparsers.add_parser("validate", help="Validate the public release")
    add_release_out(validate, "outputs/validation_check")
    validate.set_defaults(func=command_validate)
    figures = subparsers.add_parser("figures", help="Rebuild figure source data")
    add_release_out(figures, "outputs/figure_source_data_rebuilt")
    figures.set_defaults(func=command_figures)
    summary = subparsers.add_parser("summary", help="Write release counts and metadata as JSON")
    add_release_out(summary, "outputs/release_summary.json")
    summary.set_defaults(func=command_summary)
    manifest = subparsers.add_parser("manifest", help="Regenerate the technical manifest")
    add_release_out(manifest, "outputs/regenerated_manifest.csv")
    manifest.set_defaults(func=command_manifest)
    all_command = subparsers.add_parser("all", help="Validate and rebuild all public reproducibility outputs")
    add_release_out(all_command, "outputs/reproducibility_check")
    all_command.add_argument("--clean", action="store_true", help="Remove a safe output directory before writing")
    all_command.set_defaults(func=command_all)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
