from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from envcore_validation import validate_release
from tests.common import build_synthetic_public_release, build_synthetic_release


class ReleaseValidatorTests(unittest.TestCase):
    def test_public_payload_profile_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = build_synthetic_public_release(root)
            report = validate_release(root, config)
            self.assertTrue(report.passed, [item for item in report.checks if item.status == "FAIL"])

    def test_complete_synthetic_release_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = build_synthetic_release(root)
            report = validate_release(root, config)
            self.assertTrue(report.passed, [item for item in report.checks if item.status == "FAIL"])

    def test_tampered_measurement_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = build_synthetic_release(root)
            path = root / "data/measurements_long_curated_public.csv"
            path.write_text(path.read_text(encoding="utf-8").replace("20.5", "99.9"), encoding="utf-8")
            report = validate_release(root, config)
            self.assertFalse(report.passed)
            self.assertTrue(any(item.name in {"payload_manifest_values", "root_checksums"} and item.status == "FAIL" for item in report.checks))

    def test_stale_controlled_count_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = build_synthetic_release(root)
            path = root / "metadata/controlled_vocabularies_public.csv"
            text = path.read_text(encoding="utf-8").replace(",1,Synthetic controlled value.", ",2,Synthetic controlled value.")
            path.write_text(text, encoding="utf-8")
            report = validate_release(root, config)
            result = next(item for item in report.checks if item.name == "controlled_vocabulary_recount")
            self.assertEqual("FAIL", result.status)

    def test_duplicate_measurement_id_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = build_synthetic_release(root, duplicate_measurement_id=True)
            report = validate_release(root, config)
            result = next(item for item in report.checks if item.name == "measurement_id_uniqueness")
            self.assertEqual("FAIL", result.status)


if __name__ == "__main__":
    unittest.main()
