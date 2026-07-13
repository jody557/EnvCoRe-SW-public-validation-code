from __future__ import annotations

from tests.common import ReleaseTestCase, release_tools


class TestSchemaAndDerivedProducts(ReleaseTestCase):
    def test_figure_sources_rebuild_exactly(self) -> None:
        report = release_tools.ValidationReport(self.config)
        release_tools.validate_figures(self.release, report, self.config)
        self.assertTrue(report.passed, [item for item in report.checks if item["status"] == "FAIL"])

    def test_table_row_count_semantics(self) -> None:
        report = release_tools.ValidationReport(self.config)
        release_tools.validate_table_row_semantics(self.release, report, self.config)
        self.assertTrue(report.passed, [item for item in report.checks if item["status"] == "FAIL"])
