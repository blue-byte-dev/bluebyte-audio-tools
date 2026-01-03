
import argparse
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

import numpy as np
import soundfile as sf

from bb_audio import load_audio_mono


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
# Gain computation (target mode)
# ----------------------------

def compute_gain_db(
    current_lufs: float,
    target_lufs: float,
    min_gain_db: float,
    max_gain_db: float,
) -> float:
    """Compute gain (dB) to move current integrated LUFS to target LUFS.

    gain_db = -(current - target)
      - if current is louder than target (current > target), gain_db is negative
      - if current is quieter than target (current < target), gain_db is positive

    The result is clamped to [min_gain_db, max_gain_db].
    """
    raw = -(current_lufs - target_lufs)
    return clamp(raw, min_gain_db, max_gain_db)


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


def measure_ebu128_ffmpeg(path: str) -> Ebur128Metrics:
    """Measure EBU R128 metrics via FFmpeg `ebur128=peak=true`.

    Returns integrated LUFS + offline stats derived from running meter output:
    - momentary_max_lufs: max M values above the -70 LUFS floor
    - shortterm_max_lufs: max S values above the -70 LUFS floor
    - loudness_range_lu: from Summary block if present
    - true_peak_dbtp: parsed if present (varies by build)

    Note: momentary/short-term are OFFLINE maxima from the run; this CLI is not
    a real-time meter.
    """
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        path,
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
    )


# ----------------------------
# Python-side loudness
# ----------------------------

def measure_integrated_lufs_python(audio: np.ndarray, sr: int) -> float:
    """Integrated LUFS using pyloudnorm (ITU-R BS.1770 / EBU R128 style)."""
    import pyloudnorm as pyln

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

    import pyloudnorm as pyln

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


@dataclass
class AnalysisResult:
    file_path: str
    sr: int
    peak_dbfs: float
    integrated_lufs: float

    # Optional extras
    momentary_max_lufs: Optional[float] = None
    shortterm_max_lufs: Optional[float] = None
    loudness_range_lu: Optional[float] = None
    true_peak_dbtp: Optional[float] = None

    # Compare mode
    integrated_lufs_python: Optional[float] = None
    integrated_lufs_ffmpeg: Optional[float] = None
    delta_ffmpeg_minus_python: Optional[float] = None
    momentary_max_python: Optional[float] = None
    shortterm_max_python: Optional[float] = None
    momentary_max_ffmpeg: Optional[float] = None
    shortterm_max_ffmpeg: Optional[float] = None

    # Target mode
    target_lufs: Optional[float] = None
    tolerance_lu: Optional[float] = None
    target_delta_lu: Optional[float] = None
    target_status: Optional[str] = None
    suggested_gain_db: Optional[float] = None

    apply_requested: bool = False
    apply_skipped: bool = False
    apply_gain_db: Optional[float] = None
    predicted_peak_dbfs: Optional[float] = None
    predicted_true_peak_dbtp: Optional[float] = None
    predicted_true_peak_warn: bool = False

    dry_run: bool = False
    wrote_path: Optional[str] = None
    apply_note: Optional[str] = None


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
        default="python",
        help="Loudness analysis engine (default: python).",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run both engines (python + ffmpeg) and print a delta.",
    )

    parser.add_argument(
        "--target_lufs",
        type=float,
        default=None,
        help="Optional target integrated LUFS for compliance reporting (e.g., -14).",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.5,
        help="Tolerance in LU for target compliance (default: 0.5 LUFS).",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply gain to reach --target_lufs and write a new file (default: measure only).",
    )
    parser.add_argument(
        "--force_apply",
        action="store_true",
        help="With --apply: write output even if already within --tolerance of --target_lufs.",
    )

    parser.add_argument(
        "--output",
        default=None,
        help="Output file path when using --apply (default: targeted_<input>.wav).",
    )

    parser.add_argument(
        "--min_gain_db",
        type=float,
        default=-24.0,
        help="Minimum allowed gain change in dB (default: -24.0).",
    )
    parser.add_argument(
        "--max_gain_db",
        type=float,
        default=12.0,
        help="Maximum allowed gain change in dB (default: +12.0).",
    )

    parser.add_argument(
        "--true_peak_limit",
        type=float,
        default=-1.0,
        help=(
            "If ffmpeg true-peak is available, warn when predicted output exceeds this limit in dBTP "
            "(default: -1.0)."
        ),
    )

    parser.add_argument(
        "--allow_clip",
        action="store_true",
        help="Allow writing even if sample peak would exceed 0 dBFS (clipping). Default is to abort.",
    )

    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="With --apply, print what would be written without creating a file.",
    )

    return parser.parse_args(argv)


