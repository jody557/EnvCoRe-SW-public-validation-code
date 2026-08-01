from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MajorVersionPolicyTests(unittest.TestCase):
    def test_major_release_documents_breaking_interface(self) -> None:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        migration = (ROOT / "docs/MIGRATION_v1.1.1_to_v2.0.0.md").read_text(encoding="utf-8")
        self.assertIn("## 2.0.0", changelog)
        self.assertIn("Breaking changes", changelog)
        self.assertIn("not a drop-in replacement", migration)
        self.assertIn("validate_release.py", migration)

    def test_no_unreleased_1_2_0_software_version_markers(self) -> None:
        checked = [
            ROOT / "VERSION",
            ROOT / "README.md",
            ROOT / "CHANGELOG.md",
            ROOT / "CITATION.cff",
            ROOT / "config/release_config.json",
            ROOT / "envcore_validation/__init__.py",
            ROOT / "zenodo/zenodo_code_metadata_template.json",
        ]
        for path in checked:
            text = path.read_text(encoding="utf-8")
            if path.name == "CITATION.cff":
                # cff-version 1.2.0 is the Citation File Format schema version.
                text = text.replace("cff-version: 1.2.0", "")
            self.assertNotIn("1.2.0", text, path.as_posix())


if __name__ == "__main__":
    unittest.main()
