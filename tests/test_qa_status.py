from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.common import REPO_ROOT, ReleaseTestCase, release_tools


class TestQAStatus(ReleaseTestCase):
    def test_completed_dual_review_and_challenge(self) -> None:
        report = release_tools.ValidationReport(self.config)
        release_tools.validate_qa(self.release, report, self.config)
        self.assertTrue(report.passed, [item for item in report.checks if item["status"] == "FAIL"])

    def test_stage_separated_summary_script(self) -> None:
        cases = [
            ("dual_qa_csv", 173, 38, 54),
            ("challenge_qa_csv", 41, 51, 52),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            for index, (key, adjudications, rule_exclusions, final_exclusions) in enumerate(cases):
                output = Path(temporary) / f"summary_{index}.json"
                process = subprocess.run(
                    [sys.executable, str(REPO_ROOT / "scripts" / "summarize_dual_reviewer_qa.py"), str(self.release / self.files[key]), "--out", str(output)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, process.returncode, process.stderr)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(adjudications, payload["human_adjudication"]["required"])
                self.assertEqual(rule_exclusions, payload["post_review_deterministic_rule_audit"]["additional_rule_exclusions"])
                self.assertEqual(final_exclusions, payload["final_release_action"]["total_exclusions"])
                parameter_kappa = payload["pre_adjudication_human_review"]["field_agreement"]["parameter_supported"]
                self.assertIsNone(parameter_kappa["cohen_kappa"])
                self.assertEqual("not_estimable_no_category_variation", parameter_kappa["kappa_status"])

    def test_incomplete_results_fail_without_output(self) -> None:
        source = release_tools.read_csv_rows(self.release / self.files["dual_qa_csv"])[0]
        source["r2_value_supported"] = ""
        with tempfile.TemporaryDirectory() as temporary:
            input_path = Path(temporary) / "incomplete.csv"
            output_path = Path(temporary) / "summary.json"
            release_tools.write_csv_rows(input_path, list(source), [source])
            process = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "summarize_dual_reviewer_qa.py"), str(input_path), "--out", str(output_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, process.returncode)
            self.assertFalse(output_path.exists())
            self.assertIn("incomplete or inconsistent", process.stderr.lower())
