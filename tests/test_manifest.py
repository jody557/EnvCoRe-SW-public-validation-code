from __future__ import annotations

from tests.common import ReleaseTestCase, release_tools


class TestManifest(ReleaseTestCase):
    def test_manifest_columns_and_paths(self) -> None:
        manifest = self.release / self.files["manifest"]
        header, _ = release_tools.csv_header_and_count(manifest)
        self.assertEqual(release_tools.MANIFEST_FIELDS, header)
        rows = release_tools.read_csv_rows(manifest)
        listed = {row["relative_path"] for row in rows}
        actual = {
            release_tools.rel_path(self.release, path)
            for path in release_tools.iter_release_files(self.release)
            if release_tools.rel_path(self.release, path) != self.files["manifest"]
        }
        self.assertEqual(actual, listed)

    def test_manifest_hashes_counts_and_headers(self) -> None:
        for row in release_tools.read_csv_rows(self.release / self.files["manifest"]):
            path = self.release / row["relative_path"]
            self.assertEqual(int(row["size_bytes"]), path.stat().st_size, row["relative_path"])
            self.assertEqual(row["sha256"], release_tools.sha256_file(path), row["relative_path"])
            if path.suffix.lower() == ".csv":
                header, count = release_tools.csv_header_and_count(path)
                self.assertEqual(int(row["row_count"]), count, row["relative_path"])
                self.assertEqual(int(row["column_count"]), len(header), row["relative_path"])
                self.assertEqual(row["column_names"], ";".join(header), row["relative_path"])
