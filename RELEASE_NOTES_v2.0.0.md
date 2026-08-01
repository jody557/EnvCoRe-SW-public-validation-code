# EnvCoRe-SW public release validation code 2.0.0

Version `2.0.0` targets the current EnvCoRe-SW Stage 6D-R2 public-data interface. The default configuration validates the 19-file public payload; a separate configuration preserves 24-file candidate-QA validation.

## Why this is a major release

The public CLI, configuration, functional scope, and report contract are not backward compatible with `v1.1.1`. The legacy multi-command release/summary/figure-generation tools and YAML configuration are replaced by a focused JSON-configured release-candidate validator. Existing `v1.1.1` automation must be migrated; see `docs/MIGRATION_v1.1.1_to_v2.0.0.md`.

## Frozen technical target

- measurements: `20,023`
- public inventory records: `8,259`
- controlled-vocabulary rows: `122`
- default public-payload files: `19`
- separately scoped release-candidate QA files: `24`
- root checksum entries: `23`
- measurement SHA-256: `e1e7f6d0a8679af97359c19529354eb67f7d2e64d160a9f14bd660320e2c9583`
- inventory SHA-256: `24c9f1377f532bdad5d7d4f1a22dba546db4d5e18e9f9575cace058eb48ea8d7`

The validator independently recomputes file hashes, CSV sizes, identifier joins, controlled-vocabulary counts, and dictionary compatibility. It checks public aggregate validation outputs. Candidate-only manifests, gates, and incomplete-publication controls are checked only when `config/release_candidate_config.json` is selected.

The source-checksum writer is compatible with Python 3.9 and writes explicit LF line endings for cross-platform deterministic archives.

## Publication boundary

This archive is technically prepared for a new GitHub/Zenodo software-version release. Zenodo must assign the new version-specific code DOI; it is not prefilled. The new dataset-version DOI is also not guessed and is not required to mint the software-version DOI.

The package does not publish data and does not change the current dataset candidate.
