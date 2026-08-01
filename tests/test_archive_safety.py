from __future__ import annotations

import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from envcore_validation.io import ReleaseInputError, inspect_zip, open_release


class ArchiveSafetyTests(unittest.TestCase):
    def _archive(self, members):
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "test.zip"
        with zipfile.ZipFile(path, "w") as zf:
            for item in members:
                if isinstance(item, zipfile.ZipInfo):
                    zf.writestr(item, b"target")
                else:
                    zf.writestr(item, b"x")
        return temp, path

    def test_rejects_path_traversal(self) -> None:
        temp, path = self._archive(["../escape.txt"])
        self.addCleanup(temp.cleanup)
        with self.assertRaises(ReleaseInputError):
            inspect_zip(path)

    def test_rejects_case_collision(self) -> None:
        temp, path = self._archive(["root/File.txt", "root/file.txt"])
        self.addCleanup(temp.cleanup)
        with self.assertRaises(ReleaseInputError):
            inspect_zip(path)

    def test_rejects_symlink(self) -> None:
        info = zipfile.ZipInfo("root/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        temp, path = self._archive([info])
        self.addCleanup(temp.cleanup)
        with self.assertRaises(ReleaseInputError):
            inspect_zip(path)

    def test_detects_single_root_public_payload_without_candidate_manifest(self) -> None:
        temp, path = self._archive(
            [
                "public/data/measurements_long_curated_public.csv",
                "public/data/report_inventory_public.csv",
                "public/metadata/public_file_manifest.csv",
            ]
        )
        self.addCleanup(temp.cleanup)
        with open_release(path) as root:
            self.assertEqual("public", root.name)


if __name__ == "__main__":
    unittest.main()
