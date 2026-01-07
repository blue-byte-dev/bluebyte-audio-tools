
import argparse
import os
import re
import subprocess
import json
import tempfile
import soundfile as sf
import sys
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np

from bb_audio import load_audio_mono


# ----------------------------
# Small utilities
# ----------------------------
# NOTE: This script is analysis-only (read-only). It never writes audio.
# Normalization/rendering should live in a separate writer CLI (e.g., lufs_normalise.py).

def db_from_lin(x: float) -> float:
    if x <= 0.0:
        return float("-inf")
    return 20.0 * float(np.log10(x))


# ----------------------------
# FFmpeg EBU R128 parsing
# ----------------------------

@dataclass
class Ebur128Metrics:
    integrated_lufs: float
    loudness_range_lu: Optional[float]
    momentary_max_lufs: Optional[float]
    shortterm_max_lufs: Optional[float]
    true_peak_dbtp: Optional[float]
    measurement_basis: str  # "file" or "mono_samples"


def _max_above_floor(values: list[str], floor: float = -70.0) -> Optional[float]:
    best: Optional[float] = None
    for v in values:
        if v == "nan":
            continue
        fv = float(v)
        if fv <= floor:
            continue
        if best is None or fv > best:
            best = fv
    return best


def measure_ebu128_ffmpeg(
    path: str,
    *,
    audio: Optional[np.ndarray] = None,
    sr: Optional[int] = None,
) -> Ebur128Metrics:
    """Measure EBU R128 metrics via FFmpeg `ebur128=peak=true` (optionally using provided mono samples).

    Returns integrated LUFS + offline stats derived from running meter output:
    - momentary_max_lufs: max M values above the -70 LUFS floor
    - shortterm_max_lufs: max S values above the -70 LUFS floor
    - loudness_range_lu: from Summary block if present
    - true_peak_dbtp: parsed if present (varies by build)

    Note: momentary/short-term are OFFLINE maxima from the run; this CLI is not
    a real-time meter.
    """
    # If mono samples are provided, run FFmpeg on a temp mono WAV so python vs ffmpeg
    # comparisons use identical input samples (avoids downmix coefficient differences).
    tmp_path: Optional[str] = None
    input_path = path
    basis = "file"

    if audio is not None and sr is not None:
        basis = "mono_samples"
        mono = np.asarray(audio, dtype=np.float64).reshape(-1)
        fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="bb_mono_")
        os.close(fd)
        sf.write(tmp_path, mono, int(sr))
        input_path = tmp_path

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        input_path,
        "-filter_complex",
        "ebur128=peak=true",
        "-f",
        "null",
        "-",
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except FileNotFoundError as e:
        raise RuntimeError("ffmpeg not found on system.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError("ffmpeg failed to analyse audio.") from e
    finally:
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    stderr = result.stderr

    # Prefer parsing from the final Summary block to avoid any -70 LUFS floor artifacts.
    summary_idx = stderr.rfind("Summary:")
    parse_text = stderr[summary_idx:] if summary_idx != -1 else stderr

    def summary_value(tag: str) -> Optional[float]:
        m = re.search(
            rf"(?m)^\s*{re.escape(tag)}:\s*(-?\d+(?:\.\d+)?)\s*(?:LUFS|LU|dBTP)\s*$",
            parse_text,
        )
        return float(m.group(1)) if m else None

    integrated = summary_value("I")
    lra = summary_value("LRA")

    # Fallback for integrated if Summary isn't present/parsable
    if integrated is None:
        matches_all = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", stderr)
        if matches_all:
            integrated = float(matches_all[-1])

    # Offline maxima for M and S from running lines
    m_vals = re.findall(r"M:\s*(-?\d+(?:\.\d+)?|nan)\b", stderr)
    s_vals = re.findall(r"S:\s*(-?\d+(?:\.\d+)?|nan)\b", stderr)
    m_max = _max_above_floor(m_vals)
    s_max = _max_above_floor(s_vals)

    # True peak parsing is inconsistent across FFmpeg builds; attempt multiple strategies.
    tp = summary_value("TP")
    if tp is None:
        tp_all = re.findall(r"TP:\s*(-?\d+(?:\.\d+)?)\s*dBTP", stderr)
        if tp_all:
            tp = float(tp_all[-1])

    if tp is None:
        block_m = re.search(
            r"True\s+peak:\s*(?:\r?\n)+(?P<block>(?:.*\r?\n){0,25})",
            stderr,
            flags=re.IGNORECASE,
        )
        if block_m:
            block = block_m.group("block")
            m_db = re.search(r"(-?\d+(?:\.\d+)?)\s*dBTP\b",
                             block, flags=re.IGNORECASE)
            if m_db:
                tp = float(m_db.group(1))
            else:
                m_peak = re.search(
                    r"(?im)^\s*Peak:\s*(-?\d+(?:\.\d+)?)\s*(?:dBTP|dBFS)?\s*$",
                    block,
                )
                if m_peak:
                    tp = float(m_peak.group(1))

    if integrated is None:
        raise RuntimeError(
            "Could not parse final integrated LUFS from ffmpeg output.")

    return Ebur128Metrics(
        integrated_lufs=float(integrated),
        loudness_range_lu=lra,
        momentary_max_lufs=m_max,
        shortterm_max_lufs=s_max,
        true_peak_dbtp=tp,
        measurement_basis=basis,
    )


# ----------------------------
# Python-side loudness
# ----------------------------

def measure_integrated_lufs_python(audio: np.ndarray, sr: int) -> float:
    """Integrated LUFS using pyloudnorm (ITU-R BS.1770 / EBU R128 style)."""
    try:
        import pyloudnorm as pyln
    except ImportError as e:
        raise RuntimeError(
            "Python loudness engine requires 'pyloudnorm'. Install it with: pip install pyloudnorm"
        ) from e

    meter = pyln.Meter(sr)
    return float(meter.integrated_loudness(audio))


def windowed_lufs_max_python(
    audio: np.ndarray,
    sr: int,
    window_sec: float,
    step_sec: float,
) -> Optional[float]:
    """Offline approximation of max loudness over time.

    Uses pyloudnorm's integrated loudness per window.
    - window_sec = 0.4 approximates "momentary"
    - window_sec = 3.0 approximates "short-term"

    Returns max LUFS across windows, or None if not computable.
    """
    if sr <= 0:
        return None

    win_n = int(round(window_sec * sr))
    step_n = int(round(step_sec * sr))

    if win_n <= 0 or step_n <= 0:
        return None
    if audio.size < win_n:
        return None

    try:
        import pyloudnorm as pyln
    except ImportError as e:
        raise RuntimeError(
            "Python loudness engine requires 'pyloudnorm'. Install it with: pip install pyloudnorm"
        ) from e

    meter = pyln.Meter(sr)

    best: Optional[float] = None
    for start in range(0, audio.size - win_n + 1, step_n):
        chunk = audio[start: start + win_n]
        try:
            v = float(meter.integrated_loudness(chunk))
        except Exception:
            continue
        if not np.isfinite(v):
            continue
        if best is None or v > best:
            best = v

    return best


# ----------------------------
# CLI / Report
# ----------------------------

@dataclass
class AnalysisWarnings:
    short_audio_warning: Optional[str] = None
    engine_warning: Optional[str] = None


@dataclass
class AnalysisResult:
    file_path: str
    sr: int
    duration_sec: float
    peak_dbfs: float
    integrated_lufs: float

    # Optional extras
    momentary_max_lufs: Optional[float] = None
    shortterm_max_lufs: Optional[float] = None
    loudness_range_lu: Optional[float] = None
    true_peak_dbtp: Optional[float] = None
    ffmpeg_measurement_basis: Optional[str] = None

    # Compare mode
    integrated_lufs_python: Optional[float] = None
    integrated_lufs_ffmpeg: Optional[float] = None
    delta_ffmpeg_minus_python: Optional[float] = None
    momentary_max_python: Optional[float] = None
    shortterm_max_python: Optional[float] = None
    momentary_max_ffmpeg: Optional[float] = None
    shortterm_max_ffmpeg: Optional[float] = None


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure integrated LUFS and sample-peak (dBFS) for a single audio file."
    )

    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Audio file path (positional). If omitted, uses --file or defaults to test.wav.",
    )
    parser.add_argument(
        "--file",
        dest="file",
        default="test.wav",
        help="Audio file path (default: test.wav).",
    )

    parser.add_argument(
        "--engine",
        choices=["python", "ffmpeg"],
        default="ffmpeg",
        help="Loudness analysis engine (default: ffmpeg). FFmpeg is the reference implementation; python is approximate.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run both engines (python + ffmpeg) and print a delta.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON to stdout instead of the human report.",
    )
    parser.add_argument(
        "--json_pretty",
        action="store_true",
        help="Pretty-print JSON (implies --json).",
    )

    return parser.parse_args(argv)


