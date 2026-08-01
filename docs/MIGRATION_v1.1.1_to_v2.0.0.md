# Migration from v1.1.1 to v2.0.0

Version `2.0.0` is not a drop-in replacement for `v1.1.1`.

## Command-line interface

The legacy `v1.1.1` multi-command interface is replaced by:

```bash
python scripts/validate_release.py --release <public-payload.zip-or-directory> --out <output-directory>
```

The following legacy functions are not part of the `v2.0.0` public interface:

- `all`
- `summary`
- `figures`
- `manifest`
- dual-review summarization

## Configuration

The legacy YAML configuration is replaced by:

```text
config/release_config.json
```

Automation must pass the JSON configuration with `--config` only when overriding the default.

## Validation target

The default command validates the 19-file public payload. For a 24-file candidate QA package, add `--config config/release_candidate_config.json`.

`v1.1.1` targeted the older 19,122-record v5 package. `v2.0.0` targets the Stage 6D-R2 public-data contract:

- 20,023 measurements;
- 8,259 inventory records;
- 122 controlled-vocabulary rows;
- 24 candidate files;
- 19 public payload files.

## Outputs

The validator writes:

- `validation_report.json`
- `validation_report.md`

Scripts that consumed legacy summaries or figure-source outputs must be updated.

## Reproducibility boundary

This software validates the public candidate structure and aggregate validation products. It does not reconstruct private source-evidence judgments, reviewer decisions, or adjudication ledgers.
