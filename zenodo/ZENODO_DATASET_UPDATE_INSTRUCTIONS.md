# Zenodo v5 data-upload verification

Before publication, verify the uploaded data file against the locally validated artifact:

1. The local/downloaded filename may differ; identify the artifact by SHA-256, not by filename.
2. Data version DOI: `10.5281/zenodo.21339244`.
3. ZIP SHA-256: `36e0bda4a4ffe47427892d88a8ecf7fcfece3e9ef70aa3a2cfff658fa2c4cd9b`.
4. ZIP root contains `README.md`, `public_dataset_manifest.csv`, `data_public/`, `qa_completed/`, `docs/`, and `scripts/` without an extra outer directory.
5. Main table has 19,122 rows and SHA-256 `1710733cb527d4241ff8fdeef27ac94a3351393d8621d32a405a02822f91f688`.
6. Manifest SHA-256 is `8aadd4ff20d97676737f2406dce7b1ca42be6d75ae43a7c41f5c4db0b35745e4`.
7. The package has completed 800-record and 200-record QA CSV/XLSX files and no blank QA templates.
8. Create the record as a new version under data concept DOI `10.5281/zenodo.21231125`; do not overwrite version DOI `10.5281/zenodo.21231126`.
9. Copy `zenodo_dataset_metadata_template.json` to a separate submission file and fill `metadata.publication_date` with the actual publication date.
10. After the `v1.1.1` software DOI is assigned, add it to the dataset record as `isSupplementedBy`. Do not insert the incompatible corrected-v3 code DOI.
11. Preview the record, verify CC BY 4.0, open access, version `v5`, creators, title, files, and related software DOI, then publish.
