from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
import re
import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import envcore_sw_public_release_tools as release_tools
import create_release_zip
import summarize_dual_reviewer_qa as qa_summary


class TestUnitHelpers(unittest.TestCase):
    def test_manifest_comparison_is_order_independent(self) -> None:
        first = {
            "relative_path": "b.csv",
            "size_bytes": 2,
            "sha256": "b" * 64,
            "row_count": 1,
            "column_count": 1,
            "column_names": "x",
            "description": "B",
            "release_role": "data",
        }
        second = dict(first, relative_path="a.csv", sha256="a" * 64, description="A")
        self.assertTrue(release_tools.manifest_rows_equivalent([first, second], [second, first]))
        self.assertFalse(release_tools.manifest_rows_equivalent([first], [second]))
        duplicate_path = dict(first, sha256="c" * 64, description="C")
        self.assertTrue(
            release_tools.manifest_rows_equivalent(
                [first, duplicate_path], [duplicate_path, first]
            )
        )

    def test_kappa_without_category_variation_is_not_estimable(self) -> None:
        value, status = qa_summary.cohen_kappa(["yes"] * 10, ["yes"] * 10)
        self.assertIsNone(value)
        self.assertEqual("not_estimable_no_category_variation", status)

    def test_kappa_with_variation_is_estimated(self) -> None:
        value, status = qa_summary.cohen_kappa(["yes", "yes", "no", "no"], ["yes", "no", "no", "no"])
        self.assertIsInstance(value, float)
        self.assertEqual("estimated", status)

    def test_kappa_rejects_unequal_reviewer_vectors(self) -> None:
        with self.assertRaisesRegex(ValueError, "equal length"):
            qa_summary.cohen_kappa(["yes", "no"], ["yes"])

    def test_zip_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "unsafe.zip"
            destination = Path(temporary) / "out"
            destination.mkdir()
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../escape.txt", "unsafe")
            with self.assertRaises(ValueError):
                release_tools.safe_extract_zip(archive_path, destination)

    def test_unassigned_dois_are_blank_not_placeholders(self) -> None:
        config = {"data_doi": "", "code_doi": ""}
        report = release_tools.ValidationReport(
            {
                "dataset_title": "test",
                "dataset_version": "test",
                "dataset_correction_state": "test",
                **config,
            }
        )
        release_tools.validate_doi_values(report, config)
        self.assertTrue(report.passed)

        invalid = {"data_doi": "PENDING_DOI", "code_doi": "not-a-doi"}
        invalid_report = release_tools.ValidationReport(
            {
                "dataset_title": "test",
                "dataset_version": "test",
                "dataset_correction_state": "test",
                **invalid,
            }
        )
        release_tools.validate_doi_values(invalid_report, invalid)
        self.assertFalse(invalid_report.passed)

    def test_machine_readable_metadata_has_no_placeholder_doi(self) -> None:
        citation = (REPO_ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertNotIn("TODO_", citation)
        citation_dois = re.findall(r'^\s*doi:\s*["\']?([^"\'\s]+)', citation, re.MULTILINE)
        self.assertTrue(all(release_tools.DOI_RE.fullmatch(value) for value in citation_dois))
        config = release_tools.load_config(REPO_ROOT / "config" / "release_config.yaml")
        for key in ("data_doi", "code_doi"):
            value = str(config[key])
            self.assertNotIn("TODO", value)
            self.assertTrue(not value or release_tools.DOI_RE.fullmatch(value))
        zenodo_files = list((REPO_ROOT / "zenodo").iterdir())
        self.assertFalse(any("draft" in path.name for path in zenodo_files))
        placeholder_marker = "TODO" + "_NEW_"
        for path in zenodo_files:
            if path.suffix.lower() in {".json", ".bib"}:
                self.assertNotIn(placeholder_marker, path.read_text(encoding="utf-8"), path.name)

    def test_zenodo_templates_use_deposition_api_metadata_shape(self) -> None:
        allowed_metadata_fields = {
            "title",
            "upload_type",
            "publication_date",
            "description",
            "access_right",
            "creators",
            "keywords",
            "version",
            "language",
            "license",
            "notes",
            "related_identifiers",
        }
        allowed_relations = {"isNewVersionOf", "isIdenticalTo", "isSupplementedBy", "isSupplementTo"}
        templates = {
            "zenodo_code_metadata_template.json": ("software", "mit"),
            "zenodo_dataset_metadata_template.json": ("dataset", "cc-by-4.0"),
        }
        for name, (upload_type, license_id) in templates.items():
            payload = json.loads((REPO_ROOT / "zenodo" / name).read_text(encoding="utf-8"))
            self.assertEqual({"metadata"}, set(payload), name)
            metadata = payload["metadata"]
            self.assertFalse(set(metadata) - allowed_metadata_fields, name)
            self.assertEqual(upload_type, metadata["upload_type"])
            self.assertEqual(license_id, metadata["license"])
            self.assertIsInstance(metadata["license"], str)
            self.assertIsNone(metadata["publication_date"])
            self.assertNotIn("resource_type", metadata)
            for related in metadata["related_identifiers"]:
                self.assertEqual({"identifier", "relation"}, set(related), name)
                self.assertIn(related["relation"], allowed_relations)
                identifier = related["identifier"]
                self.assertTrue(
                    identifier.startswith("https://") or release_tools.DOI_RE.fullmatch(identifier),
                    identifier,
                )

    def test_disclosure_scan_reports_line_without_full_file_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.csv").write_text("field\nvalue\nsource_file_path\n", encoding="utf-8")
            report = release_tools.ValidationReport(
                {
                    "dataset_title": "test",
                    "dataset_version": "test",
                    "dataset_correction_state": "test",
                    "data_doi": "",
                }
            )
            release_tools.validate_disclosure(root, report)
            self.assertFalse(report.passed)
            disclosure = next(item for item in report.checks if item["name"] == "no sensitive disclosure patterns")
            self.assertEqual(3, disclosure["observed"][0]["line"])

    def test_release_zip_excludes_generated_and_repository_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "README.md").write_text("release\n", encoding="utf-8")
            workflow = source / ".github" / "workflows" / "tests.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("name: tests\n", encoding="utf-8")
            generated = {
                source / "outputs" / "validation.json": "{}\n",
                source / "scripts" / "__pycache__" / "module.pyc": "cache",
                source / ".coverage": "coverage data",
            }
            for path, content in generated.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            first = root / "first.zip"
            second = root / "second.zip"
            create_release_zip.build_zip(source, first)
            create_release_zip.build_zip(source, second)

            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    [".github/workflows/tests.yml", "README.md"], archive.namelist()
                )
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_release_zip_uses_only_tracked_files_in_a_git_checkout(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required for checkout packaging test")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            readme = source / "README.md"
            readme.write_text("tracked before edit\n", encoding="utf-8")
            secret = source / ".env"
            secret.write_text("TOKEN=do-not-package\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "add", "README.md"], check=True)
            readme.write_text("tracked working-tree content\n", encoding="utf-8")

            archive_path = root / "release.zip"
            create_release_zip.build_zip(source, archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(["README.md"], archive.namelist())
                self.assertEqual(
                    "tracked working-tree content\n",
                    archive.read("README.md").decode("utf-8").replace("\r\n", "\n"),
                )

    def test_release_zip_rejects_unknown_files_without_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "README.md").write_text("public\n", encoding="utf-8")
            private = source / "docs" / "private_notes.md"
            private.parent.mkdir()
            private.write_text("secret\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "outside the public source allowlist"):
                create_release_zip.build_zip(source, root / "release.zip")

    def test_all_output_cleanup_requires_a_recognized_tool_owned_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = root / "release"
            release.mkdir()
            unowned = root / "unowned"
            unowned.mkdir()
            important = unowned / "important.txt"
            important.write_text("keep\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unrecognized non-empty"):
                release_tools.prepare_all_output_directory(unowned, True, release)
            self.assertEqual("keep\n", important.read_text(encoding="utf-8"))

            managed = root / "managed"
            release_tools.prepare_all_output_directory(managed, False, release)
            report = managed / "validation_report.json"
            report.write_text("{}\n", encoding="utf-8")
            release_tools.prepare_all_output_directory(managed, True, release)
            self.assertFalse(report.exists())
            self.assertTrue((managed / release_tools.ALL_OUTPUT_MARKER).is_file())

            unexpected = managed / "manual_notes.txt"
            unexpected.write_text("do not delete\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unrecognized non-empty"):
                release_tools.prepare_all_output_directory(managed, True, release)
            self.assertTrue(unexpected.exists())

            with self.assertRaisesRegex(ValueError, "inside the validated release"):
                release_tools.prepare_all_output_directory(
                    release / "outputs", True, release
                )


if __name__ == "__main__":
    unittest.main()
