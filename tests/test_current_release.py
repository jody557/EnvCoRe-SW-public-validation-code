from __future__ import annotations

import os
import unittest
from pathlib import Path

from envcore_validation import load_config, open_release, validate_release


ROOT = Path(__file__).resolve().parents[1]


class CurrentReleaseIntegrationTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("ENVCORE_PUBLIC_RELEASE"), "ENVCORE_PUBLIC_RELEASE is not set")
    def test_public_payload_passes(self) -> None:
        config = load_config(ROOT / "config/release_config.json")
        with open_release(Path(os.environ["ENVCORE_PUBLIC_RELEASE"])) as release_root:
            report = validate_release(release_root, config)
        self.assertTrue(report.passed, [item for item in report.checks if item.status == "FAIL"])

    @unittest.skipUnless(
        os.environ.get("ENVCORE_CANDIDATE_RELEASE") or os.environ.get("ENVCORE_RELEASE"),
        "ENVCORE_CANDIDATE_RELEASE is not set",
    )
    def test_candidate_qa_passes(self) -> None:
        config = load_config(ROOT / "config/release_candidate_config.json")
        source = os.environ.get("ENVCORE_CANDIDATE_RELEASE") or os.environ["ENVCORE_RELEASE"]
        with open_release(Path(source)) as release_root:
            report = validate_release(release_root, config)
        self.assertTrue(report.passed, [item for item in report.checks if item.status == "FAIL"])


if __name__ == "__main__":
    unittest.main()
