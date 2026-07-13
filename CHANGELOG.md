# Changelog

## 1.1.1 — 2026-07-13

- Corrected the associated dataset DOI from the deleted/tombstoned record `10.5281/zenodo.21333262` to the reserved v5 data DOI `10.5281/zenodo.21339244`.
- Rebuilt and re-pinned the cross-platform dataset ZIP (`36e0bda4a4ffe47427892d88a8ecf7fcfece3e9ef70aa3a2cfff658fa2c4cd9b`) and manifest (`8aadd4ff20d97676737f2406dce7b1ca42be6d75ae43a7c41f5c4db0b35745e4`).
- Clarified the controlled-vocabulary cleanup history by distinguishing the 285-row post-cleanup state from the 286-row current v5.5-regenerated table.
- Kept the curated main-table hash unchanged.
- Updated software continuity so `1.1.1` follows archived software DOI `10.5281/zenodo.21338722` under concept DOI `10.5281/zenodo.21252349`.
- Updated GitHub/Zenodo release instructions and removed circular software-DOI insertion requirements.

## 1.1.0 — 2026-07-13 (superseded)

- Superseded by `1.1.1` because `10.5281/zenodo.21333262` was a deleted Zenodo record, not the dataset DOI.

- Aligned all paths, counts, hashes, QA logic, tests, and release metadata with the EnvCoRe-SW v5 package after v5.5 corrections.
- Added exact-ZIP validation and comprehensive v5/v5.5 correction regressions.
- Added completed dual-review/challenge QA, adjudication-stage separation, CSV/XLSX, and overlap-audit verification.
- Added exact active-schema, controlled-vocabulary, table-row semantics, summary, column-hash, and figure rebuild checks.
- Removed the obsolete v4 data-package builder and updated Zenodo release-continuity materials.
- Made manifest reproducibility independent of row order and changed disclosure scanning to bounded-memory streaming.
- Reported degenerate Cohen's kappa as not estimable, added Python 3.9 compatibility, modular tests, synthetic helper tests, and GitHub Actions.
- Removed invalid DOI placeholders from machine-readable citation metadata and renamed Zenodo/BibTeX drafts as explicit non-submittable templates.
- Hardened deterministic source packaging so generated outputs, interpreter caches, coverage files, and local Git metadata cannot leak into the public ZIP.
- Made manifest comparison fully multiset/order independent and made the QA kappa helper reject unequal reviewer-vector lengths.
- Added sentinel-based `all --clean` ownership checks so the validator cannot recursively delete an arbitrary user directory, its own repository, or the release being validated.
- Kept DOI regression tests compatible with later insertion of real assigned identifiers while continuing to reject placeholders.
- Corrected both Zenodo JSON templates to the documented deposition API shape (`upload_type`, string `license`, and two-field related identifiers) and removed misleading links to incompatible prior code/data versions.
- Made source packaging use only Git-tracked working-tree files in a checkout; archive-only sources are constrained by an exact public-file allowlist so credentials or private notes cannot leak.

## 1.0.0 — 2026-07-08

- Initial public validation and figure-generation code release for the corrected-v3 data version.
### Final data-DOI and cross-platform archive alignment

- Pinned software `1.1.0` to the final cross-platform data archive SHA-256 `48fda91a5dca95c30b5f95e32c1d026410655b38aaad577ef92561ce495f940d`.
- Updated the embedded manifest SHA-256 to `7f4c51c5faeee50c1b6ebb86eae99b6aa157e3a29855fce1b3feb7825044a0cd`.
- Recorded reserved data-version DOI `10.5281/zenodo.21333262`.
- Made source ZIP path ordering deterministic across Windows and POSIX systems.

