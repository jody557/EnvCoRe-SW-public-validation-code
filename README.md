# EnvCoRe-SW public release validation code

Version `2.0.0` is the validation companion for the current EnvCoRe-SW public-data structure containing **20,023 measurements**, **8,259 public inventory records**, and **122 controlled-vocabulary rows**.

This is a major release because it replaces the public command/configuration contract used by `v1.1.1`. The current interface is a focused release-candidate validator with a JSON configuration schema and deterministic validation reports. The legacy multi-command release/summary/figure-generation interface and YAML configuration are not retained. See `docs/MIGRATION_v1.1.1_to_v2.0.0.md`.

The validator uses only the Python standard library. It accepts either an extracted release root or a ZIP with one top-level directory. The default configuration validates the **19-file public distribution payload**. A separate, explicit configuration validates the **24-file internal release-candidate QA package** without mixing the two scopes.

## Validation scope

The default configuration checks:

- archive path safety, duplicate/case-colliding members, and symlinks;
- the exact 19-file public payload and 6-row public-file manifest in the default public profile;
- SHA-256, byte size, CSV row count, column count, and CSV/JSON manifest equivalence;
- pinned hashes for the formal measurement, inventory, dictionary, controlled-vocabulary, known-issue, and aggregate-metric artifacts;
- 20,023 unique measurement IDs, 8,259 unique report IDs, and complete measurement-to-inventory joins;
- exact active data-dictionary coverage and a fresh recount of all 122 controlled-vocabulary rows;
- parameter, medium, parameter-group, and expected-unit compatibility, including the five explicitly disclosed source-unit exceptions for `color = mg/L`;
- the 13 `water_temperature` / `°C` records and frozen dictionary support;
- Final300, Probability50, and schema-scope metric structure, range checks, and 5,000-replicate declarations;
- technical gates, incomplete-publication-metadata consistency, and public-text privacy sentinels.

The optional candidate-QA profile additionally checks the 24-file candidate layout, 23 root checksum entries, CSV/JSON candidate manifests, technical gates, and the incomplete-publication-metadata boundary.

This repository validates public release artifacts and the separately scoped candidate QA package. It does not include source reports, a private crosswalk, row-level review evidence, reviewer identities, or adjudication ledgers, and it does not recalculate source-evidence judgments from private inputs.

## Requirements

Python 3.9 or newer; no third-party packages are required.

## Run validation

```bash
python scripts/validate_release.py \
  --release path/to/EnvCoRe-SW_public_payload.zip \
  --out outputs/public_payload
```

The command writes `validation_report.json` and `validation_report.md`. The report records `validation_profile: public_payload`. Exit code `0` means every required check passed; exit code `1` means at least one check failed; exit code `2` means the input or configuration could not be opened safely.

Validate the 24-file candidate QA package only with the explicit candidate configuration:

```bash
python scripts/validate_release.py \
  --config config/release_candidate_config.json \
  --release path/to/EnvCoRe-SW_candidate_QA.zip \
  --out outputs/candidate_qa
```

An extracted directory is also accepted:

```bash
python scripts/validate_release.py --release path/to/extracted/root --out outputs/current_candidate
```

Additional files are rejected by default. Use `--allow-extra-files` only for a controlled audit workspace; it is not appropriate for validating a distribution ZIP.

## Tests

```bash
python -m compileall -q envcore_validation scripts tests
python -m unittest discover -s tests -v
```

To run the integration test against a real candidate:

```bash
ENVCORE_PUBLIC_RELEASE=path/to/public_payload.zip \
ENVCORE_CANDIDATE_RELEASE=path/to/candidate_QA.zip \
python -m unittest tests.test_current_release -v
```

PowerShell:

```powershell
$env:ENVCORE_PUBLIC_RELEASE = "C:\path\to\public_payload.zip"
$env:ENVCORE_CANDIDATE_RELEASE = "C:\path\to\candidate_QA.zip"
python -m unittest tests.test_current_release -v
```

## Build the code archive

First refresh the source checksum list, then create the deterministic archive:

```bash
python scripts/update_source_checksums.py
python scripts/create_source_zip.py --out dist/EnvCoRe-SW-public-validation-code_v2.0.0.zip
```

The build rejects symlinks, local absolute paths, interpreter caches, local Git metadata, and unlisted build artifacts.

## Release linkage

The preceding archived software version is `1.1.1`, DOI `10.5281/zenodo.21340470`, under code concept DOI `10.5281/zenodo.21252349`. The new `2.0.0` version DOI must remain blank inside the immutable source archive until Zenodo assigns it. The associated new dataset-version DOI is intentionally absent and can be added to repository and Zenodo metadata after that DOI exists; its absence does not change the frozen 20,023/8,259 technical target.

DOI `10.5281/zenodo.21339244` is a dataset record and must not be used as the code DOI. See `docs/release_linkage.md` and `zenodo/README.md` before upload.
