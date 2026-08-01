"""Synthetic release fixture for release-independent validator tests."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from envcore_validation import load_config


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = REPOSITORY_ROOT / "config" / "release_candidate_config.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def write_csv(path: Path, header: List[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def row_for(header: List[str], **values: str) -> Dict[str, str]:
    row = {field: "" for field in header}
    row.update(values)
    return row


def build_synthetic_release(root: Path, duplicate_measurement_id: bool = False) -> Dict[str, Any]:
    config = copy.deepcopy(load_config(BASE_CONFIG))
    counts = config["expected_counts"]
    counts.update(
        {
            "measurements": 2 if duplicate_measurement_id else 1,
            "public_inventory": 1,
            "controlled_vocabulary_rows": 1,
            "data_dictionary_rows": 52,
            "pollutant_dictionary_rows": 1,
            "known_issue_rows": 1,
            "final300_metric_rows": 1,
            "probability50_metric_rows": 1,
            "schema_scope_metric_rows": 1,
        }
    )
    config["pinned_sha256"] = {}
    config["declared_unit_exceptions"] = []
    config["special_counts"] = {"water_temperature_celsius": 2 if duplicate_measurement_id else 1}
    config["required_yes_gates"] = ["TECHNICAL_PASS"]
    config["required_no_gates"] = ["READY_TO_PUBLISH"]
    config["privacy_patterns"] = [r"(?i)PRIVATE_DO_NOT_RELEASE"]

    headers = config["csv_headers"]
    measurement = row_for(
        headers["data/measurements_long_curated_public.csv"],
        measurement_id="M001",
        measurement_row_candidate_id="MR001",
        report_id="R001",
        facility_id="F001",
        year="2024",
        media="water",
        facility_type="industrial",
        monitoring_type="self_monitoring",
        parameter_code="water_temperature",
        parameter_group="water",
        value="20.5",
        unit="°C",
        sample_date="2024-01-02",
        sample_date_valid="true",
        table_id="T001",
        row_index="1",
        row_text_hash="0" * 64,
        extraction_method="rule_based",
        extraction_confidence="high",
        rule_id="R_TEST",
        qa_status="validated",
        replicate_policy="retain_all",
    )
    measurement_rows = [measurement]
    if duplicate_measurement_id:
        duplicate = dict(measurement)
        duplicate["measurement_row_candidate_id"] = "MR002"
        measurement_rows.append(duplicate)
    write_csv(root / "data/measurements_long_curated_public.csv", list(measurement), measurement_rows)

    inventory = row_for(
        headers["data/report_inventory_public.csv"],
        report_id="R001",
        year="2024",
        extension=".docx",
        file_size_bytes="100",
        report_code_redacted="RC001",
        report_series="series",
        monitoring_period_label="January",
        media_tags="water",
        facility_type="industrial",
        monitoring_type="self_monitoring",
        has_docx_pair="false",
        has_pdf_pair="false",
        title_redacted="Report",
        relative_path_hash="1" * 64,
    )
    write_csv(root / "data/report_inventory_public.csv", list(inventory), [inventory])

    known = row_for(
        headers["metadata/known_issues_public.csv"],
        known_issue_id="K001",
        scope="measurement",
        issue_type="test_disclosure",
        affected_record_count="1",
        public_description="Synthetic disclosed issue.",
        recommended_use="Use cautiously.",
        status="PRESERVED",
    )
    write_csv(root / "metadata/known_issues_public.csv", list(known), [known])

    dictionary_rows = []
    for file_name, rel in (
        ("measurements_long_curated_public.csv", "data/measurements_long_curated_public.csv"),
        ("report_inventory_public.csv", "data/report_inventory_public.csv"),
        ("known_issues_public.csv", "metadata/known_issues_public.csv"),
    ):
        for field in headers[rel]:
            dictionary_rows.append(
                {
                    "file_name": file_name,
                    "field_name": field,
                    "data_type": "string",
                    "description": f"Synthetic definition for {field}.",
                    "missing_value_meaning": "Not available.",
                    "key_role": "attribute",
                    "stage6_schema_status": "ACTIVE",
                }
            )
    write_csv(root / "metadata/data_dictionary_public.csv", headers["metadata/data_dictionary_public.csv"], dictionary_rows)

    pollutant = {
        "parameter_code": "water_temperature",
        "chinese_label": "水温",
        "english_label": "Water temperature",
        "parameter_group": "water",
        "media": "water",
        "aliases": "水温",
        "expected_unit_patterns": "°C",
        "context_notes": "Synthetic fixture.",
    }
    write_csv(root / "metadata/pollutant_dictionary.csv", headers["metadata/pollutant_dictionary.csv"], [pollutant])

    vocabulary = {
        "file_name": "measurements_long_curated_public.csv",
        "field_name": "parameter_code",
        "value": "water_temperature",
        "observed_count": str(len(measurement_rows)),
        "definition": "Synthetic controlled value.",
    }
    write_csv(root / "metadata/controlled_vocabularies_public.csv", headers["metadata/controlled_vocabularies_public.csv"], [vocabulary])

    final300 = row_for(
        headers["validation/final300_metrics_public.csv"],
        metric="parameter_accuracy",
        evidence_layer="SYNTHETIC",
        original_sample_count="300",
        assessable_count="300",
        not_assessable_count="0",
        assessable_correct_count="300",
        assessable_incorrect_count="0",
        weighted_estimate="1.0",
        bootstrap_ci95_lower="1.0",
        bootstrap_ci95_upper="1.0",
        bootstrap_replicates="5000",
        review_limitation="Synthetic fixture.",
    )
    write_csv(root / "validation/final300_metrics_public.csv", list(final300), [final300])
    probability50 = row_for(
        headers["validation/probability50_metrics_public.csv"],
        metric="measurement_recall",
        evidence_layer="SYNTHETIC",
        probability_report_count="50",
        assessable_report_count="50",
        not_assessable_report_count="0",
        weighted_estimate="1.0",
        bootstrap_ci95_lower="1.0",
        bootstrap_ci95_upper="1.0",
        bootstrap_replicates="5000",
        estimation_note="Synthetic fixture.",
        review_limitation="Synthetic fixture.",
    )
    write_csv(root / "validation/probability50_metrics_public.csv", list(probability50), [probability50])
    schema = row_for(
        headers["validation/schema_scope_metrics_public.csv"],
        metric="weighted_result_scope_coverage",
        metric_type="WEIGHTED_OR_UNWEIGHTED_SCOPE_ESTIMATE",
        estimate="0.8",
        bootstrap_ci95_lower="0.7",
        bootstrap_ci95_upper="0.9",
        bootstrap_replicates="5000",
        unit="proportion",
        interpretation="Synthetic fixture.",
    )
    write_csv(root / "validation/schema_scope_metrics_public.csv", list(schema), [schema])

    for rel in config["payload_files"]:
        path = root / rel
        if path.exists() or rel.endswith(".csv"):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n\nSynthetic public documentation.\n", encoding="utf-8")

    public_files = {
        "measurements_long_curated_public.csv": "data/measurements_long_curated_public.csv",
        "report_inventory_public.csv": "data/report_inventory_public.csv",
        "controlled_vocabularies_public.csv": "metadata/controlled_vocabularies_public.csv",
        "data_dictionary_public.csv": "metadata/data_dictionary_public.csv",
        "known_issues_public.csv": "metadata/known_issues_public.csv",
        "pollutant_dictionary.csv": "metadata/pollutant_dictionary.csv",
    }
    public_manifest_rows = []
    for name, rel in public_files.items():
        path = root / rel
        header, rows = _read_csv(path)
        public_manifest_rows.append(
            {
                "file_name": name,
                "byte_size": str(path.stat().st_size),
                "sha256": sha256(path),
                "data_row_count": str(len(rows)),
                "column_count": str(len(header)),
                "release_status": "SYNTHETIC_CANDIDATE",
            }
        )
    write_csv(root / "metadata/public_file_manifest.csv", headers["metadata/public_file_manifest.csv"], public_manifest_rows)

    metadata_names = dict(public_files)
    metadata_names["public_file_manifest.csv"] = "metadata/public_file_manifest.csv"
    metadata_lines = [f"{sha256(root / rel)}  {name}" for name, rel in sorted(metadata_names.items())]
    (root / "metadata/SHA256SUMS.txt").write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")

    manifest_rows = []
    for rel in config["payload_files"]:
        path = root / rel
        if rel.endswith(".csv"):
            header, rows = _read_csv(path)
            row_count, column_count = len(rows), len(header)
        else:
            row_count, column_count = 1, ""
        manifest_rows.append(
            {
                "relative_path": rel,
                "file_size_bytes": str(path.stat().st_size),
                "sha256": sha256(path),
                "data_row_count": str(row_count),
                "column_count": str(column_count),
                "role": "PUBLIC_PAYLOAD",
                "public_safe_status": "PASS",
            }
        )
    write_csv(root / "release_candidate_manifest.csv", headers["release_candidate_manifest.csv"], manifest_rows)
    manifest_json_rows = []
    for row in manifest_rows:
        converted = dict(row)
        converted["file_size_bytes"] = int(converted["file_size_bytes"])
        converted["data_row_count"] = int(converted["data_row_count"])
        converted["column_count"] = int(converted["column_count"]) if converted["column_count"] else ""
        manifest_json_rows.append(converted)
    manifest_json = {
        "files": manifest_json_rows,
        "formal_counts": {
            "controlled_vocabulary_rows": 1,
            "measurements": len(measurement_rows),
            "public_inventory": 1,
        },
        "package_id": config["target_package_id"],
        "payload_file_count": 19,
        "publication_metadata_complete": False,
    }
    (root / "release_candidate_manifest.json").write_text(json.dumps(manifest_json, indent=2) + "\n", encoding="utf-8")
    (root / "release_candidate_gates.json").write_text(
        json.dumps({"TECHNICAL_PASS": "YES", "READY_TO_PUBLISH": "NO"}, indent=2) + "\n", encoding="utf-8"
    )
    publication = {
        "publication_metadata_complete": False,
        "publication_gate": "NO",
        "fields": {"doi": {"status": "PENDING_CONFIRMATION", "value": None}},
    }
    (root / "publication_metadata_status.json").write_text(json.dumps(publication, indent=2) + "\n", encoding="utf-8")

    config["csv_row_counts"].update(
        {
            "data/measurements_long_curated_public.csv": len(measurement_rows),
            "data/report_inventory_public.csv": 1,
            "metadata/controlled_vocabularies_public.csv": 1,
            "metadata/data_dictionary_public.csv": 52,
            "metadata/known_issues_public.csv": 1,
            "metadata/pollutant_dictionary.csv": 1,
            "metadata/public_file_manifest.csv": 6,
            "release_candidate_manifest.csv": 19,
            "validation/final300_metrics_public.csv": 1,
            "validation/probability50_metrics_public.csv": 1,
            "validation/schema_scope_metrics_public.csv": 1,
        }
    )

    root_lines = []
    for rel in sorted(set(config["required_files"]) - {"checksums.sha256"}):
        root_lines.append(f"{sha256(root / rel)}  {rel}")
    (root / "checksums.sha256").write_text("\n".join(root_lines) + "\n", encoding="utf-8")
    return config


def build_synthetic_public_release(root: Path) -> Dict[str, Any]:
    """Build the 19-file public profile from a complete synthetic candidate."""

    build_synthetic_release(root)
    for rel in (
        "checksums.sha256",
        "publication_metadata_status.json",
        "release_candidate_gates.json",
        "release_candidate_manifest.csv",
        "release_candidate_manifest.json",
    ):
        (root / rel).unlink()
    config = copy.deepcopy(load_config(REPOSITORY_ROOT / "config" / "release_config.json"))
    config["pinned_sha256"] = {}
    config["special_counts"] = {"water_temperature_celsius": 1}
    config["declared_unit_exceptions"] = []
    config["privacy_patterns"] = [r"(?i)PRIVATE_DO_NOT_RELEASE"]
    config["csv_row_counts"].update(
        {
            "data/measurements_long_curated_public.csv": 1,
            "data/report_inventory_public.csv": 1,
            "metadata/controlled_vocabularies_public.csv": 1,
            "metadata/data_dictionary_public.csv": 52,
            "metadata/known_issues_public.csv": 1,
            "metadata/pollutant_dictionary.csv": 1,
            "metadata/public_file_manifest.csv": 6,
            "validation/final300_metrics_public.csv": 1,
            "validation/probability50_metrics_public.csv": 1,
            "validation/schema_scope_metrics_public.csv": 1,
        }
    )
    config["expected_counts"].update(
        {
            "measurements": 1,
            "public_inventory": 1,
            "controlled_vocabulary_rows": 1,
            "data_dictionary_rows": 52,
            "pollutant_dictionary_rows": 1,
            "known_issue_rows": 1,
            "final300_metric_rows": 1,
            "probability50_metric_rows": 1,
            "schema_scope_metric_rows": 1,
        }
    )
    return config


def refresh_root_controls(root: Path, config: Mapping[str, Any]) -> None:
    """Refresh manifests and sums after a test mutation when needed."""

    raise NotImplementedError("Tests intentionally leave mutations detectable; no refresh helper is provided.")


def _read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)
