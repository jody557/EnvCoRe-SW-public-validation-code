from __future__ import annotations

from tests.common import ReleaseTestCase, release_tools


class TestDocumentationConsistency(ReleaseTestCase):
    def test_documentation_and_schema_checks(self) -> None:
        report = release_tools.ValidationReport(self.config)
        release_tools.validate_schema_and_docs(self.release, report, self.config)
        self.assertTrue(report.passed, [item for item in report.checks if item["status"] == "FAIL"])

    def test_doi_values_are_real_or_blank_while_unassigned(self) -> None:
        report = release_tools.ValidationReport(self.config)
        release_tools.validate_doi_values(report, self.config)
        self.assertTrue(report.passed, report.checks)

    def test_no_private_disclosure(self) -> None:
        report = release_tools.ValidationReport(self.config)
        release_tools.validate_disclosure(self.release, report)
        self.assertTrue(report.passed, report.checks)
