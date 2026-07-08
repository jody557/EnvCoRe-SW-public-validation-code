# EnvCoRe-SW public reproducibility code, corrected v3

This code package supports the public release of:

EnvCoRe-SW: A de-identified environmental compliance monitoring report corpus and structured measurement extraction dataset from Southwest China, 2018-2025 (corrected v3).

Dataset DOI: https://doi.org/10.5281/zenodo.21231126

## Scope

The scripts in this package are the public reproducibility and validation code for the corrected v3 public release. They:

- validate the public package manifest, file sizes, row counts, column counts and SHA-256 checksums;
- check the key table counts reported in the manuscript;
- verify cross-file links among the corrected measurement layer, report inventory, standardized candidate layer, pollutant dictionary and human QA sample;
- verify the corrected v3 correction-history counts;
- regenerate the figure source data from the public CSV files;
- scan the public package for private source-path and raw-text disclosure patterns.

The private end-to-end extraction pipeline used to parse the original source reports is not included here because it depends on non-public source reports, private source paths, private crosswalks and private manual review context. This public code package is therefore designed to reproduce and audit the public data release, not to redistribute the private source corpus.

## Requirements

Python 3.9 or newer. The scripts use only the Python standard library.

## Quick start

From this directory, run:

```bash
python scripts/envcore_sw_public_release_tools.py all --release path/to/EnvCoRe-SW_public_release_corrected_v3_20260705.zip --out outputs/check_corrected_v3
```

The `--release` argument may point either to the Zenodo ZIP file or to the extracted release directory containing `public_dataset_manifest.csv`.

## Outputs

The `all` command writes:

- `validation_report.json`
- `validation_report.md`
- `manuscript_key_counts.json`
- regenerated figure source CSV files in `figure_source_data_rebuilt/`
- `regenerated_manifest_technical.csv`

The validation report should end with `PASS` for the published corrected v3 package.

## Recommended manuscript text

See `docs/code_availability_text.md`.
