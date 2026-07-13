#!/usr/bin/env python3
"""Validate and summarize a completed EnvCoRe-SW dual-human-review CSV.

The summary keeps four stages separate: frozen R1/R2 assessments, HUM_ADJ01
human adjudication, later deterministic post-review audit, and final release
action. Incomplete or internally inconsistent files produce no output.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

import envcore_sw_public_release_tools as release_tools


def cohen_kappa(values1: Iterable[str], values2: Iterable[str]) -> Tuple[Optional[float], str]:
    left = list(values1)
    right = list(values2)
    if len(left) != len(right):
        raise ValueError("Cohen's kappa requires reviewer vectors of equal length.")
    if not left:
        raise ValueError("Cannot calculate Cohen's kappa for an empty sample.")
    pairs = list(zip(left, right))
    observed = sum(left == right for left, right in pairs) / len(pairs)
    left_counts = Counter(left for left, _right in pairs)
    right_counts = Counter(right for _left, right in pairs)
    categories = set(left_counts) | set(right_counts)
    expected = sum(
        (left_counts[item] / len(pairs)) * (right_counts[item] / len(pairs))
        for item in categories
    )
    if expected == 1.0:
        return None, "not_estimable_no_category_variation"
    return (observed - expected) / (1.0 - expected), "estimated"


def validate_complete(rows: Sequence[Mapping[str, str]], id_field: str) -> None:
    if not rows:
        raise ValueError("The dual-review file contains no records.")
    report = release_tools.ValidationReport(
        {
            "dataset_title": "EnvCoRe-SW QA",
            "dataset_version": "v5",
            "dataset_correction_state": "v5.5",
            "data_doi": "",
        }
    )
    release_tools._validate_qa_table(rows, "QA", id_field, report)
    failures = [check for check in report.checks if check["status"] == "FAIL"]
    if failures:
        examples = "; ".join(f"{item['name']}: {item.get('observed')}" for item in failures[:5])
        raise ValueError(f"Dual-review results are incomplete or inconsistent; no statistics were generated. {examples}")


def summarize(rows: Sequence[Mapping[str, str]], id_field: str) -> Dict[str, object]:
    field_agreement: Dict[str, object] = {}
    for field in release_tools.QA_AGREEMENT_FIELDS:
        left = [row[f"r1_{field}"] for row in rows]
        right = [row[f"r2_{field}"] for row in rows]
        agreements = sum(a == b for a, b in zip(left, right))
        kappa, kappa_status = cohen_kappa(left, right)
        field_agreement[field] = {
            "agreements": agreements,
            "disagreements": len(rows) - agreements,
            "agreement_rate": agreements / len(rows),
            "cohen_kappa": kappa,
            "kappa_status": kappa_status,
        }
    metrics = release_tools.qa_metrics(rows)
    return {
        "status": "completed_stage_separated_dual_review_summary",
        "sample_id_field": id_field,
        "pre_adjudication_human_review": {
            "records": len(rows),
            "reviewers": ["HUM_R01", "HUM_R02"],
            "review_status": "independent_blinded",
            "reviewer_agreement": metrics["reviewer_agreement"],
            "field_agreement": field_agreement,
        },
        "human_adjudication": {
            "adjudicator": "HUM_ADJ01",
            "required": metrics["human_adjudication_required"],
            "not_required": len(rows) - int(metrics["human_adjudication_required"]),
            "confirmed_false_accepts": metrics["human_confirmed_false_accepts"],
            "accepted_with_correction": metrics["human_adjudicated_corrections"],
        },
        "post_review_deterministic_rule_audit": {
            "additional_rule_exclusions": metrics["post_review_rule_exclusions"],
            "note": "These outcomes are not human-adjudication decisions.",
        },
        "final_release_action": {
            "total_exclusions": metrics["final_total_exclusions"],
            "final_qa_decisions": metrics["final_qa_decisions"],
            "final_correction_actions": metrics["final_correction_actions"],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize completed EnvCoRe-SW v5 dual-human-review QA")
    parser.add_argument("input_csv", type=Path, help="Completed stratified or challenge QA CSV")
    parser.add_argument("--out", type=Path, required=True, help="New summary JSON path")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows = release_tools.read_csv_rows(args.input_csv)
        if not rows:
            raise ValueError("The dual-review file contains no records.")
        if "qa_sample_id" in rows[0]:
            id_field = "qa_sample_id"
        elif "challenge_sample_id" in rows[0]:
            id_field = "challenge_sample_id"
        else:
            raise ValueError("Missing qa_sample_id/challenge_sample_id column.")
        validate_complete(rows, id_field)
        payload = summarize(rows, id_field)
        if args.out.exists():
            raise FileExistsError(f"Output already exists: {args.out}")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
