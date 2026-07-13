# Zenodo code update instructions

These instructions prepare a code archive; they do not publish Zenodo records automatically.

1. Validate the exact corrected data ZIP and run the full test suite from the final code commit.
2. Create software version `1.1.1` as a **new version** under code concept DOI `10.5281/zenodo.21252349`.
3. Use `10.5281/zenodo.21338722` (`1.1.0`) as the immediately preceding software version. Do not overwrite or delete the existing GitHub `v1.1.0` tag/release.
4. Create the GitHub `v1.1.1` tag/release from the exact validated commit.
5. Copy `zenodo_code_metadata_template.json` to a separate submission file. Fill `metadata.publication_date` with the actual `YYYY-MM-DD` publication date.
6. Confirm the related dataset identifier is `10.5281/zenodo.21339244` with relation `isSupplementTo`.
7. Confirm the pinned data ZIP SHA-256 is `36e0bda4a4ffe47427892d88a8ecf7fcfece3e9ef70aa3a2cfff658fa2c4cd9b` and the manifest SHA-256 is `8aadd4ff20d97676737f2406dce7b1ca42be6d75ae43a7c41f5c4db0b35745e4`.
8. After Zenodo assigns the software version DOI, add it to the dataset record `10.5281/zenodo.21339244` as `isSupplementedBy`.
9. Do not create a circular follow-up release merely to insert the newly assigned software DOI into the already immutable tagged source archive. The Zenodo record itself supplies the canonical DOI.
