from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.create_source_zip import ARCHIVE_ROOT, build_archive


class SourceZipTests(unittest.TestCase):
    def test_two_builds_are_identical_and_single_rooted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first.zip"
            second = Path(temp) / "second.zip"
            first_hash = build_archive(first)
            second_hash = build_archive(second)
            self.assertEqual(first_hash, second_hash)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as zf:
                names = zf.namelist()
                self.assertTrue(names)
                self.assertTrue(all(name.startswith(ARCHIVE_ROOT + "/") for name in names))
                self.assertEqual(len(names), len(set(name.casefold() for name in names)))
                self.assertIn(f"{ARCHIVE_ROOT}/SHA256SUMS.txt", names)


if __name__ == "__main__":
    unittest.main()