def resolve_file_path(args: argparse.Namespace) -> str:
    return args.path if args.path is not None else args.file


def build_warnings(args: argparse.Namespace, duration_sec: float) -> AnalysisWarnings:
    """Build AnalysisWarnings consistently for both JSON and human reports."""
    warnings = AnalysisWarnings()

    if duration_sec < 3.0:
        warnings.short_audio_warning = (
            f"Very short audio ({duration_sec:.2f}s). LUFS/LRA may be unreliable."
        )

    if str(args.engine) == "python" and not bool(args.compare):
        warnings.engine_warning = (
            "Python loudness engine is approximate. FFmpeg is the reference engine "
            "and may differ from DAW / streaming-platform meters."
        )

    return warnings


def analyse_file(
    args: argparse.Namespace,
    audio: np.ndarray,
    sr: int,
) -> tuple[AnalysisResult, AnalysisWarnings] | tuple[None, None]:
    file_path = resolve_file_path(args)

    audio = np.asarray(audio, dtype=np.float64)

    duration_sec = float(audio.size) / float(sr) if sr else 0.0
    warnings = build_warnings(args, duration_sec)

    # Peak + silence check
    peak_lin = float(np.max(np.abs(audio)))
    if peak_lin == 0.0:
        # Silence path handled in main() for nice report output.
        peak_dbfs = float("-inf")
    else:
        peak_dbfs = db_from_lin(peak_lin)

    compare = bool(args.compare)

    # Compare mode: always run both engines and pick ffmpeg integrated as the target reference.
    if compare:
        try:
            lufs_py = measure_integrated_lufs_python(audio, sr)
            mmax_py = windowed_lufs_max_python(
                audio, sr, window_sec=0.4, step_sec=0.1)
            smax_py = windowed_lufs_max_python(
                audio, sr, window_sec=3.0, step_sec=0.5)
        except RuntimeError:
            return None, None

        ff = measure_ebu128_ffmpeg(file_path, audio=audio, sr=sr)

        lufs_ff = ff.integrated_lufs
        delta = lufs_ff - lufs_py

        # Reference integrated = ffmpeg integrated
        res = AnalysisResult(
            file_path=file_path,
            sr=sr,
            duration_sec=duration_sec,
            peak_dbfs=peak_dbfs,
            integrated_lufs=lufs_ff,
            integrated_lufs_python=lufs_py,
            integrated_lufs_ffmpeg=lufs_ff,
            delta_ffmpeg_minus_python=delta,
            momentary_max_python=mmax_py,
            shortterm_max_python=smax_py,
            momentary_max_ffmpeg=ff.momentary_max_lufs,
            shortterm_max_ffmpeg=ff.shortterm_max_lufs,
            loudness_range_lu=ff.loudness_range_lu,
            true_peak_dbtp=ff.true_peak_dbtp,
            ffmpeg_measurement_basis=ff.measurement_basis,
        )
        return res, warnings

    # Non-compare: run selected engine.
    engine = str(args.engine)
    if engine == "python":
        try:
            lufs_i = measure_integrated_lufs_python(audio, sr)
            mmax_py = windowed_lufs_max_python(
                audio, sr, window_sec=0.4, step_sec=0.1)
            smax_py = windowed_lufs_max_python(
                audio, sr, window_sec=3.0, step_sec=0.5)
        except RuntimeError:
            return None, None
        res = AnalysisResult(
            file_path=file_path,
            sr=sr,
            duration_sec=duration_sec,
            peak_dbfs=peak_dbfs,
            integrated_lufs=lufs_i,
            integrated_lufs_python=lufs_i,
            momentary_max_python=mmax_py,
            shortterm_max_python=smax_py,
        )
        return res, warnings

    # ffmpeg engine
    ff = measure_ebu128_ffmpeg(file_path, audio=audio, sr=sr)
    res = AnalysisResult(
        file_path=file_path,
        sr=sr,
        duration_sec=duration_sec,
        peak_dbfs=peak_dbfs,
        integrated_lufs=ff.integrated_lufs,
        integrated_lufs_ffmpeg=ff.integrated_lufs,
        # Canonical ffmpeg fields (schema v1)
        momentary_max_ffmpeg=ff.momentary_max_lufs,
        shortterm_max_ffmpeg=ff.shortterm_max_lufs,
        # Backward-compatible aliases for the human report (pruned from JSON)
        momentary_max_lufs=ff.momentary_max_lufs,
        shortterm_max_lufs=ff.shortterm_max_lufs,
        loudness_range_lu=ff.loudness_range_lu,
        true_peak_dbtp=ff.true_peak_dbtp,
        ffmpeg_measurement_basis=ff.measurement_basis,
    )
    return res, warnings


