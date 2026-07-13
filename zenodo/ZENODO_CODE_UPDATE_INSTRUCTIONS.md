# Zenodo code update instructions

These instructions prepare a code archive; they do not publish Zenodo records automatically.

1. Validate the exact data ZIP and run the full test suite from the final code commit.
2. Create software version `1.1.0` as a **new version** under code concept DOI `10.5281/zenodo.21252349`; the previous version DOI is `10.5281/zenodo.21252350` (`1.0.0`, corrected-v3 only).
3. Create the GitHub `v1.1.0` tag/release from that exact validated commit; do not overwrite `v1.0.0`.
4. Copy `zenodo_code_metadata_template.json` to a separate submission file. Its `metadata` object follows the Zenodo legacy deposit API schema; the template is intentionally rejected until the required null publication date is filled.
5. Fill `metadata.publication_date` with the actual `YYYY-MM-DD` publication date. Do not add unassigned DOI placeholders.
6. Add the assigned v5 data-version DOI to `metadata.related_identifiers` with relation `isSupplementTo`. The pinned data ZIP SHA-256 must remain `48fda91a5dca95c30b5f95e32c1d026410655b38aaad577ef92561ce495f940d`.
7. After Zenodo assigns the code-version DOI, add it to `CITATION.cff`, README, config, release linkage, citation template, and version mapping, then rerun tests.
