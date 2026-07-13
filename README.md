# EnvCoRe-SW public validation and figure-generation code

This repository is the public validation companion for the EnvCoRe-SW **v5 data package with all v5.5 follow-up corrections applied**:

> **EnvCoRe-SW: a de-identified inventory and structured environmental measurement dataset derived from environmental compliance monitoring reports in Guizhou Province, Southwest China, 2018–2025**

Software version `1.1.0` targets the v5 archive identified by the following hashes. The local/downloaded filename may differ; **SHA-256 is authoritative**:

- ZIP SHA-256: `48fda91a5dca95c30b5f95e32c1d026410655b38aaad577ef92561ce495f940d`
- main-table SHA-256: `1710733cb527d4241ff8fdeef27ac94a3351393d8621d32a405a02822f91f688`
- manifest SHA-256: `7f4c51c5faeee50c1b6ebb86eae99b6aa157e3a29855fce1b3feb7825044a0cd`

The reserved v5 data-version DOI is [10.5281/zenodo.21333262](https://doi.org/10.5281/zenodo.21333262). It identifies the final cross-platform v5 data archive pinned by the hashes above. The previous published data version is [10.5281/zenodo.21231126](https://doi.org/10.5281/zenodo.21231126).

## What this code validates

The validator independently checks:

- all 77 manifest entries, sizes, SHA-256 values, CSV row counts, headers, descriptions, and release roles;
- the 19,122-row current measurement table and its disjoint 1,392-row cumulative exclusion audit;
- report, candidate, parameter-dictionary, QA, retained-record, and excluded-record identifier relationships;
- the completed 800-record stratified dual-human review and 200-record targeted challenge review;
- strict separation of frozen R1/R2 assessments, `HUM_ADJ01` human adjudication, later deterministic `post_review_*` audit fields, and final release actions;
- semantic CSV/XLSX equality without requiring a third-party spreadsheet library;
- a fresh field-level reconstruction of the eight-record challenge `OVERLAP_AUDIT`;
- application of all media/group, unit, floating-value, fecal-limit-unit, censored-compliance, and arsenic source-unit corrections to the main table;
- resolution of the reviewed parameter–unit anomalies and censored-pass ambiguities;
- exact active-schema coverage for 44 CSVs, controlled-vocabulary references, table-row-count semantics, summaries, column hashes, and figure source data; and
- disclosure controls and absence of blank QA templates.

This repository does **not** contain private source reports, readable original report text, source paths, facility names, private crosswalks, or the private extraction/review workspace. It therefore validates the public release and rebuilds public derivatives; it cannot recreate the source-report review decisions from original documents.

## Requirements

Python 3.9 or newer. Runtime and tests use only the Python standard library.

## Validate the exact ZIP

```bash
python scripts/envcore_sw_public_release_tools.py \
  --config config/release_config.yaml \
  all \
  --release path/to/EnvCoRe-SW_public_release_v5.zip \
  --out outputs/reproducibility_check \
  --clean
```

The same command accepts an extracted release root. ZIP input additionally checks the exact confirmed ZIP SHA-256. The `all` command writes a validation report, release summary, regenerated manifest, and rebuilt figure-source CSVs. A conforming package ends with `Validation status: PASS`.

Individual subcommands are also available:

```bash
python scripts/envcore_sw_public_release_tools.py --config config/release_config.yaml validate --release path/to/package.zip --out outputs/validation
python scripts/envcore_sw_public_release_tools.py --config config/release_config.yaml summary  --release path/to/package.zip --out outputs/release_summary.json
python scripts/envcore_sw_public_release_tools.py --config config/release_config.yaml figures  --release path/to/package.zip --out outputs/figures
python scripts/envcore_sw_public_release_tools.py --config config/release_config.yaml manifest --release path/to/package.zip --out outputs/regenerated_manifest.csv
```

## QA summary

The QA summarizer refuses incomplete or internally inconsistent review files and reports each review stage separately:

```bash
python scripts/summarize_dual_reviewer_qa.py \
  path/to/qa_completed/stratified_800_dual_human_review_v5.csv \
  --out outputs/stratified_800_summary.json
```

It also accepts `targeted_water_parameter_challenge_review_v5.csv`. When a reviewer field has no category variation, Cohen's kappa is reported as `null` with `kappa_status: not_estimable_no_category_variation`; percent agreement remains available.

## Tests

`ENVCORE_RELEASE` may point to the ZIP or extracted release root:

```bash
ENVCORE_RELEASE=path/to/EnvCoRe-SW_public_release_v5.zip \
python -m unittest discover -s tests -v
```

PowerShell:

```powershell
$env:ENVCORE_RELEASE = "C:\path\to\EnvCoRe-SW_public_release_v5.zip"
python -m unittest discover -s tests -v
```

GitHub Actions runs release-independent tests on Python 3.9, 3.11, and 3.13 for every push and pull request. A manual workflow can download a user-supplied public release URL, run the exact-hash `all` command, record resource metrics, and execute the full release-dependent suite.

## Release continuity

The previous archived code version is [10.5281/zenodo.21252350](https://doi.org/10.5281/zenodo.21252350), under code concept DOI `10.5281/zenodo.21252349`. It validates corrected-v3 and is not compatible with v5. Publish software `1.1.0` as a new version of that existing code concept record. The associated data version is [10.5281/zenodo.21333262](https://doi.org/10.5281/zenodo.21333262); add the software version DOI only after Zenodo assigns it.

Files under `zenodo/` whose names contain `template` are preparation aids, not directly submittable metadata. Required unassigned values are null/blank, and must be filled with real assigned values in a separate submission copy.

See `RELEASE_NOTES_v1.1.0.md`, `docs/release_linkage.md`, and `zenodo/` for release preparation details.
