# Local validation note

Software candidate `1.1.1` targets the corrected, cross-platform EnvCoRe-SW v5 ZIP after all v5.5 corrections and the dataset DOI correction. The local/downloaded ZIP filename may differ; the hashes below identify the artifact.

- Validation date: 2026-07-13
- Reserved data-version DOI: `10.5281/zenodo.21339244`
- Target ZIP SHA-256: `36e0bda4a4ffe47427892d88a8ecf7fcfece3e9ef70aa3a2cfff658fa2c4cd9b`
- Main-table SHA-256: `1710733cb527d4241ff8fdeef27ac94a3351393d8621d32a405a02822f91f688`
- Manifest SHA-256: `8aadd4ff20d97676737f2406dce7b1ca42be6d75ae43a7c41f5c4db0b35745e4`
- Python: `3.13.5`
- Operating system: `Linux x86_64`

Integrated command:

```bash
python scripts/envcore_sw_public_release_tools.py \
  --config config/release_config.yaml \
  all \
  --release path/to/EnvCoRe-SW_public_release_v5.zip \
  --out outputs/reproducibility_check \
  --clean
```

Observed integrated result against the exact corrected cross-platform ZIP:

- validation status: `PASS`
- process exit code: `0`
- elapsed wall time: `31.93` seconds
- maximum resident set size: `395392 KiB`
- generated `validation_report.json` SHA-256: `b8cff235c4e86bf6de489364612b9201ec0a9d164bbb3f352260d605e400a5ee`

Automated test command:

```bash
ENVCORE_RELEASE=path/to/EnvCoRe-SW_public_release_v5.zip \
python -m unittest discover -s tests -v
```

Observed test result:

- `29` tests passed
- process exit code: `0`
- elapsed wall time: `31.75` seconds
- maximum resident set size: `387984 KiB`

The software version DOI is intentionally omitted from the immutable candidate archive because Zenodo assigns it only after GitHub release `v1.1.1` is archived. The assigned software DOI should then be linked from dataset record `10.5281/zenodo.21339244`.
