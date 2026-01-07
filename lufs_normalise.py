#!/usr/bin/env python3

"""lufs_normalise.py

Writer CLI: applies gain to reach a target integrated loudness (LUFS) and writes a new file.

This is intentionally separate from lufs_analyse.py:
- lufs_analyse.py = read-only measurement/reporting
- lufs_normalise.py = normalization/rendering (writes audio)

Design goals:
- Safe defaults (no accidental overwrites)
- Predict/guard against clipping (sample peak)
- Best-effort true-peak guard when ffmpeg true peak is available
- Clear terminal report

Notes:
- Writer uses FFmpeg (ebur128) as the reference measurement.
- In --compare mode, we also compute python (pyloudnorm) integrated loudness via lufs_analyse.py for comparison.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, asdict
import json
import sys
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf

from bb_audio import load_audio_mono

from lufs_analyse import Ebur128Metrics, measure_ebu128_ffmpeg


# ----------------------------
# Small utilities
# ----------------------------

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def db_from_lin(x: float) -> float:
    if x <= 0.0:
        return float("-inf")
    return 20.0 * float(np.log10(x))


def lin_from_db(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def fmt_signed(x: float) -> str:
    return f"{x:+.2f}"


# ----------------------------
# Core logic
# ----------------------------

@dataclass
class NormaliseWarnings:
    short_audio_warning: Optional[str] = None
    true_peak_warn: bool = False


@dataclass
class NormaliseResult:
    file_path: str
    sr: int

    # Measurements
    integrated_lufs: float
    peak_dbfs: float
    true_peak_dbtp: Optional[float] = None

    # Compare (optional)
    integrated_lufs_python: Optional[float] = None
    integrated_lufs_ffmpeg: Optional[float] = None
    delta_ffmpeg_minus_python: Optional[float] = None

    # Target/apply
    target_lufs: float = -14.0
    tolerance_lu: float = 0.5
    delta_lu: Optional[float] = None
    status: Optional[str] = None

    suggested_gain_db: Optional[float] = None
    applied_gain_db: Optional[float] = None

    predicted_peak_dbfs: Optional[float] = None
    predicted_true_peak_dbtp: Optional[float] = None

    wrote_path: Optional[str] = None
    did_write: bool = False
    note: Optional[str] = None


def default_output_path(file_path: str) -> str:
    base = os.path.basename(file_path)
    stem, _ext = os.path.splitext(base)
    return os.path.join(os.path.dirname(file_path), f"targeted_{stem}.wav")


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Normalize audio to a target integrated loudness (LUFS) and write output."
    )

    p.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Audio file path (positional). If omitted, uses --file or defaults to test.wav.",
    )
    p.add_argument("--file", default="test.wav",
                   help="Audio file path (default: test.wav).")

    p.add_argument(
        "--engine",
        choices=["ffmpeg"],
        default="ffmpeg",
        help="Measurement engine (default: ffmpeg). FFmpeg is the reference implementation.",
    )
    p.add_argument(
        "--compare",
        action="store_true",
        help="Measure both engines and use ffmpeg integrated as reference.",
    )

    p.add_argument(
        "--target_lufs",
        type=float,
        default=-14.0,
        help="Target integrated loudness in LUFS (default: -14.0).",
    )
    p.add_argument(
        "--tolerance",
        type=float,
        default=0.5,
        help="Tolerance in LU for compliance (default: 0.5).",
    )

    p.add_argument(
        "--output",
        default=None,
        help="Output file path (default: targeted_<input>.wav).",
    )

    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )

    p.add_argument(
        "--min_gain_db",
        type=float,
        default=-24.0,
        help="Minimum gain change in dB (default: -24.0).",
    )
    p.add_argument(
        "--max_gain_db",
        type=float,
        default=12.0,
        help="Maximum gain change in dB (default: +12.0).",
    )

    p.add_argument(
        "--true_peak_limit",
        type=float,
        default=-1.0,
        help="Warn if predicted true peak exceeds this dBTP (default: -1.0).",
    )

    p.add_argument(
        "--allow_clip",
        action="store_true",
        help="Allow writing even if predicted sample peak exceeds 0 dBFS.",
    )

    p.add_argument(
        "--force",
        action="store_true",
        help="Write output even if already within tolerance.",
    )

    p.add_argument(
        "--dry_run",
        action="store_true",
        help="Print what would be written without creating a file.",
    )

    p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON to stdout instead of the human report.",
    )
    p.add_argument(
        "--json_pretty",
        action="store_true",
        help="Pretty-print JSON (implies --json).",
    )
    return p.parse_args(argv)


def resolve_file_path(args: argparse.Namespace) -> str:
    return args.path if args.path is not None else args.file


def build_warnings(duration_sec: float) -> NormaliseWarnings:
    """Build NormaliseWarnings consistently."""
    warn = NormaliseWarnings()
    if duration_sec < 3.0:
        warn.short_audio_warning = "Audio shorter than 3 seconds; LUFS may be unreliable."
    return warn


def measure_lufs(
    file_path: str,
    audio: np.ndarray,
    sr: int,
    compare: bool,
) -> Tuple[float, Optional[float], Optional[float], Optional[float], Optional[Ebur128Metrics]]:
    """Return (integrated_ref, lufs_py, lufs_ff, delta_ff_minus_py, ff_metrics)."""

    ff_metrics: Optional[Ebur128Metrics] = None

    if compare:
        from lufs_analyse import measure_integrated_lufs_python
        try:
            lufs_py = measure_integrated_lufs_python(audio, sr)
        except RuntimeError as e:
            raise RuntimeError(
                "--compare requires 'pyloudnorm'. Install it with: pip install pyloudnorm"
            ) from e
        ff_metrics = measure_ebu128_ffmpeg(file_path, audio=audio, sr=sr)
        lufs_ff = ff_metrics.integrated_lufs
        delta = float(lufs_ff - lufs_py)
        return float(lufs_ff), float(lufs_py), float(lufs_ff), delta, ff_metrics

    ff_metrics = measure_ebu128_ffmpeg(file_path, audio=audio, sr=sr)
    return float(ff_metrics.integrated_lufs), None, float(ff_metrics.integrated_lufs), None, ff_metrics


def _round_floats(obj, ndigits: int = 3):
    """Recursively round floats in JSON payloads for stability/readability."""
    if isinstance(obj, float):
        if not np.isfinite(obj):
            return "-inf" if obj < 0 else "inf"
        v = round(obj, ndigits)
        # Normalize -0.0 -> 0.0 for cleaner JSON
        if v == 0.0:
            return 0.0
        return v
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(v, ndigits) for v in obj]
    return obj


def compute_gain_db(current_lufs: float, target_lufs: float, min_gain_db: float, max_gain_db: float) -> float:
    raw = -(current_lufs - target_lufs)
    return clamp(raw, min_gain_db, max_gain_db)


def print_report(res: NormaliseResult, warn: NormaliseWarnings, args: argparse.Namespace) -> None:
    print("=" * 44)
    print(" Blue Byte LUFS Normalise ")
    print("=" * 44)

    print(f"File:              {res.file_path}")
    print(f"Sample Rate:       {res.sr} Hz")
    engine_label = "compare" if args.compare else str(args.engine)
    ref_tag = " (reference)" if engine_label == "ffmpeg" else ""
    print(f"Engine:            {engine_label}{ref_tag}")

    if warn.short_audio_warning:
        print(f"Warning:           {warn.short_audio_warning}")

    if args.compare:
        assert res.integrated_lufs_python is not None
        assert res.integrated_lufs_ffmpeg is not None
        assert res.delta_ffmpeg_minus_python is not None
        print(f"Integrated (python): {res.integrated_lufs_python:.2f} LUFS")
        print(f"Integrated (ffmpeg): {res.integrated_lufs_ffmpeg:.2f} LUFS")
        print(f"Delta (ff-py):       {res.delta_ffmpeg_minus_python:+.2f} LU")
        print("Reference:           ffmpeg integrated")
    else:
        if np.isfinite(res.integrated_lufs):
            print(f"Integrated LUFS:     {res.integrated_lufs:.2f} LUFS")
        else:
            print("Integrated LUFS:     -inf (silence)")

    if np.isfinite(res.peak_dbfs):
        print(f"Peak (in):           {res.peak_dbfs:.2f} dBFS")
    else:
        print("Peak (in):           -inf dBFS")

    if res.true_peak_dbtp is not None:
        print(f"True Peak (in):      {res.true_peak_dbtp:.2f} dBTP")

    print("-" * 44)

    print(f"Target LUFS:         {res.target_lufs:.2f} LUFS")
    print(f"Tolerance:           ±{res.tolerance_lu:.2f} LU")

    if res.delta_lu is not None:
        print(f"Delta:               {fmt_signed(res.delta_lu)} LU")
    if res.status:
        print(f"Status:              {res.status}")

    if res.suggested_gain_db is not None:
        print(f"Suggested gain:      {fmt_signed(res.suggested_gain_db)} dB")

    if res.applied_gain_db is not None:
        print(f"Applied gain:        {fmt_signed(res.applied_gain_db)} dB")

    if res.predicted_peak_dbfs is not None:
        print(f"Pred. Peak (out):    {res.predicted_peak_dbfs:.2f} dBFS")

    if res.predicted_true_peak_dbtp is not None:
        tp_warn = " ⚠" if warn.true_peak_warn else ""
        print(
            f"Pred. True Peak:     {res.predicted_true_peak_dbtp:.2f} dBTP{tp_warn}")

    if args.dry_run:
        print("Dry run:             True")

    if res.wrote_path:
        if args.dry_run:
            print(f"Would write:         {res.wrote_path}")
        else:
            print(f"Wrote file:          {res.wrote_path}")

    if res.note:
        print(f"Note:               {res.note}")

    print("=" * 44)


def emit_json(res: NormaliseResult, warn: NormaliseWarnings, args: argparse.Namespace) -> None:
    payload = asdict(res)
    payload["mode"] = "normalise"
    payload["engine"] = "compare" if args.compare else str(args.engine)
    payload["warnings"] = asdict(warn)
    payload["dry_run"] = bool(args.dry_run)

    payload["schema"] = "bb.lufs.normalise.v1"

    # Prune python-only fields unless we're explicitly comparing.
    if not args.compare:
        for k in [
            "integrated_lufs_python",
            "delta_ffmpeg_minus_python",
        ]:
            payload.pop(k, None)

    payload = _round_floats(payload, ndigits=3)

    if args.json_pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def main(argv=None) -> int:
    args = parse_args(argv)
    # Convenience: --json_pretty implies --json
    if args.json_pretty:
        args.json = True
    file_path = resolve_file_path(args)

    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.", file=sys.stderr)
        return 1

    audio, sr = load_audio_mono(file_path)
    audio = np.asarray(audio, dtype=np.float64)

    duration_sec = float(len(audio) / sr) if sr > 0 else 0.0
    warn = build_warnings(duration_sec)

    peak_lin = float(np.max(np.abs(audio))) if audio.size else 0.0
    peak_dbfs = db_from_lin(peak_lin)

    # Silence: nothing to normalise
    if peak_lin == 0.0:
        res = NormaliseResult(
            file_path=file_path,
            sr=sr,
            integrated_lufs=float("-inf"),
            peak_dbfs=float("-inf"),
            target_lufs=float(args.target_lufs),
            tolerance_lu=float(args.tolerance),
            delta_lu=None,
            status="⚠ Silence",
            suggested_gain_db=None,
            applied_gain_db=None,
            wrote_path=args.output if args.output else default_output_path(
                file_path),
            note="Silence detected; no output written.",
        )
        if args.json:
            emit_json(res, warn, args)
            return 0
        print_report(res, warn, args)
        return 0

    # Measure loudness
    try:
        integrated_ref, lufs_py, lufs_ff, delta, ff_metrics = measure_lufs(
            file_path=file_path,
            audio=audio,
            sr=sr,
            compare=bool(args.compare),
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # True peak: available only when ffmpeg ran (compare or ffmpeg engine)
    tp_in = ff_metrics.true_peak_dbtp if ff_metrics is not None else None

    target = float(args.target_lufs)
    tol = float(args.tolerance)

    delta_lu = float(integrated_ref - target)
    within = abs(delta_lu) <= tol

    suggested_gain_db = -delta_lu

    status: str
    if within:
        status = "✅ Within tolerance"
    else:
        status = "⬆ Too loud" if delta_lu > 0 else "⬇ Too quiet"

    # If already compliant and not forced, do not write
    out_path = args.output if args.output else default_output_path(file_path)

    res = NormaliseResult(
        file_path=file_path,
        sr=sr,
        integrated_lufs=float(integrated_ref),
        peak_dbfs=float(peak_dbfs),
        true_peak_dbtp=tp_in,
        integrated_lufs_python=lufs_py,
        integrated_lufs_ffmpeg=lufs_ff,
        delta_ffmpeg_minus_python=delta,
        target_lufs=target,
        tolerance_lu=tol,
        delta_lu=delta_lu,
        status=status,
        suggested_gain_db=float(suggested_gain_db),
        wrote_path=out_path,
    )

    if within and not args.force:
        res.note = "Already within tolerance; no output written. Use --force to write anyway."
        if args.json:
            emit_json(res, warn, args)
            return 0
        print_report(res, warn, args)
        return 0

    # Compute clamped gain
    gain_db = compute_gain_db(
        current_lufs=float(integrated_ref),
        target_lufs=target,
        min_gain_db=float(args.min_gain_db),
        max_gain_db=float(args.max_gain_db),
    )
    gain_lin = lin_from_db(gain_db)

    # Predict sample peak after gain
    pred_peak_dbfs = float(peak_dbfs + gain_db)
    res.applied_gain_db = float(gain_db)
    res.predicted_peak_dbfs = float(pred_peak_dbfs)

    # Predict true peak if we have it
    if tp_in is not None:
        pred_tp = float(tp_in + gain_db)
        res.predicted_true_peak_dbtp = pred_tp
        if pred_tp > float(args.true_peak_limit):
            warn.true_peak_warn = True

    # Safety: sample clipping
    if pred_peak_dbfs > 0.0 and not args.allow_clip:
        res.note = "Aborted: predicted sample peak exceeds 0 dBFS. Use --allow_clip to force write."
        if args.json:
            emit_json(res, warn, args)
            return 1
        print_report(res, warn, args)
        return 1

    if args.dry_run:
        if args.json:
            emit_json(res, warn, args)
            return 0
        print_report(res, warn, args)
        return 0

    # Overwrite safety (only when actually writing)
    # Treated as a successful run: analysis/predictions completed, write was intentionally skipped.
    if out_path and os.path.exists(out_path) and not args.overwrite:
        res.note = "Refusing to overwrite existing output. Use --overwrite to allow."
        if args.json:
            emit_json(res, warn, args)
            return 0
        print_report(res, warn, args)
        return 0

    # Apply gain and write
    out_audio = audio * gain_lin

    try:
        sf.write(out_path, out_audio, sr)
        res.did_write = True
    except Exception as e:
        res.note = f"Error writing output file: {e}"
        if args.json:
            emit_json(res, warn, args)
            return 1
        print_report(res, warn, args)
        return 1

    if args.json:
        emit_json(res, warn, args)
        return 0
    print_report(res, warn, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
