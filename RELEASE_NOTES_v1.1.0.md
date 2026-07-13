> **Historical/superseded release note.** GitHub/Zenodo software version `1.1.0` was archived before the dataset DOI was corrected. It references the deleted record `10.5281/zenodo.21333262` and is superseded by `1.1.1`, which targets `10.5281/zenodo.21339244`.

# EnvCoRe-SW public validation code 1.1.0 — v5/v5.5 release candidate

Version `1.1.0` aligns the public code with the exact EnvCoRe-SW v5 ZIP after the v5.5 limit-unit, censored-compliance, and arsenic source-unit follow-up.

## Changes from 1.0.0

- Replaced the obsolete corrected-v3/v4 and single-reviewer assumptions with the final 19,122-record v5 measurement layer.
- Pinned the validator to the confirmed ZIP, main-table, and manifest SHA-256 values.
- Added cumulative retained/excluded partition checks for 19,122 + 1,392 = 20,514 pre-v5 records.
- Added completed 800-record dual-review and 200-record challenge validation, including R1/R2 agreement recomputation and human-adjudication rules.
- Enforced separation of `HUM_ADJ01` adjudication fields from deterministic `post_review_*` audit fields.
- Added standard-library CSV/XLSX semantic comparison and fresh reconstruction of all eight `OVERLAP_AUDIT` comparisons.
- Verified that final QA exclusions are absent from the main table and present in the cumulative exclusion audit.
- Added record-level checks that all 58 media/group, 20 unit, 56 canonical-value, 17 fecal limit-unit, 38 censored-compliance, and 8 arsenic normalization audit outcomes are applied.
- Added regression checks for heavy-metal media/unit consistency, reviewed parameter–unit anomalies, censored-pass ambiguity, multi-media pollutant dictionary entries, schema coverage, controlled vocabularies, column hashes, table-row-count semantics, and rebuilt figures.
- Reworked the QA summarizer to reject incomplete/inconsistent inputs and report human review, human adjudication, deterministic audit, and final actions separately.
- Removed the obsolete v4 release-candidate builder. Public code cannot reproduce private source-report review decisions.

## Exact target artifacts

- v5 archive (local/downloaded filename may differ): `48fda91a5dca95c30b5f95e32c1d026410655b38aaad577ef92561ce495f940d`
- `measurements_long_curated_public.csv`: `1710733cb527d4241ff8fdeef27ac94a3351393d8621d32a405a02822f91f688`
- `public_dataset_manifest.csv`: `7f4c51c5faeee50c1b6ebb86eae99b6aa157e3a29855fce1b3feb7825044a0cd`

## DOI status

The associated v5 data-version DOI is `10.5281/zenodo.21333262`. The previous code DOI `10.5281/zenodo.21252350` is version `1.0.0` for corrected-v3. Publish `1.1.0` as a new version under code concept DOI `10.5281/zenodo.21252349`. The new software version DOI remains unassigned and must be added only after Zenodo assigns it.
## Final validation

The final cross-platform data ZIP passed the integrated `all` workflow with exit code `0`, and all `29` automated tests passed on Linux/Python 3.13.5. See `docs/local_validation_note.md` for the exact hashes and run metrics.

