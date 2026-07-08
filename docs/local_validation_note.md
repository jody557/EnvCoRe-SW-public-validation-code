# Local validation note

This code package was tested locally against the final corrected v3 public data ZIP on 2026-07-07.

Data ZIP tested:

`EnvCoRe-SW_public_release_corrected_v3_20260705.zip`

Data ZIP SHA-256:

`ada5e6ac419fdcaa2488eedf67d220632354115fbf71ef8f872832180f6102a3`

Data ZIP MD5:

`763f3a37618a3c72e61df9a82b8b1361`

Command used:

```bash
python scripts/envcore_sw_public_release_tools.py all --release EnvCoRe-SW_public_release_corrected_v3_20260705.zip --out outputs/reproducibility_check --clean
```

Result:

`Validation status: PASS`
