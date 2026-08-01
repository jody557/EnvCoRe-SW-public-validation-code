"""Validation checks for the EnvCoRe-SW public release candidate."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    message: str


class ValidationReport:
    """Accumulates deterministic PASS/FAIL results."""

    def __init__(self, root: Path, config: Mapping[str, Any]) -> None:
        self.root = root
        self.config = config
        self.checks: List[CheckResult] = []

    def add(self, name: str, condition: bool, pass_message: str, fail_message: str) -> None:
        self.checks.append(
            CheckResult(name, "PASS" if condition else "FAIL", pass_message if condition else fail_message)
        )

    @property
    def passed(self) -> bool:
        return all(item.status == "PASS" for item in self.checks)

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validator_version": self.config["software_version"],
            "validation_profile": self.config.get("validation_profile", "unspecified"),
            "target_release_line": self.config.get("target_release_line"),
            "release_root_name": self.root.name,
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "status": self.status,
            "pass_count": sum(item.status == "PASS" for item in self.checks),
            "fail_count": sum(item.status == "FAIL" for item in self.checks),
            "checks": [asdict(item) for item in self.checks],
        }

    def write(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "validation_report.json"
        md_path = output_dir / "validation_report.md"
        json_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        lines = [
            "# EnvCoRe-SW release validation report",
            "",
            f"Overall status: **{self.status}**",
            "",
            f"Validator version: `{self.config['software_version']}`",
            f"Validation profile: `{self.config.get('validation_profile', 'unspecified')}`",
            f"Target release line: `{self.config.get('target_release_line', '')}`",
            "",
            "| Check | Status | Result |",
            "|---|---:|---|",
        ]
        for item in self.checks:
            message = item.message.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{item.name}` | {item.status} | {message} |")
        lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")


class _Context:
    def __init__(self, root: Path, config: Mapping[str, Any], report: ValidationReport) -> None:
        self.root = root
        self.config = config
        self.report = report
        self._csv_cache: Dict[str, Tuple[List[str], List[Dict[str, str]]]] = {}
        self._sha_cache: Dict[str, str] = {}

    def csv(self, rel: str) -> Tuple[List[str], List[Dict[str, str]]]:
        if rel not in self._csv_cache:
            path = self.root / rel
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames is None:
                    raise ValueError(f"CSV has no header: {rel}")
                self._csv_cache[rel] = (list(reader.fieldnames), list(reader))
        return self._csv_cache[rel]

    def sha256(self, rel: str) -> str:
        if rel not in self._sha_cache:
            digest = hashlib.sha256()
            with (self.root / rel).open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            self._sha_cache[rel] = digest.hexdigest()
        return self._sha_cache[rel]


def validate_release(root: Path, config: Mapping[str, Any], allow_extra_files: bool = False) -> ValidationReport:
    report = ValidationReport(root, config)
    ctx = _Context(root, config, report)
    stages = [
        ("file_set", lambda: _check_file_set(ctx, allow_extra_files)),
        ("pinned_hashes", lambda: _check_pinned_hashes(ctx)),
        ("csv_shapes", lambda: _check_csv_shapes(ctx)),
    ]
    required = set(config["required_files"])
    if {"release_candidate_manifest.csv", "release_candidate_manifest.json"}.issubset(required):
        stages.append(("candidate_manifest", lambda: _check_candidate_manifest(ctx)))
    stages.extend(
        [
            ("checksum_files", lambda: _check_checksum_files(ctx)),
            ("public_file_manifest", lambda: _check_public_file_manifest(ctx)),
            ("identifiers_and_rows", lambda: _check_identifiers_and_rows(ctx)),
            ("data_dictionary", lambda: _check_data_dictionary(ctx)),
            ("controlled_vocabulary", lambda: _check_controlled_vocabulary(ctx)),
            ("pollutant_dictionary", lambda: _check_pollutant_dictionary(ctx)),
            ("metrics", lambda: _check_metrics(ctx)),
        ]
    )
    if "release_candidate_gates.json" in required:
        stages.append(("gates", lambda: _check_gates(ctx)))
    if "publication_metadata_status.json" in required:
        stages.append(("publication_metadata", lambda: _check_publication_metadata(ctx)))
    stages.append(("privacy", lambda: _check_privacy(ctx)))
    for stage_name, stage in stages:
        try:
            stage()
        except Exception as exc:  # keep a complete diagnostic report
            report.add(
                f"{stage_name}_execution",
                False,
                "",
                f"Check stage could not complete: {type(exc).__name__}: {exc}",
            )
    return report


def _check_file_set(ctx: _Context, allow_extra_files: bool) -> None:
    required = set(ctx.config["required_files"])
    actual: set[str] = set()
    symlinks: List[str] = []
    for path in ctx.root.rglob("*"):
        rel = path.relative_to(ctx.root).as_posix()
        if path.is_symlink():
            symlinks.append(rel)
        elif path.is_file():
            actual.add(rel)
    missing = sorted(required - actual)
    extra = sorted(actual - required)
    ctx.report.add("required_files_present", not missing, f"All {len(required)} required files are present.", f"Missing: {missing}")
    ctx.report.add("release_symlinks_absent", not symlinks, "No symlinks are present.", f"Symlinks found: {symlinks}")
    acceptable = not missing and (allow_extra_files or not extra)
    ctx.report.add(
        "release_file_set",
        acceptable,
        f"Release file set contains {len(actual)} files; extra-file policy satisfied.",
        f"Unexpected files: {extra}; missing files: {missing}",
    )
    expected = ctx.config["expected_counts"]["candidate_files"]
    count_ok = len(actual) == expected if not allow_extra_files else len(actual) >= expected
    ctx.report.add(
        "release_file_count",
        count_ok,
        f"Release file count is compatible with expected {expected}.",
        f"Found {len(actual)} files; expected {expected}.",
    )


def _check_pinned_hashes(ctx: _Context) -> None:
    mismatches = []
    for rel, expected in ctx.config["pinned_sha256"].items():
        if not (ctx.root / rel).is_file():
            mismatches.append(f"{rel}=missing")
            continue
        actual = ctx.sha256(rel)
        if actual != expected:
            mismatches.append(f"{rel} expected {expected}, got {actual}")
    ctx.report.add(
        "pinned_artifact_hashes",
        not mismatches,
        f"All {len(ctx.config['pinned_sha256'])} pinned artifact hashes match.",
        "; ".join(mismatches),
    )


def _check_csv_shapes(ctx: _Context) -> None:
    header_errors = []
    row_errors = []
    for rel, expected_header in ctx.config["csv_headers"].items():
        header, rows = ctx.csv(rel)
        if header != expected_header:
            header_errors.append(f"{rel}: {header!r}")
        expected_rows = ctx.config["csv_row_counts"].get(rel)
        if expected_rows is not None and len(rows) != expected_rows:
            row_errors.append(f"{rel}: expected {expected_rows}, got {len(rows)}")
    ctx.report.add(
        "csv_headers",
        not header_errors,
        f"All {len(ctx.config['csv_headers'])} configured CSV headers match exactly.",
        "; ".join(header_errors),
    )
    ctx.report.add(
        "csv_row_counts",
        not row_errors,
        f"All {len(ctx.config['csv_row_counts'])} configured CSV row counts match.",
        "; ".join(row_errors),
    )


def _check_candidate_manifest(ctx: _Context) -> None:
    _, rows = ctx.csv("release_candidate_manifest.csv")
    expected_payload = set(ctx.config["payload_files"])
    row_paths = [row["relative_path"] for row in rows]
    duplicates = sorted(path for path, count in Counter(row_paths).items() if count > 1)
    ctx.report.add("payload_manifest_unique_paths", not duplicates, "Payload manifest paths are unique.", f"Duplicates: {duplicates}")
    ctx.report.add(
        "payload_manifest_file_set",
        set(row_paths) == expected_payload,
        f"Payload manifest contains the expected {len(expected_payload)} files.",
        f"Missing: {sorted(expected_payload - set(row_paths))}; extra: {sorted(set(row_paths) - expected_payload)}",
    )

    row_errors = []
    for row in rows:
        rel = row["relative_path"]
        path = ctx.root / rel
        if rel not in expected_payload or not path.is_file():
            continue
        actual_rows, actual_cols = _file_shape(ctx, rel)
        expected_values = {
            "file_size_bytes": str(path.stat().st_size),
            "sha256": ctx.sha256(rel),
            "data_row_count": str(actual_rows),
            "column_count": "" if actual_cols is None else str(actual_cols),
            "public_safe_status": "PASS",
        }
        for field, expected in expected_values.items():
            if row.get(field, "") != expected:
                row_errors.append(f"{rel}:{field} expected {expected!r}, got {row.get(field)!r}")
    ctx.report.add("payload_manifest_values", not row_errors, "Every payload manifest value matches the file.", "; ".join(row_errors))

    data = json.loads((ctx.root / "release_candidate_manifest.json").read_text(encoding="utf-8"))
    json_rows = data.get("files", [])
    csv_canonical = sorted(_canonical_manifest_row(row) for row in rows)
    json_canonical = sorted(_canonical_manifest_row(row) for row in json_rows)
    ctx.report.add(
        "payload_manifest_csv_json_equivalence",
        csv_canonical == json_canonical,
        "CSV and JSON payload manifests are canonically equivalent.",
        "CSV and JSON manifest rows differ.",
    )
    formal = data.get("formal_counts", {})
    expected_formal = {
        "controlled_vocabulary_rows": ctx.config["expected_counts"]["controlled_vocabulary_rows"],
        "measurements": ctx.config["expected_counts"]["measurements"],
        "public_inventory": ctx.config["expected_counts"]["public_inventory"],
    }
    metadata_ok = (
        data.get("package_id") == ctx.config["target_package_id"]
        and data.get("payload_file_count") == ctx.config["expected_counts"]["payload_files"]
        and formal == expected_formal
    )
    ctx.report.add(
        "payload_manifest_metadata",
        metadata_ok,
        "Manifest package ID, payload count, and formal counts match configuration.",
        f"Observed package/count metadata: package_id={data.get('package_id')!r}, payload_file_count={data.get('payload_file_count')!r}, formal_counts={formal!r}",
    )


def _check_checksum_files(ctx: _Context) -> None:
    if "checksums.sha256" in set(ctx.config["required_files"]):
        root_sums = _parse_checksum_file(ctx.root / "checksums.sha256")
        expected_root = set(ctx.config["required_files"]) - {"checksums.sha256"}
        root_errors = _checksum_errors(ctx, root_sums, expected_root, prefix="")
        expected_count = ctx.config["expected_counts"]["root_checksum_entries"]
        root_ok = not root_errors and len(root_sums) == expected_count
        ctx.report.add(
            "root_checksums",
            root_ok,
            f"All {expected_count} root checksum entries match.",
            f"Count={len(root_sums)}; errors={root_errors}",
        )

    metadata_sums = _parse_checksum_file(ctx.root / "metadata/SHA256SUMS.txt")
    name_to_rel = {
        "measurements_long_curated_public.csv": "data/measurements_long_curated_public.csv",
        "report_inventory_public.csv": "data/report_inventory_public.csv",
        "controlled_vocabularies_public.csv": "metadata/controlled_vocabularies_public.csv",
        "data_dictionary_public.csv": "metadata/data_dictionary_public.csv",
        "known_issues_public.csv": "metadata/known_issues_public.csv",
        "pollutant_dictionary.csv": "metadata/pollutant_dictionary.csv",
        "public_file_manifest.csv": "metadata/public_file_manifest.csv",
    }
    metadata_errors = []
    if set(metadata_sums) != set(name_to_rel):
        metadata_errors.append(
            f"names differ; missing={sorted(set(name_to_rel) - set(metadata_sums))}, extra={sorted(set(metadata_sums) - set(name_to_rel))}"
        )
    for name, rel in name_to_rel.items():
        if name in metadata_sums and metadata_sums[name] != ctx.sha256(rel):
            metadata_errors.append(f"{name} hash mismatch")
    expected_metadata_count = ctx.config["expected_counts"]["metadata_checksum_entries"]
    metadata_ok = not metadata_errors and len(metadata_sums) == expected_metadata_count
    ctx.report.add(
        "metadata_checksums",
        metadata_ok,
        f"All {expected_metadata_count} metadata checksum entries match.",
        f"Count={len(metadata_sums)}; errors={metadata_errors}",
    )


def _check_public_file_manifest(ctx: _Context) -> None:
    _, rows = ctx.csv("metadata/public_file_manifest.csv")
    mapping = {
        "measurements_long_curated_public.csv": "data/measurements_long_curated_public.csv",
        "report_inventory_public.csv": "data/report_inventory_public.csv",
        "controlled_vocabularies_public.csv": "metadata/controlled_vocabularies_public.csv",
        "data_dictionary_public.csv": "metadata/data_dictionary_public.csv",
        "known_issues_public.csv": "metadata/known_issues_public.csv",
        "pollutant_dictionary.csv": "metadata/pollutant_dictionary.csv",
    }
    names = [row["file_name"] for row in rows]
    errors = []
    if len(names) != len(set(names)):
        errors.append("duplicate file_name")
    if set(names) != set(mapping):
        errors.append(f"file set differs: {sorted(names)}")
    for row in rows:
        rel = mapping.get(row["file_name"])
        if not rel:
            continue
        path = ctx.root / rel
        data_rows, columns = _file_shape(ctx, rel)
        expected = {
            "byte_size": str(path.stat().st_size),
            "sha256": ctx.sha256(rel),
            "data_row_count": str(data_rows),
            "column_count": str(columns),
        }
        for field, value in expected.items():
            if row.get(field) != value:
                errors.append(f"{row['file_name']}:{field} expected {value}, got {row.get(field)!r}")
        if not row.get("release_status"):
            errors.append(f"{row['file_name']}: blank release_status")
    ctx.report.add("public_file_manifest", not errors, "The six-row public file manifest matches all files.", "; ".join(errors))


def _check_identifiers_and_rows(ctx: _Context) -> None:
    _, measurements = ctx.csv("data/measurements_long_curated_public.csv")
    _, inventory = ctx.csv("data/report_inventory_public.csv")
    measurement_ids = [row["measurement_id"] for row in measurements]
    report_ids = [row["report_id"] for row in inventory]
    m_duplicates = sorted(value for value, count in Counter(measurement_ids).items() if not value or count > 1)
    r_duplicates = sorted(value for value, count in Counter(report_ids).items() if not value or count > 1)
    ctx.report.add("measurement_id_uniqueness", not m_duplicates, f"All {len(measurement_ids)} measurement IDs are nonblank and unique.", f"Invalid IDs: {m_duplicates[:20]}")
    ctx.report.add("report_id_uniqueness", not r_duplicates, f"All {len(report_ids)} report IDs are nonblank and unique.", f"Invalid IDs: {r_duplicates[:20]}")
    report_set = set(report_ids)
    missing_links = sorted({row["report_id"] for row in measurements if row["report_id"] not in report_set})
    ctx.report.add("measurement_inventory_join", not missing_links, "Every measurement report_id joins to the public inventory.", f"Missing report IDs: {missing_links[:20]}")

    row_errors = []
    for index, row in enumerate(measurements, start=2):
        try:
            Decimal(row["value"])
        except (InvalidOperation, ValueError):
            row_errors.append(f"row {index}: nonnumeric value {row['value']!r}")
        try:
            year = int(row["year"])
            if not 2018 <= year <= 2025:
                row_errors.append(f"row {index}: year {year}")
        except ValueError:
            row_errors.append(f"row {index}: invalid year {row['year']!r}")
        if row["sample_date"]:
            try:
                datetime.strptime(row["sample_date"], "%Y-%m-%d")
            except ValueError:
                row_errors.append(f"row {index}: invalid sample_date {row['sample_date']!r}")
        if len(row_errors) >= 50:
            break
    ctx.report.add("measurement_scalar_formats", not row_errors, "Measurement values, years, and populated dates have valid scalar formats.", "; ".join(row_errors))


def _check_data_dictionary(ctx: _Context) -> None:
    _, dictionary = ctx.csv("metadata/data_dictionary_public.csv")
    source_map = {
        "measurements_long_curated_public.csv": "data/measurements_long_curated_public.csv",
        "report_inventory_public.csv": "data/report_inventory_public.csv",
        "known_issues_public.csv": "metadata/known_issues_public.csv",
    }
    keys = [(row["file_name"], row["field_name"]) for row in dictionary]
    errors = []
    if len(keys) != len(set(keys)):
        errors.append("duplicate file_name/field_name rows")
    if any(row["stage6_schema_status"] != "ACTIVE" for row in dictionary):
        errors.append("non-ACTIVE schema status")
    for file_name, rel in source_map.items():
        header, _ = ctx.csv(rel)
        fields = [row["field_name"] for row in dictionary if row["file_name"] == file_name]
        if fields != header:
            errors.append(f"{file_name} dictionary order/coverage differs from CSV header")
    unknown_files = sorted(set(row["file_name"] for row in dictionary) - set(source_map))
    if unknown_files:
        errors.append(f"unknown dictionary files: {unknown_files}")
    ctx.report.add("data_dictionary_coverage", not errors, "The 52-row active data dictionary exactly covers the three public tables.", "; ".join(errors))


def _check_controlled_vocabulary(ctx: _Context) -> None:
    _, vocabulary = ctx.csv("metadata/controlled_vocabularies_public.csv")
    source_map = {
        "measurements_long_curated_public.csv": "data/measurements_long_curated_public.csv",
        "report_inventory_public.csv": "data/report_inventory_public.csv",
    }
    source_rows = {name: ctx.csv(rel)[1] for name, rel in source_map.items()}
    errors = []
    keys = [(row["file_name"], row["field_name"], row["value"]) for row in vocabulary]
    if len(keys) != len(set(keys)):
        errors.append("duplicate file/field/value entries")
    for row in vocabulary:
        source = source_rows.get(row["file_name"])
        if source is None:
            errors.append(f"unknown source file {row['file_name']!r}")
            continue
        if row["field_name"] not in source[0]:
            errors.append(f"unknown field {row['file_name']}:{row['field_name']}")
            continue
        actual = sum(item[row["field_name"]] == row["value"] for item in source)
        try:
            expected = int(row["observed_count"])
        except ValueError:
            errors.append(f"nonnumeric observed_count for {row!r}")
            continue
        if actual != expected:
            errors.append(f"{row['file_name']}:{row['field_name']}={row['value']!r}: expected {expected}, got {actual}")
        if not row["definition"]:
            errors.append(f"blank definition for {row!r}")
    ctx.report.add("controlled_vocabulary_recount", not errors, "All 122 controlled-vocabulary counts were independently reproduced.", "; ".join(errors[:50]))


def _check_pollutant_dictionary(ctx: _Context) -> None:
    _, measurements = ctx.csv("data/measurements_long_curated_public.csv")
    _, dictionary_rows = ctx.csv("metadata/pollutant_dictionary.csv")
    codes = [row["parameter_code"] for row in dictionary_rows]
    duplicates = sorted(code for code, count in Counter(codes).items() if not code or count > 1)
    dictionary = {row["parameter_code"]: row for row in dictionary_rows}
    structural_errors = []
    unit_mismatches: Counter[Tuple[str, str]] = Counter()
    for row in measurements:
        entry = dictionary.get(row["parameter_code"])
        if entry is None:
            structural_errors.append(f"missing code {row['parameter_code']!r}")
            continue
        media = set(_split_semicolon(entry["media"]))
        groups = set(_split_semicolon(entry["parameter_group"]))
        units = set(_split_semicolon(entry["expected_unit_patterns"]))
        if row["media"] not in media:
            structural_errors.append(f"{row['parameter_code']}: unsupported media {row['media']!r}")
        if row["parameter_group"] not in groups:
            structural_errors.append(f"{row['parameter_code']}: unsupported group {row['parameter_group']!r}")
        if row["unit"] and row["unit"] not in units:
            unit_mismatches[(row["parameter_code"], row["unit"])] += 1

    expected_exceptions = Counter(
        {(item["parameter_code"], item["unit"]): int(item["count"]) for item in ctx.config.get("declared_unit_exceptions", [])}
    )
    exception_notes_ok = True
    for (code, unit), count in expected_exceptions.items():
        note = dictionary.get(code, {}).get("context_notes", "")
        if unit not in note or str(count) not in note.lower().replace("five", "5"):
            exception_notes_ok = False
    ctx.report.add("pollutant_dictionary_codes", not duplicates, "Pollutant dictionary codes are nonblank and unique.", f"Invalid codes: {duplicates}")
    ctx.report.add("pollutant_dictionary_row_compatibility", not structural_errors, "Every measurement parameter, medium, and group is dictionary-supported.", "; ".join(structural_errors[:50]))
    ctx.report.add(
        "pollutant_dictionary_unit_exceptions",
        unit_mismatches == expected_exceptions and exception_notes_ok,
        "All unit mismatches equal the five explicitly disclosed color/mg/L source-unit exceptions.",
        f"Observed={dict(unit_mismatches)!r}; expected={dict(expected_exceptions)!r}; notes_ok={exception_notes_ok}",
    )
    water_temperature = [row for row in measurements if row["parameter_code"] == "water_temperature"]
    expected_water_temperature = int(ctx.config.get("special_counts", {}).get("water_temperature_celsius", 13))
    special_ok = len(water_temperature) == expected_water_temperature and all(row["unit"] == "°C" for row in water_temperature)
    dictionary_ok = "°C" in set(_split_semicolon(dictionary.get("water_temperature", {}).get("expected_unit_patterns", "")))
    ctx.report.add(
        "water_temperature_celsius",
        special_ok and dictionary_ok,
        f"All {expected_water_temperature} water_temperature records use °C and the dictionary explicitly supports °C.",
        f"water_temperature rows={len(water_temperature)}, all_celsius={special_ok}, dictionary_support={dictionary_ok}",
    )


def _check_metrics(ctx: _Context) -> None:
    errors = []
    metric_files = [
        ("validation/final300_metrics_public.csv", "weighted_estimate"),
        ("validation/probability50_metrics_public.csv", "weighted_estimate"),
        ("validation/schema_scope_metrics_public.csv", "estimate"),
    ]
    for rel, estimate_field in metric_files:
        _, rows = ctx.csv(rel)
        names = [row["metric"] for row in rows]
        if len(names) != len(set(names)) or any(not name for name in names):
            errors.append(f"{rel}: duplicate/blank metrics")
        for row in rows:
            estimate_text = row.get(estimate_field, "")
            if estimate_text:
                try:
                    estimate = Decimal(estimate_text)
                except InvalidOperation:
                    errors.append(f"{rel}:{row['metric']}: invalid estimate")
                    continue
                if row.get("unit") == "proportion" or rel != "validation/schema_scope_metrics_public.csv":
                    if not Decimal("0") <= estimate <= Decimal("1"):
                        errors.append(f"{rel}:{row['metric']}: estimate outside [0,1]")
            lower = row.get("bootstrap_ci95_lower", "")
            upper = row.get("bootstrap_ci95_upper", "")
            if lower or upper:
                try:
                    low_value, high_value = Decimal(lower), Decimal(upper)
                    if low_value > high_value:
                        errors.append(f"{rel}:{row['metric']}: CI lower > upper")
                except InvalidOperation:
                    errors.append(f"{rel}:{row['metric']}: invalid CI")
            replicas = row.get("bootstrap_replicates", "")
            if replicas and int(replicas) < 5000:
                errors.append(f"{rel}:{row['metric']}: bootstrap_replicates={replicas}")

    _, final300 = ctx.csv("validation/final300_metrics_public.csv")
    if any(row["original_sample_count"] != "300" for row in final300):
        errors.append("Final300 original_sample_count is not consistently 300")
    _, probability50 = ctx.csv("validation/probability50_metrics_public.csv")
    if any(row["probability_report_count"] != "50" for row in probability50):
        errors.append("Probability50 probability_report_count is not consistently 50")
    ctx.report.add("aggregate_validation_metrics", not errors, "Aggregate metric tables have unique metrics, valid ranges, declared samples, and at least 5,000 bootstrap replicates where applicable.", "; ".join(errors))


def _check_gates(ctx: _Context) -> None:
    gates = json.loads((ctx.root / "release_candidate_gates.json").read_text(encoding="utf-8"))
    errors = []
    for name in ctx.config.get("required_yes_gates", []):
        if gates.get(name) != "YES":
            errors.append(f"{name}={gates.get(name)!r}, expected YES")
    for name in ctx.config.get("required_no_gates", []):
        if gates.get(name) != "NO":
            errors.append(f"{name}={gates.get(name)!r}, expected NO")
    ctx.report.add("release_candidate_gates", not errors, "All configured technical and publication-boundary gates have the expected values.", "; ".join(errors))


def _check_publication_metadata(ctx: _Context) -> None:
    status = json.loads((ctx.root / "publication_metadata_status.json").read_text(encoding="utf-8"))
    errors = []
    if status.get("publication_metadata_complete") is not False:
        errors.append("publication_metadata_complete is not false")
    if status.get("publication_gate") != "NO":
        errors.append("publication_gate is not NO")
    fields = status.get("fields")
    if not isinstance(fields, dict) or not fields:
        errors.append("fields mapping is missing")
    else:
        for name, item in fields.items():
            if not isinstance(item, dict):
                errors.append(f"{name}: malformed field status")
                continue
            if item.get("value") not in (None, ""):
                errors.append(f"{name}: value populated while publication metadata is incomplete")
            if not str(item.get("status", "")).startswith("PENDING"):
                errors.append(f"{name}: status is not pending")
    ctx.report.add("publication_metadata_boundary", not errors, "Publication metadata is consistently recorded as incomplete without invented final values.", "; ".join(errors))


def _check_privacy(ctx: _Context) -> None:
    patterns = [re.compile(value) for value in ctx.config.get("privacy_patterns", [])]
    findings = []
    for rel in ctx.config["required_files"]:
        path = ctx.root / rel
        try:
            with path.open("r", encoding="utf-8-sig", errors="strict") as handle:
                for line_number, line in enumerate(handle, start=1):
                    for pattern in patterns:
                        if pattern.search(line):
                            findings.append(f"{rel}:{line_number}:{pattern.pattern}")
                            if len(findings) >= 50:
                                break
                    if len(findings) >= 50:
                        break
        except UnicodeError:
            findings.append(f"{rel}: not valid UTF-8 text")
        if len(findings) >= 50:
            break
    ctx.report.add("public_privacy_sentinels", not findings, "No configured local-path, private-workflow, or reviewer-identity sentinel was found.", "; ".join(findings))


def _canonical_manifest_row(row: Mapping[str, Any]) -> Tuple[str, ...]:
    fields = [
        "relative_path",
        "file_size_bytes",
        "sha256",
        "data_row_count",
        "column_count",
        "role",
        "public_safe_status",
    ]
    return tuple("" if row.get(field) is None else str(row.get(field, "")) for field in fields)


def _file_shape(ctx: _Context, rel: str) -> Tuple[int, Optional[int]]:
    if rel.lower().endswith(".csv"):
        header, rows = ctx.csv(rel)
        return len(rows), len(header)
    return 1, None


def _parse_checksum_file(path: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    pattern = re.compile(r"^([0-9a-f]{64})  (.+)$")
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not raw:
            continue
        match = pattern.fullmatch(raw)
        if not match:
            raise ValueError(f"Malformed checksum line {path.name}:{line_number}")
        digest, name = match.groups()
        normalized = name.replace("\\", "/")
        if normalized.startswith("/") or ".." in Path(normalized).parts or normalized in result:
            raise ValueError(f"Unsafe or duplicate checksum path {name!r}")
        result[normalized] = digest
    return result


def _checksum_errors(ctx: _Context, sums: Mapping[str, str], expected: set[str], prefix: str) -> List[str]:
    errors = []
    if set(sums) != expected:
        errors.append(f"missing={sorted(expected - set(sums))}, extra={sorted(set(sums) - expected)}")
    for name, expected_hash in sums.items():
        rel = f"{prefix}{name}" if prefix else name
        path = ctx.root / rel
        if path.is_file() and ctx.sha256(rel) != expected_hash:
            errors.append(f"{name}: hash mismatch")
    return errors


def _split_semicolon(value: str) -> List[str]:
    return [item.strip() for item in value.split(";") if item.strip()]
