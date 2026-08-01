# Changelog

## 2.0.0 - 2026-08-01

### Breaking changes

- Replaced the `v1.1.1` multi-command release, summary, figure-generation, and manifest-regeneration interface with a focused release-candidate validator.
- Replaced the legacy YAML configuration contract with `config/release_config.json`.
- Removed the legacy dual-review summarization and figure-generation entry points from the public interface.
- Replaced the older 19,122-record v5 validation contract with the Stage 6D-R2 / Stage 8A-R1 contract for 20,023 measurements, 8,259 inventory records, 122 controlled-vocabulary rows, 24 candidate files, and 19 public payload files.
- Replaced the legacy output contract with deterministic `validation_report.json` and `validation_report.md` outputs.

### Added and improved

- Made the 19-file public payload the default validation profile and retained the 24-file candidate QA checks under an explicit separate configuration.
- Fixed `update_source_checksums.py` for actual Python 3.9 compatibility while preserving LF-only deterministic output.
- Added safe ZIP handling, exact candidate/payload file-set checks, root and metadata checksum verification, and CSV/JSON manifest equivalence.
- Added fresh identifier, join, data-dictionary, controlled-vocabulary, pollutant-dictionary, unit-exception, validation-metric, gate, and privacy checks.
- Added explicit validation of the 13 `water_temperature` / `°C` records and frozen dictionary support.
- Added deterministic source packaging, source checksums, release-independent negative controls, and optional real-candidate integration tests.
- Corrected DOI roles: `10.5281/zenodo.21340470` is the preceding software-version DOI; `10.5281/zenodo.21339244` is a dataset record, not a code DOI.

## 1.1.1 - 2026-07-13

- Previous archived software release for the older 19,122-record data package.
