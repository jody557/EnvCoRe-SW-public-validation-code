# EnvCoRe-SW public validation code 1.1.1 — corrected v5/v5.5 DOI linkage

Version `1.1.1` supersedes `1.1.0` because the latter referenced `10.5281/zenodo.21333262`, a deleted Zenodo software record, as though it were the dataset DOI.

## Changes from 1.1.0

- Replaced the invalid/tombstoned dataset DOI with the reserved v5 data-version DOI `10.5281/zenodo.21339244`.
- Rebuilt the immutable cross-platform v5 data ZIP after the DOI correction.
- Clarified the controlled-vocabulary cleanup history: 285 rows immediately after stale-reference removal and 286 current rows after the later v5.5 vocabulary regeneration.
- Updated the exact data ZIP SHA-256 to `36e0bda4a4ffe47427892d88a8ecf7fcfece3e9ef70aa3a2cfff658fa2c4cd9b`.
- Updated the embedded public manifest SHA-256 to `8aadd4ff20d97676737f2406dce7b1ca42be6d75ae43a7c41f5c4db0b35745e4`.
- Retained the unchanged curated main-table SHA-256 `1710733cb527d4241ff8fdeef27ac94a3351393d8621d32a405a02822f91f688`.
- Updated release-continuity and Zenodo metadata templates so software `1.1.1` is a new version of software DOI `10.5281/zenodo.21338722` under concept DOI `10.5281/zenodo.21252349`.
- Removed the circular requirement to insert an unassigned software DOI into the immutable tagged source archive. The assigned software DOI is linked externally through Zenodo metadata after archiving.

## Exact target artifacts

- v5 archive SHA-256: `36e0bda4a4ffe47427892d88a8ecf7fcfece3e9ef70aa3a2cfff658fa2c4cd9b`
- `measurements_long_curated_public.csv`: `1710733cb527d4241ff8fdeef27ac94a3351393d8621d32a405a02822f91f688`
- `public_dataset_manifest.csv`: `8aadd4ff20d97676737f2406dce7b1ca42be6d75ae43a7c41f5c4db0b35745e4`
- data DOI: `10.5281/zenodo.21339244`

## Publication sequence

1. Commit this exact source state.
2. Create GitHub tag/release `v1.1.1`.
3. Archive the release as a new software version under Zenodo concept DOI `10.5281/zenodo.21252349`.
4. Add the assigned software DOI to the dataset record `10.5281/zenodo.21339244` as `isSupplementedBy`.
5. Publish the data record after the final metadata preview.

## Validation

The exact corrected data ZIP must pass the integrated `all` workflow and the complete automated test suite. See `docs/local_validation_note.md` for the measured results.