def resolve_file_path(args: argparse.Namespace) -> str:
    return args.path if args.path is not None else args.file


def default_output_path_for_apply(file_path: str) -> str:
    base = os.path.basename(file_path)
    stem, _ext = os.path.splitext(base)
    return os.path.join(os.path.dirname(file_path), f"targeted_{stem}.wav")


def analyse_file(args: argparse.Namespace) -> tuple[AnalysisResult, AnalysisWarnings] | tuple[None, None]:
    file_path = resolve_file_path(args)

    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        return None, None

    audio, sr = load_audio_mono(file_path)
    audio = np.asarray(audio, dtype=np.float64)

    warnings = AnalysisWarnings()

    if audio.size == 0:
        print("Error: Audio contains no samples.")
        return None, None

    duration_sec = float(audio.size) / float(sr) if sr else 0.0
    if duration_sec < 3.0:
        warnings.short_audio_warning = (
            f"Very short audio ({duration_sec:.2f}s). LUFS/LRA may be unreliable."
        )

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
        lufs_py = measure_integrated_lufs_python(audio, sr)
        mmax_py = windowed_lufs_max_python(
            audio, sr, window_sec=0.4, step_sec=0.1)
        smax_py = windowed_lufs_max_python(
            audio, sr, window_sec=3.0, step_sec=0.5)

        ff = measure_ebu128_ffmpeg(file_path)

        lufs_ff = ff.integrated_lufs
        delta = lufs_ff - lufs_py

        # Reference integrated = ffmpeg integrated
        res = AnalysisResult(
            file_path=file_path,
            sr=sr,
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
            momentary_max_lufs=ff.momentary_max_lufs,
            shortterm_max_lufs=ff.shortterm_max_lufs,
        )
        return res, warnings

    # Non-compare: run selected engine.
    engine = str(args.engine)
    if engine == "python":
        lufs_i = measure_integrated_lufs_python(audio, sr)
        res = AnalysisResult(
            file_path=file_path,
            sr=sr,
            peak_dbfs=peak_dbfs,
            integrated_lufs=lufs_i,
        )
        return res, warnings

    # ffmpeg engine
    ff = measure_ebu128_ffmpeg(file_path)
    res = AnalysisResult(
        file_path=file_path,
        sr=sr,
        peak_dbfs=peak_dbfs,
        integrated_lufs=ff.integrated_lufs,
        momentary_max_lufs=ff.momentary_max_lufs,
        shortterm_max_lufs=ff.shortterm_max_lufs,
        loudness_range_lu=ff.loudness_range_lu,
        true_peak_dbtp=ff.true_peak_dbtp,
    )
    return res, warnings


