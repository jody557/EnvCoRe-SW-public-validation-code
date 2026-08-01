# Zenodo preparation

`zenodo_code_metadata_template.json` is a preparation template, not a ready-to-submit API payload. Before submission:

1. confirm the creator list and order, title, description, publication date, and MIT license against the repository owners' authoritative metadata;
2. do not add affiliations or ORCIDs unless they are separately confirmed by the creators;
3. create version `2.0.0` under code concept DOI `10.5281/zenodo.21252349` as a new version of `10.5281/zenodo.21340470`;
4. let Zenodo assign the new version-specific code DOI; never reuse the preceding DOI;
5. add an `isSupplementTo` relation only after the associated new dataset-version DOI has been assigned and verified;
6. upload the deterministic source ZIP and record its SHA-256 in the release notes.

Do not use `10.5281/zenodo.21339244` as the code DOI. It is a dataset record.
