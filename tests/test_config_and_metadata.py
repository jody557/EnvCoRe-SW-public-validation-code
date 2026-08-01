from __future__ import annotations

import json
import unittest
from pathlib import Path

from envcore_validation import load_config


ROOT = Path(__file__).resolve().parents[1]


class ConfigAndMetadataTests(unittest.TestCase):
    def test_version_is_consistent(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        config = load_config(ROOT / "config/release_config.json")
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertEqual("2.0.0", version)
        self.assertEqual(version, config["software_version"])
        self.assertIn('version: "2.0.0"', citation)

    def test_public_and_candidate_profiles_are_explicit(self) -> None:
        public = load_config(ROOT / "config/release_config.json")
        candidate = load_config(ROOT / "config/release_candidate_config.json")
        self.assertEqual("public_payload", public["validation_profile"])
        self.assertEqual(19, len(public["required_files"]))
        self.assertEqual("candidate_qa", candidate["validation_profile"])
        self.assertEqual(24, len(candidate["required_files"]))

    def test_unassigned_dois_are_not_invented(self) -> None:
        config = load_config(ROOT / "config/release_config.json")
        metadata = json.loads((ROOT / "zenodo/zenodo_code_metadata_template.json").read_text(encoding="utf-8"))
        self.assertIsNone(config["associated_data_version_doi"])
        related = metadata["metadata"]["related_identifiers"]
        self.assertNotIn("10.5281/zenodo.21339244", {item["identifier"] for item in related})
        self.assertIn("10.5281/zenodo.21340470", {item["identifier"] for item in related})
        self.assertEqual("2026-08-01", metadata["metadata"]["publication_date"])
        self.assertTrue(all(set(creator) == {"name"} for creator in metadata["metadata"]["creators"]))


if __name__ == "__main__":
    unittest.main()