def apply_target_gain_if_requested(
    args: argparse.Namespace,
    result: AnalysisResult,
    warnings: AnalysisWarnings,
) -> int:
    """If --target_lufs and --apply are used, perform optional render.

    Implements:
    - do NOT write if already within tolerance, unless --force_apply
    - optional --dry_run
    - peak prediction + optional true-peak prediction warning
    """

    if args.target_lufs is None:
        return 0

    target_lufs = float(args.target_lufs)
    tol = float(args.tolerance)

    delta_lu = float(result.integrated_lufs - target_lufs)
    within = abs(delta_lu) <= tol

    suggested_gain_db = -delta_lu

    result.target_lufs = target_lufs
    result.tolerance_lu = tol
    result.target_delta_lu = delta_lu
    result.suggested_gain_db = suggested_gain_db

    if within:
        result.target_status = "✅ Within tolerance"
    else:
        result.target_status = "⬆ Too loud" if delta_lu > 0 else "⬇ Too quiet"

    # Apply mode?
    if not args.apply:
        return 0

    result.apply_requested = True

    # No write if compliant unless forced
    if within and not args.force_apply:
        result.apply_skipped = True
        result.dry_run = bool(args.dry_run)
        result.apply_note = "Skipped (already within tolerance). Use --force_apply to write anyway."
        return 0

    # Compute clamped gain for apply
    gain_db = compute_gain_db(
        current_lufs=float(result.integrated_lufs),
        target_lufs=target_lufs,
        min_gain_db=float(args.min_gain_db),
        max_gain_db=float(args.max_gain_db),
    )
    gain_lin = lin_from_db(gain_db)
    result.apply_gain_db = gain_db

    # Predict peak after gain
    # We need the true peak linear for prediction? We only have sample peak dBFS in result.
    # Predict using sample peak dBFS only.
    if np.isfinite(result.peak_dbfs):
        peak_out_dbfs = float(result.peak_dbfs + gain_db)
    else:
        peak_out_dbfs = float("-inf")
    result.predicted_peak_dbfs = peak_out_dbfs

    # True peak prediction if available (only for ffmpeg / compare where TP exists)
    if result.true_peak_dbtp is not None:
        pred_tp = float(result.true_peak_dbtp + gain_db)
        result.predicted_true_peak_dbtp = pred_tp
        if pred_tp > float(args.true_peak_limit):
            result.predicted_true_peak_warn = True

    # Safety: clipping check
    if peak_out_dbfs > 0.0 and not args.allow_clip:
        result.apply_note = "Error: Predicted sample peak exceeds 0 dBFS. Use --allow_clip to force write."
        return 1

    # Output path
    output_path = args.output if args.output is not None else default_output_path_for_apply(
        result.file_path)

    result.dry_run = bool(args.dry_run)

    if result.dry_run:
        result.wrote_path = output_path
        return 0

    # Load again for rendering (keeps apply isolated from analysis flow)
    audio, sr = load_audio_mono(result.file_path)
    audio = np.asarray(audio, dtype=np.float64)

    out_audio = audio * gain_lin
    try:
        sf.write(output_path, out_audio, sr)
    except Exception as e:
        result.apply_note = f"Error writing output file: {e}"
        return 1

    result.wrote_path = output_path
    return 0


def print_report(result: AnalysisResult, warnings: AnalysisWarnings, args: argparse.Namespace) -> None:
    print("=" * 40)
    print(" Blue Byte LUFS Analysis ")
    print("=" * 40)

    print(f"File:            {result.file_path}")
    print(f"Sample Rate:     {result.sr} Hz")

    if warnings.short_audio_warning:
        print(f"Warning:         {warnings.short_audio_warning}")

    # Silence handling is done in main() before calling analyse_file() in the original version,
    # but here we keep consistent printing if peak is -inf.

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

        if args.target_lufs is not None:
            print("Target reference:        ffmpeg integrated")

        if result.momentary_max_python is not None:
            print(
                f"Momentary Max (python):   {result.momentary_max_python:.2f} LUFS")
        if result.shortterm_max_python is not None:
            print(
                f"Short-term Max (python):  {result.shortterm_max_python:.2f} LUFS")

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

        if args.engine == "ffmpeg":
            if result.momentary_max_lufs is not None:
                print(f"Momentary Max:   {result.momentary_max_lufs:.2f} LUFS")
            if result.shortterm_max_lufs is not None:
                print(f"Short-term Max:  {result.shortterm_max_lufs:.2f} LUFS")
            if result.loudness_range_lu is not None:
                print(f"Loudness Range:  {result.loudness_range_lu:.2f} LU")
            if result.true_peak_dbtp is not None:
                print(f"True Peak:       {result.true_peak_dbtp:.2f} dBTP")

    # Target reporting
    if result.target_lufs is not None:
        if not np.isfinite(result.integrated_lufs):
            print(f"Target LUFS:     {result.target_lufs:.2f} LUFS")
            print("Delta:           N/A (silence)")
            print("Status:          ⚠ Silence")
            print("Suggested gain:  N/A")
        else:
            assert result.target_delta_lu is not None
            assert result.target_status is not None
            assert result.suggested_gain_db is not None

            print(f"Target LUFS:     {result.target_lufs:.2f} LUFS")
            print(f"Delta:           {fmt_signed(result.target_delta_lu)} LU")
            print(f"Status:          {result.target_status}")
            print(
                f"Suggested gain:  {fmt_signed(result.suggested_gain_db)} dB")

        # Apply reporting
        if result.apply_requested:
            if result.apply_skipped:
                if result.dry_run:
                    print("Dry run:         True")
                print(f"Apply:           {result.apply_note}")
            else:
                if result.apply_gain_db is not None:
                    print(
                        f"Apply gain:      {fmt_signed(result.apply_gain_db)} dB")

                if result.predicted_true_peak_dbtp is not None:
                    warn = " ⚠" if result.predicted_true_peak_warn else ""
                    print(
                        f"Pred. True Peak: {result.predicted_true_peak_dbtp:.2f} dBTP{warn}")

                if result.predicted_peak_dbfs is not None:
                    print(
                        f"Pred. Peak:      {result.predicted_peak_dbfs:.2f} dBFS")

                if result.dry_run:
                    print("Dry run:         True")
                    if result.wrote_path:
                        print(f"Would write:     {result.wrote_path}")
                else:
                    if result.wrote_path:
                        print(f"Wrote file:      {result.wrote_path}")
                    if result.apply_note and result.apply_note.startswith("Error"):
                        print(result.apply_note)

    # Peak always at end for consistency
    if np.isfinite(result.peak_dbfs):
        print(f"Peak:            {result.peak_dbfs:.2f} dBFS")
    else:
        print("Peak:            -inf dBFS")

    print("=" * 40)


