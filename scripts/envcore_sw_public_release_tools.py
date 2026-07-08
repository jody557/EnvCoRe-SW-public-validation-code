#!/usr/bin/env python3
"""Public reproducibility tools for the EnvCoRe-SW corrected v3 release.

The script intentionally uses only the Python standard library. It validates
the de-identified public data package and regenerates manuscript-facing counts
and figure source data from the public CSV files.
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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


DATASET_DOI = "https://doi.org/10.5281/zenodo.21231126"
RELEASE_VERSION = "corrected_v3_20260705"
EXPECTED_ZIP_SHA256 = "ada5e6ac419fdcaa2488eedf67d220632354115fbf71ef8f872832180f6102a3"
EXPECTED_ZIP_MD5 = "763f3a37618a3c72e61df9a82b8b1361"
EXPECTED_ZIP_SIZE_BYTES = 33509037

EXPECTED_TOTAL_FILES_IN_RELEASE = 47
EXPECTED_MANIFEST_ROWS = 46

EXPECTED_CSV_COUNTS = {
    "data_public/report_inventory_public.csv": (8265, 14),
    "data_public/docx_report_metadata_public.csv": (2004, 14),
    "data_public/docx_table_cells_public.csv": (552375, 7),
    "data_public/measurement_candidates_public.csv": (43822, 7),
    "data_public/measurement_row_candidates_standardized_public.csv": (63075, 23),
    "data_public/measurement_token_candidates_public.csv": (344682, 21),
    "data_public/measurements_long_draft_public.csv": (21073, 31),
    "data_public/measurements_long_draft_public_corrected_v3.csv": (20514, 31),
    "data_public/human_manual_qa_review_template_800_v3_final.csv": (800, 83),
    "data_public/pollutant_dictionary.csv": (34, 7),
    "docs/correction_history/frequency_context_false_accept_candidates.csv": (559, 36),
    "docs/correction_history/ammonia_parameter_mapping_correction_audit.csv": (1096, 38),
}

KEY_FILES = {
    "manifest": "public_dataset_manifest.csv",
    "report_inventory": "data_public/report_inventory_public.csv",
    "docx_metadata": "data_public/docx_report_metadata_public.csv",
    "docx_table_cells": "data_public/docx_table_cells_public.csv",
    "measurement_candidates": "data_public/measurement_candidates_public.csv",
    "standardized_candidates": "data_public/measurement_row_candidates_standardized_public.csv",
    "token_candidates": "data_public/measurement_token_candidates_public.csv",
    "measurements_original": "data_public/measurements_long_draft_public.csv",
    "measurements_corrected": "data_public/measurements_long_draft_public_corrected_v3.csv",
    "human_qa": "data_public/human_manual_qa_review_template_800_v3_final.csv",
    "pollutant_dictionary": "data_public/pollutant_dictionary.csv",
    "frequency_removed": "docs/correction_history/frequency_context_false_accept_candidates.csv",
    "ammonia_audit": "docs/correction_history/ammonia_parameter_mapping_correction_audit.csv",
    "color_audit": "docs/correction_history/color_unit_source_audit.csv",
    "corrected_generation_summary": "docs/validation/corrected_v3_generation_summary.json",
    "dataset_schema": "docs/metadata_schema/dataset_schema.csv",
    "validation_report": "docs/validation/public_release_validation_report_corrected_v3.md",
}

FIGURE_FILES = {
    "measurements_by_year": "docs/figure_source_data/figure_data_draft_measurements_by_year_corrected_v3.csv",
    "measurements_by_medium": "docs/figure_source_data/figure_data_draft_measurements_by_medium_corrected_v3.csv",
    "measurements_by_parameter": "docs/figure_source_data/figure_data_draft_measurements_by_parameter_corrected_v3.csv",
    "reports_by_year": "docs/figure_source_data/figure_data_reports_by_year.csv",
    "reports_by_facility_type": "docs/figure_source_data/figure_data_reports_by_facility_type.csv",
    "table_layer_scale": "docs/figure_source_data/figure_data_table_derived_layer_scale_corrected_v3.csv",
}

SENSITIVE_DISCLOSURE_PATTERNS = [
    ("data_private_path", re.compile(r"data_private[\\/]|\bdata_private\b", re.IGNORECASE)),
    ("source_crosswalk_private", re.compile(r"source_crosswalk_private", re.IGNORECASE)),
    ("private_row_text_column", re.compile(r"\brow_text_private\b", re.IGNORECASE)),
    ("raw_report_text_column", re.compile(r"\braw_report_text\b|\breport_text_raw\b", re.IGNORECASE)),
    ("local_windows_user_path", re.compile(r"[A-Za-z]:[\\/](Users[\\/]57049|jianhui data|.*?Documents[\\/]Codex)", re.IGNORECASE)),
    ("source_file_path_column", re.compile(r"\b(source_file_path|original_file_path|absolute_path)\b", re.IGNORECASE)),
    ("assistant_or_chatgpt_trace", re.compile(r"\b(ChatGPT|OpenAI assistant|assistant_source_context|AI-generated)\b", re.IGNORECASE)),
]

TEXT_EXTENSIONS_TO_SCAN = {".csv", ".md", ".json", ".txt", ".cff"}
ORIGINAL_REPORT_EXTENSIONS = {".doc", ".docx", ".pdf"}


class ValidationReport:
    def __init__(self) -> None:
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
        return all(check["status"] == "PASS" for check in self.checks)

    def to_dict(self) -> Dict[str, object]:
        return {
            "dataset_doi": DATASET_DOI,
            "release_version": RELEASE_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "PASS" if self.passed else "FAIL",
            "checks": self.checks,
        }


def normalize_rel(path: Path) -> str:
    return path.as_posix()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_header_and_count(path: Path) -> Tuple[List[str], int]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return [], 0
        rows = sum(1 for _ in reader)
    return header, rows


def iter_csv_rows(path: Path) -> Iterable[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {k: (v if v is not None else "") for k, v in row.items()}


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    return list(iter_csv_rows(path))


def write_csv_rows(path: Path, fieldnames: List[str], rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def iter_release_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def _is_inside(child: Path, parent: Path) -> bool:
    child_resolved = child.resolve()
    parent_resolved = parent.resolve()
    try:
        child_resolved.relative_to(parent_resolved)
        return True
    except ValueError:
        return False


def safe_extract_zip(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = dest / member.filename
            if not _is_inside(target, dest):
                raise ValueError(f"Unsafe path in ZIP: {member.filename}")
        zf.extractall(dest)


def locate_release_root(path: Path) -> Path:
    if (path / KEY_FILES["manifest"]).exists():
        return path
    matches = list(path.rglob(KEY_FILES["manifest"]))
    if len(matches) == 1:
        return matches[0].parent
    if not matches:
        raise FileNotFoundError(f"Could not find {KEY_FILES['manifest']} under {path}")
    raise ValueError(f"Found multiple manifest files under {path}; provide the release root explicitly.")


def prepare_release(path: Path) -> Tuple[Path, Optional[tempfile.TemporaryDirectory], Optional[Dict[str, object]]]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_file() and path.suffix.lower() == ".zip":
        zip_info = {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "md5": md5_file(path),
        }
        tmp = tempfile.TemporaryDirectory(prefix="envcore_sw_release_")
        safe_extract_zip(path, Path(tmp.name))
        return locate_release_root(Path(tmp.name)), tmp, zip_info
    return locate_release_root(path), None, None


def rel_path(root: Path, path: Path) -> str:
    return normalize_rel(path.relative_to(root))


def generate_technical_manifest(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in iter_release_files(root):
        relative_path = rel_path(root, path)
        if relative_path == KEY_FILES["manifest"]:
            continue
        row_count = ""
        column_count = ""
        columns = ""
        if path.suffix.lower() == ".csv":
            header, count = csv_header_and_count(path)
            row_count = count
            column_count = len(header)
            columns = ";".join(header)
        rows.append(
            {
                "file_name": path.name,
                "relative_path": relative_path,
                "file_size_bytes": path.stat().st_size,
                "row_count": row_count,
                "column_count": column_count,
                "columns": columns,
                "sha256": sha256_file(path),
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
    return rows


def validate_zip_info(zip_info: Optional[Dict[str, object]], report: ValidationReport) -> None:
    if zip_info is None:
        report.add("zip checksum", True, "Release was supplied as an extracted directory; ZIP checksum not checked.")
        return
    report.add(
        "zip size",
        zip_info["size_bytes"] == EXPECTED_ZIP_SIZE_BYTES,
        "Published ZIP size matches the corrected v3 reference value.",
        observed=zip_info["size_bytes"],
        expected=EXPECTED_ZIP_SIZE_BYTES,
    )
    report.add(
        "zip sha256",
        zip_info["sha256"] == EXPECTED_ZIP_SHA256,
        "Published ZIP SHA-256 matches the corrected v3 reference value.",
        observed=zip_info["sha256"],
        expected=EXPECTED_ZIP_SHA256,
    )
    report.add(
        "zip md5",
        zip_info["md5"] == EXPECTED_ZIP_MD5,
        "Published ZIP MD5 matches the corrected v3 Zenodo file checksum.",
        observed=zip_info["md5"],
        expected=EXPECTED_ZIP_MD5,
    )


def validate_manifest(root: Path, report: ValidationReport) -> None:
    manifest_path = root / KEY_FILES["manifest"]
    manifest_rows = read_csv_rows(manifest_path)
    files = list(iter_release_files(root))
    report.add(
        "manifest row count",
        len(manifest_rows) == EXPECTED_MANIFEST_ROWS,
        "Manifest lists the expected number of package files, excluding itself.",
        observed=len(manifest_rows),
        expected=EXPECTED_MANIFEST_ROWS,
    )
    report.add(
        "release file count",
        len(files) == EXPECTED_TOTAL_FILES_IN_RELEASE,
        "Release directory contains the expected total number of files, including the manifest.",
        observed=len(files),
        expected=EXPECTED_TOTAL_FILES_IN_RELEASE,
    )

    listed_paths = [row["relative_path"].replace("\\", "/") for row in manifest_rows]
    report.add(
        "manifest excludes itself",
        KEY_FILES["manifest"] not in listed_paths,
        "The public manifest intentionally does not list public_dataset_manifest.csv itself.",
        observed=KEY_FILES["manifest"] in listed_paths,
        expected=False,
    )

    actual_paths = {rel_path(root, p): p for p in files}
    missing = [p for p in listed_paths if p not in actual_paths]
    unlisted = sorted(set(actual_paths) - set(listed_paths) - {KEY_FILES["manifest"]})
    report.add("manifest listed files exist", not missing, "Every manifest-listed file exists.", observed=missing, expected=[])
    report.add("no unlisted data files", not unlisted, "No non-manifest files are present apart from the manifest.", observed=unlisted, expected=[])

    for row in manifest_rows:
        relative_path = row["relative_path"].replace("\\", "/")
        path = root / relative_path
        if not path.exists():
            continue
        expected_size = int(row["file_size_bytes"]) if row.get("file_size_bytes") else None
        report.add(
            f"file size: {relative_path}",
            expected_size is None or path.stat().st_size == expected_size,
            "File size matches manifest.",
            observed=path.stat().st_size,
            expected=expected_size,
        )
        expected_sha = row.get("sha256", "")
        actual_sha = sha256_file(path)
        report.add(
            f"sha256: {relative_path}",
            actual_sha == expected_sha,
            "SHA-256 matches manifest.",
            observed=actual_sha,
            expected=expected_sha,
        )
        if path.suffix.lower() == ".csv":
            header, count = csv_header_and_count(path)
            expected_rows = int(row["row_count"]) if row.get("row_count") else None
            expected_cols = int(row["column_count"]) if row.get("column_count") else None
            expected_columns = row.get("columns", "")
            report.add(
                f"csv row count: {relative_path}",
                expected_rows is None or count == expected_rows,
                "CSV row count matches manifest.",
                observed=count,
                expected=expected_rows,
            )
            report.add(
                f"csv column count: {relative_path}",
                expected_cols is None or len(header) == expected_cols,
                "CSV column count matches manifest.",
                observed=len(header),
                expected=expected_cols,
            )
            report.add(
                f"csv columns: {relative_path}",
                ";".join(header) == expected_columns,
                "CSV header matches manifest column list.",
                observed=";".join(header),
                expected=expected_columns,
            )


def validate_expected_counts(root: Path, report: ValidationReport) -> None:
    for relative_path, (expected_rows, expected_cols) in EXPECTED_CSV_COUNTS.items():
        path = root / relative_path
        if not path.exists():
            report.add(f"expected file exists: {relative_path}", False, "Required public CSV is missing.")
            continue
        header, rows = csv_header_and_count(path)
        report.add(
            f"expected rows: {relative_path}",
            rows == expected_rows,
            "Required CSV has the expected row count.",
            observed=rows,
            expected=expected_rows,
        )
        report.add(
            f"expected columns: {relative_path}",
            len(header) == expected_cols,
            "Required CSV has the expected column count.",
            observed=len(header),
            expected=expected_cols,
        )


def duplicate_count(values: Iterable[str]) -> int:
    seen = set()
    duplicates = 0
    for value in values:
        if value in seen:
            duplicates += 1
        else:
            seen.add(value)
    return duplicates


def validate_cross_file_links(root: Path, report: ValidationReport) -> None:
    inventory_ids = {row["report_id"] for row in iter_csv_rows(root / KEY_FILES["report_inventory"])}
    corrected_rows = read_csv_rows(root / KEY_FILES["measurements_corrected"])
    corrected_measurement_ids = [row["measurement_id"] for row in corrected_rows]
    corrected_measurement_id_set = set(corrected_measurement_ids)
    corrected_candidate_ids = {row["measurement_row_candidate_id"] for row in corrected_rows}
    corrected_parameter_codes = {row["parameter_code"] for row in corrected_rows}
    standardized_candidate_ids = {
        row["measurement_row_candidate_id"] for row in iter_csv_rows(root / KEY_FILES["standardized_candidates"])
    }
    pollutant_codes = {row["parameter_code"] for row in iter_csv_rows(root / KEY_FILES["pollutant_dictionary"])}
    qa_rows = read_csv_rows(root / KEY_FILES["human_qa"])
    qa_measurement_ids = {row["measurement_id"] for row in qa_rows}

    missing_reports = sorted({row["report_id"] for row in corrected_rows} - inventory_ids)
    missing_candidates = sorted(corrected_candidate_ids - standardized_candidate_ids)
    missing_parameters = sorted(corrected_parameter_codes - pollutant_codes)
    missing_qa_measurements = sorted(qa_measurement_ids - corrected_measurement_id_set)

    report.add(
        "corrected duplicate measurement IDs",
        duplicate_count(corrected_measurement_ids) == 0,
        "Corrected v3 measurement IDs are unique.",
        observed=duplicate_count(corrected_measurement_ids),
        expected=0,
    )
    report.add("corrected report IDs link to inventory", not missing_reports, "All corrected report IDs exist in report inventory.", observed=missing_reports, expected=[])
    report.add(
        "corrected row candidates link to standardized layer",
        not missing_candidates,
        "All corrected measurement-row candidate IDs exist in the standardized candidate layer.",
        observed=missing_candidates[:10],
        expected=[],
    )
    report.add(
        "corrected parameter codes link to dictionary",
        not missing_parameters,
        "All corrected parameter codes exist in pollutant_dictionary.csv.",
        observed=missing_parameters,
        expected=[],
    )
    report.add(
        "human QA measurement IDs link to corrected table",
        not missing_qa_measurements,
        "All human QA measurement IDs exist in the corrected v3 measurement table.",
        observed=missing_qa_measurements[:10],
        expected=[],
    )


def count_values(rows: Iterable[Dict[str, str]], field: str) -> Counter:
    counter: Counter = Counter()
    for row in rows:
        counter[row.get(field, "")] += 1
    return counter


def validate_human_qa(root: Path, report: ValidationReport) -> None:
    qa_rows = read_csv_rows(root / KEY_FILES["human_qa"])
    checks = {
        "human_review_status": ("reviewed", 800),
        "human_reviewer_id": ("R1", 800),
        "human_review_date": ("2026-07-03", 800),
        "human_accepted_measurement_supported": ("yes", 800),
        "human_false_accept": ("no", 800),
        "human_error_category": ("none", 800),
        "adjudication_required": ("no", 800),
    }
    for field, (expected_value, expected_count) in checks.items():
        counter = count_values(qa_rows, field)
        observed = counter.get(expected_value, 0)
        report.add(
            f"human QA {field}",
            observed == expected_count,
            f"Human QA field {field} has the expected completed-review value.",
            observed=dict(counter),
            expected={expected_value: expected_count},
        )
    report.add(
        "human QA duplicate sample IDs",
        duplicate_count(row["qa_sample_id"] for row in qa_rows) == 0,
        "Human QA sample IDs are unique.",
        observed=duplicate_count(row["qa_sample_id"] for row in qa_rows),
        expected=0,
    )
    report.add(
        "human QA duplicate measurement IDs",
        duplicate_count(row["measurement_id"] for row in qa_rows) == 0,
        "Human QA measurement IDs are unique.",
        observed=duplicate_count(row["measurement_id"] for row in qa_rows),
        expected=0,
    )


def validate_correction_history(root: Path, report: ValidationReport) -> None:
    original_rows = read_csv_rows(root / KEY_FILES["measurements_original"])
    corrected_rows = read_csv_rows(root / KEY_FILES["measurements_corrected"])
    removed_rows = read_csv_rows(root / KEY_FILES["frequency_removed"])
    ammonia_rows = read_csv_rows(root / KEY_FILES["ammonia_audit"])

    original_ids = {row["measurement_id"] for row in original_rows}
    corrected_ids = {row["measurement_id"] for row in corrected_rows}
    removed_ids = {row["measurement_id"] for row in removed_rows}

    report.add(
        "frequency-context removal count",
        len(removed_rows) == 559,
        "Frequency-context false accepts removed from measurement layer.",
        observed=len(removed_rows),
        expected=559,
    )
    report.add(
        "original minus corrected equals removed count",
        len(original_rows) - len(corrected_rows) == len(removed_rows),
        "The original-to-corrected row-count decrease equals the removed frequency-context row count.",
        observed=len(original_rows) - len(corrected_rows),
        expected=len(removed_rows),
    )
    report.add(
        "removed IDs present in original draft",
        removed_ids <= original_ids,
        "All removed measurement IDs were present in the superseded original draft table.",
        observed=len(removed_ids - original_ids),
        expected=0,
    )
    report.add(
        "removed IDs absent from corrected v3",
        not (removed_ids & corrected_ids),
        "Removed frequency-context measurement IDs are absent from corrected v3.",
        observed=len(removed_ids & corrected_ids),
        expected=0,
    )
    ammonia_ok = all(
        row.get("old_parameter_code") == "ammonia_air" and row.get("new_parameter_code") == "ammonia_nitrogen"
        for row in ammonia_rows
    )
    report.add(
        "ammonia correction count",
        len(ammonia_rows) == 1096,
        "Water-context ammonia_air rows recoded to ammonia_nitrogen.",
        observed=len(ammonia_rows),
        expected=1096,
    )
    report.add(
        "ammonia correction mapping",
        ammonia_ok,
        "Every ammonia correction audit row maps ammonia_air to ammonia_nitrogen.",
        observed="all rows match" if ammonia_ok else "one or more rows differ",
        expected="all rows match",
    )

    summary_path = root / KEY_FILES["corrected_generation_summary"]
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        report.add(
            "color unit recode count",
            summary.get("color_platinum_cobalt_unit_recoded_to_degree") == 7,
            "Corrected generation summary records 7 color unit recodes to degree.",
            observed=summary.get("color_platinum_cobalt_unit_recoded_to_degree"),
            expected=7,
        )


def figure_measurements_by_year(root: Path) -> List[Dict[str, object]]:
    counter = count_values(iter_csv_rows(root / KEY_FILES["measurements_corrected"]), "year")
    return [{"year": year, "draft_measurement_count": counter[year]} for year in sorted(counter, key=lambda y: int(y))]


def figure_measurements_by_medium(root: Path) -> List[Dict[str, object]]:
    counter = count_values(iter_csv_rows(root / KEY_FILES["measurements_corrected"]), "media")
    return [{"media": media, "draft_measurement_count": counter[media]} for media in sorted(counter)]


def figure_measurements_by_parameter(root: Path) -> List[Dict[str, object]]:
    counter = count_values(iter_csv_rows(root / KEY_FILES["measurements_corrected"]), "parameter_code")
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"parameter_code": key, "draft_measurement_count": value} for key, value in items]


def figure_reports_by_year(root: Path) -> List[Dict[str, object]]:
    counter = count_values(iter_csv_rows(root / KEY_FILES["report_inventory"]), "year")
    return [{"name": year, "count": counter[year]} for year in sorted(counter, key=lambda y: int(y))]


def figure_reports_by_facility_type(root: Path) -> List[Dict[str, object]]:
    counter = count_values(iter_csv_rows(root / KEY_FILES["report_inventory"]), "facility_type")
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"name": key, "count": value} for key, value in items]


def figure_table_layer_scale(root: Path) -> List[Dict[str, object]]:
    def rows_for(relative_path: str) -> int:
        return csv_header_and_count(root / relative_path)[1]

    return [
        {
            "layer": "Parsed DOCX reports",
            "count": rows_for(KEY_FILES["docx_metadata"]),
            "unit": "reports",
            "notes": "Reports with extractable DOCX table structures",
        },
        {
            "layer": "Public table-cell records",
            "count": rows_for(KEY_FILES["docx_table_cells"]),
            "unit": "records",
            "notes": "De-identified table-cell structural records",
        },
        {
            "layer": "Broad measurement candidate rows",
            "count": rows_for(KEY_FILES["measurement_candidates"]),
            "unit": "rows",
            "notes": "Rows with possible measurement evidence before conservative acceptance",
        },
        {
            "layer": "Numeric-token candidates",
            "count": rows_for(KEY_FILES["token_candidates"]),
            "unit": "tokens",
            "notes": "Numeric expressions extracted from candidate contexts",
        },
        {
            "layer": "Standardized parameter-row candidates",
            "count": rows_for(KEY_FILES["standardized_candidates"]),
            "unit": "records",
            "notes": "Candidate rows linked to standardized parameter codes",
        },
        {
            "layer": "Corrected v3 draft measurements",
            "count": rows_for(KEY_FILES["measurements_corrected"]),
            "unit": "records",
            "notes": "Current corrected draft long-form measurement layer",
        },
        {
            "layer": "Pollutant dictionary",
            "count": rows_for(KEY_FILES["pollutant_dictionary"]),
            "unit": "parameter_codes",
            "notes": "Standard parameter codes used for harmonization",
        },
    ]


def normalize_rows_for_compare(rows: List[Dict[str, object]]) -> List[Dict[str, str]]:
    return [{key: str(value) for key, value in row.items()} for row in rows]


def compare_figure_file(root: Path, relative_path: str, generated_rows: List[Dict[str, object]], report: ValidationReport) -> None:
    existing = read_csv_rows(root / relative_path)
    generated = normalize_rows_for_compare(generated_rows)
    report.add(
        f"figure source matches: {relative_path}",
        existing == generated,
        "Regenerated figure source data matches the deposited file.",
        observed=generated,
        expected=existing,
    )


def validate_figure_data(root: Path, report: ValidationReport) -> None:
    measurements_by_year = figure_measurements_by_year(root)
    measurements_by_medium = figure_measurements_by_medium(root)
    reports_by_year = figure_reports_by_year(root)
    reports_by_facility = figure_reports_by_facility_type(root)

    report.add(
        "figure measurements by year sum",
        sum(int(row["draft_measurement_count"]) for row in measurements_by_year) == 20514,
        "Corrected v3 measurement counts by year sum to the corrected v3 measurement table row count.",
        observed=sum(int(row["draft_measurement_count"]) for row in measurements_by_year),
        expected=20514,
    )
    report.add(
        "figure measurements by medium sum",
        sum(int(row["draft_measurement_count"]) for row in measurements_by_medium) == 20514,
        "Corrected v3 measurement counts by medium sum to the corrected v3 measurement table row count.",
        observed=sum(int(row["draft_measurement_count"]) for row in measurements_by_medium),
        expected=20514,
    )
    report.add(
        "figure reports by year sum",
        sum(int(row["count"]) for row in reports_by_year) == 8265,
        "Report inventory counts by year sum to the report inventory row count.",
        observed=sum(int(row["count"]) for row in reports_by_year),
        expected=8265,
    )
    report.add(
        "figure reports by facility type sum",
        sum(int(row["count"]) for row in reports_by_facility) == 8265,
        "Report inventory counts by facility type sum to the report inventory row count.",
        observed=sum(int(row["count"]) for row in reports_by_facility),
        expected=8265,
    )

    compare_figure_file(root, FIGURE_FILES["measurements_by_year"], measurements_by_year, report)
    compare_figure_file(root, FIGURE_FILES["measurements_by_medium"], measurements_by_medium, report)
    compare_figure_file(root, FIGURE_FILES["measurements_by_parameter"], figure_measurements_by_parameter(root), report)
    compare_figure_file(root, FIGURE_FILES["reports_by_year"], reports_by_year, report)
    compare_figure_file(root, FIGURE_FILES["reports_by_facility_type"], reports_by_facility, report)
    compare_figure_file(root, FIGURE_FILES["table_layer_scale"], figure_table_layer_scale(root), report)


def validate_schema_coverage(root: Path, report: ValidationReport) -> None:
    schema_path = root / KEY_FILES["dataset_schema"]
    schema_rows = read_csv_rows(schema_path)
    schema_file_names = {row["file_name"] for row in schema_rows if row.get("file_name")}
    package_file_names = {path.name for path in iter_release_files(root)}
    missing = sorted(schema_file_names - package_file_names)
    report.add(
        "dataset_schema file coverage",
        not missing,
        "Every file_name referenced by dataset_schema.csv is present in the package by file name.",
        observed=missing,
        expected=[],
    )


def validate_disclosure_scan(root: Path, report: ValidationReport) -> None:
    original_report_files = []
    sensitive_hits = []
    for path in iter_release_files(root):
        relative_path = rel_path(root, path)
        if path.suffix.lower() in ORIGINAL_REPORT_EXTENSIONS:
            original_report_files.append(relative_path)
        if path.suffix.lower() not in TEXT_EXTENSIONS_TO_SCAN:
            continue
        try:
            with path.open("r", encoding="utf-8-sig", errors="ignore") as f:
                for line_number, line in enumerate(f, start=1):
                    for label, pattern in SENSITIVE_DISCLOSURE_PATTERNS:
                        if pattern.search(line):
                            sensitive_hits.append(
                                {
                                    "file": relative_path,
                                    "line": line_number,
                                    "pattern": label,
                                }
                            )
                            break
        except UnicodeDecodeError:
            continue

    report.add(
        "no original report files",
        not original_report_files,
        "Public package contains no original DOC, DOCX or PDF report files.",
        observed=original_report_files,
        expected=[],
    )
    report.add(
        "no sensitive disclosure pattern hits",
        not sensitive_hits,
        "No private path, raw report text, private crosswalk or assistant trace patterns were found.",
        observed=sensitive_hits[:20],
        expected=[],
    )


def validate_release(root: Path, zip_info: Optional[Dict[str, object]] = None) -> ValidationReport:
    report = ValidationReport()
    validate_zip_info(zip_info, report)
    validate_manifest(root, report)
    validate_expected_counts(root, report)
    validate_cross_file_links(root, report)
    validate_human_qa(root, report)
    validate_correction_history(root, report)
    validate_figure_data(root, report)
    validate_schema_coverage(root, report)
    validate_disclosure_scan(root, report)
    return report


def manuscript_summary(root: Path, zip_info: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    counts = {}
    for name, relative_path in KEY_FILES.items():
        path = root / relative_path
        if path.exists() and path.suffix.lower() == ".csv":
            header, rows = csv_header_and_count(path)
            counts[name] = {"relative_path": relative_path, "rows": rows, "columns": len(header)}

    measurements_by_year = figure_measurements_by_year(root)
    measurements_by_medium = figure_measurements_by_medium(root)
    reports_by_year = figure_reports_by_year(root)
    reports_by_facility = figure_reports_by_facility_type(root)

    summary = {
        "dataset_doi": DATASET_DOI,
        "release_version": RELEASE_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "zip": zip_info,
        "key_table_counts": counts,
        "correction_history": {
            "removed_frequency_context_false_accepts": csv_header_and_count(root / KEY_FILES["frequency_removed"])[1],
            "ammonia_parameter_mapping_rows": csv_header_and_count(root / KEY_FILES["ammonia_audit"])[1],
            "original_draft_measurements": csv_header_and_count(root / KEY_FILES["measurements_original"])[1],
            "corrected_v3_draft_measurements": csv_header_and_count(root / KEY_FILES["measurements_corrected"])[1],
        },
        "figure_source_data": {
            "measurements_by_year": measurements_by_year,
            "measurements_by_medium": measurements_by_medium,
            "reports_by_year": reports_by_year,
            "reports_by_facility_type": reports_by_facility,
        },
    }
    return summary


def write_figure_outputs(root: Path, out_dir: Path) -> None:
    write_csv_rows(
        out_dir / "figure_data_draft_measurements_by_year_corrected_v3.csv",
        ["year", "draft_measurement_count"],
        figure_measurements_by_year(root),
    )
    write_csv_rows(
        out_dir / "figure_data_draft_measurements_by_medium_corrected_v3.csv",
        ["media", "draft_measurement_count"],
        figure_measurements_by_medium(root),
    )
    write_csv_rows(
        out_dir / "figure_data_draft_measurements_by_parameter_corrected_v3.csv",
        ["parameter_code", "draft_measurement_count"],
        figure_measurements_by_parameter(root),
    )
    write_csv_rows(out_dir / "figure_data_reports_by_year.csv", ["name", "count"], figure_reports_by_year(root))
    write_csv_rows(
        out_dir / "figure_data_reports_by_facility_type.csv",
        ["name", "count"],
        figure_reports_by_facility_type(root),
    )
    write_csv_rows(
        out_dir / "figure_data_table_derived_layer_scale_corrected_v3.csv",
        ["layer", "count", "unit", "notes"],
        figure_table_layer_scale(root),
    )


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_markdown_report(path: Path, report: ValidationReport) -> None:
    lines = [
        "# EnvCoRe-SW corrected v3 public release validation",
        "",
        f"Dataset DOI: {DATASET_DOI}",
        f"Release version: {RELEASE_VERSION}",
        f"Generated at UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Validation status: {'PASS' if report.passed else 'FAIL'}",
        "",
        "## Checks",
        "",
    ]
    for check in report.checks:
        lines.append(f"- {check['status']}: {check['name']} - {check['detail']}")
        if check["status"] != "PASS":
            lines.append(f"  - observed: {check.get('observed')}")
            lines.append(f"  - expected: {check.get('expected')}")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def command_validate(args: argparse.Namespace) -> int:
    tmp: Optional[tempfile.TemporaryDirectory] = None
    try:
        root, tmp, zip_info = prepare_release(Path(args.release))
        report = validate_release(root, zip_info)
        out_dir = Path(args.out)
        write_json(out_dir / "validation_report.json", report.to_dict())
        write_markdown_report(out_dir / "validation_report.md", report)
        print(f"Validation status: {'PASS' if report.passed else 'FAIL'}")
        print(f"Wrote {out_dir / 'validation_report.md'}")
        return 0 if report.passed else 1
    finally:
        if tmp is not None:
            tmp.cleanup()


def command_figures(args: argparse.Namespace) -> int:
    tmp: Optional[tempfile.TemporaryDirectory] = None
    try:
        root, tmp, _zip_info = prepare_release(Path(args.release))
        write_figure_outputs(root, Path(args.out))
        print(f"Wrote regenerated figure source data to {args.out}")
        return 0
    finally:
        if tmp is not None:
            tmp.cleanup()


def command_summary(args: argparse.Namespace) -> int:
    tmp: Optional[tempfile.TemporaryDirectory] = None
    try:
        root, tmp, zip_info = prepare_release(Path(args.release))
        write_json(Path(args.out), manuscript_summary(root, zip_info))
        print(f"Wrote {args.out}")
        return 0
    finally:
        if tmp is not None:
            tmp.cleanup()


def command_manifest(args: argparse.Namespace) -> int:
    tmp: Optional[tempfile.TemporaryDirectory] = None
    try:
        root, tmp, _zip_info = prepare_release(Path(args.release))
        rows = generate_technical_manifest(root)
        write_csv_rows(
            Path(args.out),
            [
                "file_name",
                "relative_path",
                "file_size_bytes",
                "row_count",
                "column_count",
                "columns",
                "sha256",
                "generated_at_utc",
            ],
            rows,
        )
        print(f"Wrote {args.out}")
        return 0
    finally:
        if tmp is not None:
            tmp.cleanup()


def command_all(args: argparse.Namespace) -> int:
    tmp: Optional[tempfile.TemporaryDirectory] = None
    try:
        root, tmp, zip_info = prepare_release(Path(args.release))
        out_dir = Path(args.out)
        if out_dir.exists() and args.clean:
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        write_figure_outputs(root, out_dir / "figure_source_data_rebuilt")
        write_json(out_dir / "manuscript_key_counts.json", manuscript_summary(root, zip_info))
        write_csv_rows(
            out_dir / "regenerated_manifest_technical.csv",
            [
                "file_name",
                "relative_path",
                "file_size_bytes",
                "row_count",
                "column_count",
                "columns",
                "sha256",
                "generated_at_utc",
            ],
            generate_technical_manifest(root),
        )
        report = validate_release(root, zip_info)
        write_json(out_dir / "validation_report.json", report.to_dict())
        write_markdown_report(out_dir / "validation_report.md", report)
        print(f"Validation status: {'PASS' if report.passed else 'FAIL'}")
        print(f"Wrote all outputs to {out_dir}")
        return 0 if report.passed else 1
    finally:
        if tmp is not None:
            tmp.cleanup()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EnvCoRe-SW corrected v3 public release tools")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_release_and_out(p: argparse.ArgumentParser, out_default: str) -> None:
        p.add_argument("--release", required=True, help="Path to the release ZIP or extracted release directory")
        p.add_argument("--out", required=True if out_default == "" else False, default=out_default, help="Output path")

    p_validate = sub.add_parser("validate", help="Validate the public release")
    add_release_and_out(p_validate, "outputs/validation_check")
    p_validate.set_defaults(func=command_validate)

    p_figures = sub.add_parser("figures", help="Regenerate figure source data from the public release")
    add_release_and_out(p_figures, "outputs/figure_source_data_rebuilt")
    p_figures.set_defaults(func=command_figures)

    p_summary = sub.add_parser("summary", help="Write manuscript key counts as JSON")
    add_release_and_out(p_summary, "outputs/manuscript_key_counts.json")
    p_summary.set_defaults(func=command_summary)

    p_manifest = sub.add_parser("manifest", help="Regenerate a technical manifest")
    add_release_and_out(p_manifest, "outputs/regenerated_manifest_technical.csv")
    p_manifest.set_defaults(func=command_manifest)

    p_all = sub.add_parser("all", help="Run validation and regenerate all public reproducibility outputs")
    add_release_and_out(p_all, "outputs/reproducibility_check")
    p_all.add_argument("--clean", action="store_true", help="Remove the output directory before writing outputs")
    p_all.set_defaults(func=command_all)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
