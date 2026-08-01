from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.update_source_checksums import write_checksum_file


class PythonCompatibilityTests(unittest.TestCase):
    def test_checksum_writer_uses_lf_and_runs_on_supported_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "SHA256SUMS.txt"
            write_checksum_file(target, ["a" * 64 + "  first.txt", "b" * 64 + "  second.txt"])
            self.assertEqual(
                ("a" * 64 + "  first.txt\n" + "b" * 64 + "  second.txt\n").encode("utf-8"),
                target.read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