def main(argv=None) -> int:
    args = parse_args(argv)

    file_path = resolve_file_path(args)

    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        return 1

    # Load early for silence/empty safety net (fast fail with clean UX)
    audio, sr = load_audio_mono(file_path)
    audio = np.asarray(audio, dtype=np.float64)

    if audio.size == 0:
        print("Error: Audio contains no samples.")
        return 1

    peak_lin = float(np.max(np.abs(audio)))
    peak_dbfs = db_from_lin(peak_lin)

    # Build warnings
    duration_sec = float(audio.size) / float(sr) if sr else 0.0
    warnings = AnalysisWarnings()
    if duration_sec < 3.0:
        warnings.short_audio_warning = (
            f"Very short audio ({duration_sec:.2f}s). LUFS/LRA may be unreliable."
        )

    # Silence special-case
    if peak_lin == 0.0:
        print("=" * 40)
        print(" Blue Byte LUFS Analysis ")
        print("=" * 40)
        print(f"File:            {file_path}")
        print(f"Sample Rate:     {sr} Hz")
        if warnings.short_audio_warning:
            print(f"Warning:         {warnings.short_audio_warning}")
        print("Integrated LUFS: -inf (silence)")
        print("Peak:            -inf dBFS")

        if args.target_lufs is not None:
            print(f"Target LUFS:     {float(args.target_lufs):.2f} LUFS")
            print("Delta:           N/A (silence)")
            print("Status:          ⚠ Silence")
            print("Suggested gain:  N/A")

            if args.apply:
                if args.dry_run:
                    print("Dry run:         True")
                print("Apply:           N/A (silence)")

        print("=" * 40)
        return 0

    # For non-silence, run analysis via the unified flow.
    # We pass args through analyse_file() which will load the file again only for apply render.
    res, warn = analyse_file(args)
    if res is None or warn is None:
        return 1

    # ensure peak from the early load is used (avoids any tiny dtype differences)
    res.peak_dbfs = peak_dbfs

    # target/apply handling
    if args.target_lufs is not None:
        # For compare mode, the result.integrated_lufs is already ffmpeg integrated.
        # For non-compare, it is the selected engine integrated.
        apply_rc = apply_target_gain_if_requested(args, res, warn)
        if apply_rc != 0:
            # Print report including error note
            print_report(res, warn, args)
            return apply_rc

    print_report(res, warn, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