def print_report(result: AnalysisResult, warnings: AnalysisWarnings, args: argparse.Namespace) -> None:
    print("=" * 40)
    print(" Blue Byte LUFS Analysis ")
    print("=" * 40)

    print(f"File:            {result.file_path}")
    print(f"Sample Rate:     {result.sr} Hz")
    print(f"Duration:        {result.duration_sec:.2f} s")

    engine_label = "compare" if args.compare else str(args.engine)
    ref_tag = " (reference)" if engine_label == "ffmpeg" else ""
    if engine_label == "python":
        ref_tag = " (approx)"
    print(f"Engine:          {engine_label}{ref_tag}")

    if warnings.short_audio_warning:
        print(f"Warning:         {warnings.short_audio_warning}")

    if warnings.engine_warning:
        print(f"Warning:         {warnings.engine_warning}")

    if args.compare:
        assert result.integrated_lufs_python is not None
        assert result.integrated_lufs_ffmpeg is not None
        assert result.delta_ffmpeg_minus_python is not None

        print(
            f"Integrated LUFS (python): {result.integrated_lufs_python:.2f} LUFS")
        print(
            f"Integrated LUFS (ffmpeg): {result.integrated_lufs_ffmpeg:.2f} LUFS")
        print(
            f"Delta (ffmpeg - python):  {result.delta_ffmpeg_minus_python:+.2f} LU")

        if result.momentary_max_ffmpeg is not None:
            print(
                f"Momentary Max (ffmpeg):   {result.momentary_max_ffmpeg:.2f} LUFS")
        if result.shortterm_max_ffmpeg is not None:
            print(
                f"Short-term Max (ffmpeg):  {result.shortterm_max_ffmpeg:.2f} LUFS")

        if result.loudness_range_lu is not None:
            print(
                f"Loudness Range (ffmpeg):  {result.loudness_range_lu:.2f} LU")
        if result.true_peak_dbtp is not None:
            print(
                f"True Peak (ffmpeg):       {result.true_peak_dbtp:.2f} dBTP")

    else:
        if not np.isfinite(result.integrated_lufs):
            print("Integrated LUFS: -inf (silence)")
        else:
            print(f"Integrated LUFS: {result.integrated_lufs:.2f} LUFS")

        if args.engine == "python":
            if result.momentary_max_python is not None:
                print(
                    f"Momentary Max:   {result.momentary_max_python:.2f} LUFS")
            if result.shortterm_max_python is not None:
                print(
                    f"Short-term Max:  {result.shortterm_max_python:.2f} LUFS")

        if args.engine == "ffmpeg":
            if result.momentary_max_ffmpeg is not None:
                print(
                    f"Momentary Max:   {result.momentary_max_ffmpeg:.2f} LUFS")
            if result.shortterm_max_ffmpeg is not None:
                print(
                    f"Short-term Max:  {result.shortterm_max_ffmpeg:.2f} LUFS")
            if result.loudness_range_lu is not None:
                print(f"Loudness Range:  {result.loudness_range_lu:.2f} LU")
            if result.true_peak_dbtp is not None:
                print(f"True Peak:       {result.true_peak_dbtp:.2f} dBTP")

    # Peak always at end for consistency
    if np.isfinite(result.peak_dbfs):
        print(f"Peak:            {result.peak_dbfs:.2f} dBFS")
    else:
        print("Peak:            -inf dBFS")

    print("=" * 40)


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


