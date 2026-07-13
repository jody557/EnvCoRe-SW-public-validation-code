# Zenodo v5 data-upload verification

The v5 package is reported as uploaded. Before publication, verify the uploaded file against the locally validated artifact:

1. The local/downloaded filename may differ; identify the artifact by SHA-256, not by filename.
2. SHA-256: `48fda91a5dca95c30b5f95e32c1d026410655b38aaad577ef92561ce495f940d`.
3. ZIP root contains `README.md`, `public_dataset_manifest.csv`, `data_public/`, `qa_completed/`, `docs/`, and `scripts/` without an extra outer directory.
4. Main table has 19,122 rows and SHA-256 `1710733cb527d4241ff8fdeef27ac94a3351393d8621d32a405a02822f91f688`.
5. The package has completed 800-record and 200-record QA CSV/XLSX files and no blank QA templates.
6. Copy `zenodo_dataset_metadata_template.json` to a separate submission file. Its `metadata` object follows the Zenodo legacy deposit API schema; fill `metadata.publication_date` with the actual `YYYY-MM-DD` date, retain the creators unless explicitly changed, and use CC BY 4.0. Do not submit the template while required values remain null.
7. Create the record as a new version under data concept DOI `10.5281/zenodo.21231125`; do not overwrite version DOI `10.5281/zenodo.21231126`.
8. The reserved new data version DOI is `10.5281/zenodo.21333262` and is recorded in this repository before publishing the companion code archive. After the v1.1.0 code DOI exists, add it to the dataset record as `isSupplementedBy`; do not link the incompatible corrected-v3 code as if it validated v5.
