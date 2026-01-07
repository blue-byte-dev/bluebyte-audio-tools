# Blue Byte LUFS JSON Schemas

This document defines the **stable, versioned JSON contracts** emitted by the
Blue Byte LUFS command-line tools.

These schemas are intended for:
- automation pipelines
- batch processing
- CI / QA checks
- downstream tools that must not break on upgrades

All schemas are **additive-only**.  
Removing or renaming fields requires a new schema version.

---

## Common Principles

- **FFmpeg is the reference loudness engine**
- Python (`pyloudnorm`) is approximate and optional
- JSON output is deterministic and rounded for stability
- Safety refusals (overwrite, within tolerance) are **successful runs**
- Errors are reserved for actual failures (invalid input, missing dependencies, write failure)

---

# Schema: `bb.lufs.analyse.v1`

Emitted by: `lufs_analyse.py`

Purpose:
- Measurement only
- Never writes audio
- Safe to run in any environment

---

## Common Fields (all engines)

| Field | Type | Description |
|-----|-----|-------------|
| `schema` | string | Always `"bb.lufs.analyse.v1"` |
| `mode` | string | Always `"analyse"` |
| `engine` | string | `"ffmpeg"`, `"python"`, or `"compare"` |
| `file_path` | string | Input file path |
| `sr` | number | Sample rate (Hz) |
| `duration_sec` | number | Duration in seconds |
| `peak_dbfs` | number | Sample peak in dBFS |
| `integrated_lufs` | number | Reference integrated LUFS |
| `warnings` | object | Warning flags/messages |

### `warnings`

| Field | Type | Meaning |
|-----|-----|---------|
| `short_audio_warning` | string \| null | Audio shorter than ~3s |
| `engine_warning` | string \| null | Python engine disclaimer |

---

## Engine: `ffmpeg` (reference)

Additional guaranteed fields:

| Field | Type |
|-----|-----|
| `integrated_lufs_ffmpeg` | number |
| `momentary_max_ffmpeg` | number \| null |
| `shortterm_max_ffmpeg` | number \| null |
| `loudness_range_lu` | number \| null |
| `true_peak_dbtp` | number \| null |
| `ffmpeg_measurement_basis` | string |

Notes:
- Measurement basis is currently `"mono_samples"`
- Momentary / short-term values may be null if not available

---

## Engine: `python` (approximate)

Additional guaranteed fields:

| Field | Type |
|-----|-----|
| `integrated_lufs_python` | number |
| `momentary_max_python` | number \| null |
| `shortterm_max_python` | number \| null |

Notes:
- Requires `pyloudnorm`
- If missing, the tool exits with a clean error
- `engine_warning` is always populated in this mode

---

## Engine: `compare`

Includes **both engines** and their delta:

| Field | Type |
|-----|-----|
| `integrated_lufs_ffmpeg` | number |
| `integrated_lufs_python` | number |
| `delta_ffmpeg_minus_python` | number |
| `momentary_max_ffmpeg` | number \| null |
| `momentary_max_python` | number \| null |
| `shortterm_max_ffmpeg` | number \| null |
| `shortterm_max_python` | number \| null |
| `loudness_range_lu` | number \| null |
| `true_peak_dbtp` | number \| null |

---

# Schema: `bb.lufs.normalise.v1`

Emitted by: `lufs_normalise.py`

Purpose:
- Policy + rendering
- May write audio
- Designed for automation

---

## Common Fields

| Field | Type | Description |
|-----|-----|-------------|
| `schema` | string | Always `"bb.lufs.normalise.v1"` |
| `mode` | string | Always `"normalise"` |
| `engine` | string | `"ffmpeg"` or `"compare"` |
| `file_path` | string | Input file path |
| `sr` | number | Sample rate (Hz) |
| `integrated_lufs` | number | Reference integrated LUFS |
| `peak_dbfs` | number | Input sample peak |
| `true_peak_dbtp` | number \| null | Input true peak |
| `target_lufs` | number | Target loudness |
| `tolerance_lu` | number | Allowed tolerance |
| `delta_lu` | number | Difference from target |
| `status` | string | Human-readable state |
| `warnings` | object | Warning flags |
| `schema` | string | Schema identifier |

---

## Write Semantics

| Field | Type | Meaning |
|-----|-----|---------|
| `dry_run` | boolean | User passed `--dry_run` |
| `did_write` | boolean | File was actually written |
| `wrote_path` | string \| null | Intended output path |
| `note` | string \| null | Explanation when not written |

Key rule:
- **`dry_run` ≠ `did_write`**
- Overwrite refusal, within-tolerance, and dry-run are **successful runs**

---

## Prediction Fields

| Field | Type |
|-----|-----|
| `suggested_gain_db` | number |
| `applied_gain_db` | number |
| `predicted_peak_dbfs` | number |
| `predicted_true_peak_dbtp` | number \| null |

---

## Compare Mode (`--compare`)

Additional fields:

| Field | Type |
|-----|-----|
| `integrated_lufs_python` | number |
| `integrated_lufs_ffmpeg` | number |
| `delta_ffmpeg_minus_python` | number |

FFmpeg is always the reference for gain application.

---

## Exit Code Semantics

| Exit Code | Meaning |
|---------|---------|
| `0` | Successful run (even if nothing written) |
| `1` | Error (invalid input, missing dependency, write failure, hard safety abort) |

---

## Versioning Policy

- New fields → same schema version
- Renamed / removed fields → **new schema version**
- Existing fields will never change meaning within a version

---

_End of schema_