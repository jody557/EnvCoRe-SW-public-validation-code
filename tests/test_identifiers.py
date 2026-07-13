from __future__ import annotations

from tests.common import ReleaseTestCase, release_tools


class TestIdentifiers(ReleaseTestCase):
    def test_curated_measurement_structure_and_exact_hash(self) -> None:
        report = release_tools.ValidationReport(self.config)
        release_tools.validate_curated_measurements(self.release, report, self.config)
        self.assertTrue(report.passed, [item for item in report.checks if item["status"] == "FAIL"])

    def test_cross_file_identifiers_and_pre_v5_partition(self) -> None:
        report = release_tools.ValidationReport(self.config)
        release_tools.validate_identifiers(self.release, report, self.config)
        self.assertTrue(report.passed, [item for item in report.checks if item["status"] == "FAIL"])
