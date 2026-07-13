# Local validation note

Software candidate `1.1.0` targets the final cross-platform EnvCoRe-SW v5 ZIP after all v5.5 corrections. The local/downloaded ZIP filename may differ; the hashes below identify the artifact.

- Validation date: 2026-07-13
- Reserved data-version DOI: `10.5281/zenodo.21333262`
- Target ZIP SHA-256: `48fda91a5dca95c30b5f95e32c1d026410655b38aaad577ef92561ce495f940d`
- Main-table SHA-256: `1710733cb527d4241ff8fdeef27ac94a3351393d8621d32a405a02822f91f688`
- Manifest SHA-256: `7f4c51c5faeee50c1b6ebb86eae99b6aa157e3a29855fce1b3feb7825044a0cd`
- Python: `3.13.5`
- Operating system: Linux x86_64

Integrated command:

```bash
python scripts/envcore_sw_public_release_tools.py \
  --config config/release_config.yaml \
  all \
  --release path/to/EnvCoRe-SW_public_release_v5.zip \
  --out outputs/reproducibility_check \
  --clean
```

Observed integrated result against the exact cross-platform ZIP:

- validation status: `PASS`
- process exit code: `0`
- elapsed wall time: `32.67` seconds
- maximum resident set size: `378688 KiB`
- generated `validation_report.json` SHA-256: `02d845d26b5de47c6cb8c2b242bc64588e79db1dc36ead5c408405aacc86f7a7`

Automated test command:

```bash
ENVCORE_RELEASE=path/to/EnvCoRe-SW_public_release_v5.zip \
python -m unittest discover -s tests -v
```

Observed test result:

- `29` tests passed
- process exit code: `0`
- elapsed wall time: `30.97` seconds
- maximum resident set size: `384764 KiB`

The software version DOI is intentionally omitted until Zenodo assigns the version-specific identifier for release `1.1.0`.
