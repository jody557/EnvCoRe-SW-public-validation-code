from __future__ import annotations

from tests.common import ReleaseTestCase, release_tools


class TestV5Corrections(ReleaseTestCase):
    def test_all_v5_and_v5_5_audits_are_applied(self) -> None:
        report = release_tools.ValidationReport(self.config)
        release_tools.validate_v5_corrections(self.release, report, self.config)
        self.assertTrue(report.passed, [item for item in report.checks if item["status"] == "FAIL"])
