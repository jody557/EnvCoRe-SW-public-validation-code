from __future__ import annotations

from tests.common import ReleaseTestCase, release_tools


class TestReleaseFiles(ReleaseTestCase):
    def test_required_files_and_configured_counts(self) -> None:
        report = release_tools.ValidationReport(self.config)
        release_tools.validate_expected_counts(self.release, report, self.config)
        self.assertTrue(report.passed, [item for item in report.checks if item["status"] == "FAIL"])

    def test_exact_confirmed_zip_hash_when_zip_is_supplied(self) -> None:
        if self.zip_info is None:
            self.skipTest("ENVCORE_RELEASE points to an extracted directory, so there is no ZIP hash to test.")
        self.assertEqual(self.config["expected_release_zip_sha256"], self.zip_info["sha256"])

    def test_summary_metadata_and_column_hashes(self) -> None:
        report = release_tools.ValidationReport(self.config)
        release_tools.validate_summary_metadata(self.release, report, self.config)
        release_tools.validate_column_hashes(self.release, report, self.config)
        self.assertTrue(report.passed, [item for item in report.checks if item["status"] == "FAIL"])