def emit_json(result: AnalysisResult, warnings: AnalysisWarnings, args: argparse.Namespace) -> None:
    payload = asdict(result)
    payload["mode"] = "analyse"
    payload["engine"] = "compare" if args.compare else str(args.engine)
    payload["warnings"] = asdict(warnings)

    payload["schema"] = "bb.lufs.analyse.v1"

    # Schema v1 cleanup: remove deprecated alias fields (always)
    for k in [
        "momentary_max_lufs",
        "shortterm_max_lufs",
    ]:
        payload.pop(k, None)
    # Prune engine-specific fields unless we're explicitly comparing.
    if not args.compare:
        eng = str(args.engine)
        if eng == "python":
            # Keep python-specific integrated, drop ffmpeg-only stats.
            for k in [
                "integrated_lufs_ffmpeg",
                "delta_ffmpeg_minus_python",
                "momentary_max_ffmpeg",
                "shortterm_max_ffmpeg",
                "loudness_range_lu",
                "true_peak_dbtp",
                "momentary_max_lufs",
                "shortterm_max_lufs",
                "ffmpeg_measurement_basis",
            ]:
                payload.pop(k, None)
        else:
            # Keep ffmpeg-specific stats, drop python windowed stats.
            for k in [
                "integrated_lufs_python",
                "delta_ffmpeg_minus_python",
                "momentary_max_python",
                "shortterm_max_python",
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

    # Load early for silence/empty safety net (fast fail with clean UX)
    audio, sr = load_audio_mono(file_path)
    audio = np.asarray(audio, dtype=np.float64)

    if audio.size == 0:
        print("Error: Audio contains no samples.")
        return 1

    peak_lin = float(np.max(np.abs(audio)))

    duration_sec = float(audio.size) / float(sr) if sr else 0.0
    warnings = build_warnings(args, duration_sec)

    # Silence special-case
    if peak_lin == 0.0:
        silence_res = AnalysisResult(
            file_path=file_path,
            sr=sr,
            duration_sec=duration_sec,
            peak_dbfs=float("-inf"),
            integrated_lufs=float("-inf"),
        )
        if args.json:
            emit_json(silence_res, warnings, args)
            return 0

        print("=" * 40)
        print(" Blue Byte LUFS Analysis ")
        print("=" * 40)
        print(f"File:            {file_path}")
        print(f"Sample Rate:     {sr} Hz")
        print(f"Duration:        {duration_sec:.2f} s")
        engine_label = "compare" if args.compare else str(args.engine)
        ref_tag = " (reference)" if engine_label == "ffmpeg" else ""
        if engine_label == "python":
            ref_tag = " (approx)"
        print(f"Engine:          {engine_label}{ref_tag}")
        if warnings.short_audio_warning:
            print(f"Warning:         {warnings.short_audio_warning}")
        if warnings.engine_warning:
            print(f"Warning:         {warnings.engine_warning}")
        print("Integrated LUFS: -inf (silence)")
        print("Peak:            -inf dBFS")
        print("=" * 40)
        return 0

    # For non-silence, run analysis via the unified flow using the preloaded audio.
    res, warn = analyse_file(args, audio=audio, sr=sr)
    if res is None or warn is None:
        if args.compare or str(args.engine) == "python":
            print(
                "Error: Python loudness engine requires 'pyloudnorm'. Install it with: pip install pyloudnorm",
                file=sys.stderr,
            )
        else:
            print("Error: analysis failed.", file=sys.stderr)
        return 1

    if args.json:
        emit_json(res, warn, args)
        return 0

    print_report(res, warn, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
