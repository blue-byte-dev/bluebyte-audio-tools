import numpy as np
import pyloudnorm as pyln
import argparse
import os
import subprocess
import re
from bb_audio import load_audio_mono


def measure_ebu128_ffmpeg(path):
    """
    Measure EBU R128 metrics via FFmpeg ebur128 filter.
    Returns a dict with keys: I (integrated LUFS), M (momentary LUFS),
    S (short-term LUFS), LRA (loudness range in LU).
    Values may be None if not present in FFmpeg output.
    """
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i", path,
        "-filter_complex", "ebur128=peak=true",
        "-f", "null",
        "-"
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found on system.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError("ffmpeg failed to analyse audio.") from e

    # FFmpeg prints loudness info to stderr
    stderr = result.stderr

    # FFmpeg ebur128 prints a running meter and a final "Summary" block.
    # Parse metrics primarily from the Summary to avoid the running -70 LUFS floor.
    summary_idx = stderr.rfind("Summary:")
    parse_text = stderr[summary_idx:] if summary_idx != -1 else stderr

    def _summary_value(tag: str):
        # Matches lines like: "I:  -23.0 LUFS", "M:  -18.2 LUFS", "S:  -20.1 LUFS", "LRA:  6.7 LU"
        m = re.search(
            rf"(?m)^\s*{re.escape(tag)}:\s*(-?\d+(?:\.\d+)?)\s*(?:LUFS|LU|dBTP)\s*$",
            parse_text,
        )
        return float(m.group(1)) if m else None

    metrics = {
        "I": _summary_value("I"),
        "LRA": _summary_value("LRA"),
        "M_MAX": None,
        "S_MAX": None,
        "TP": None,
    }

    # If metrics aren't present in Summary, fall back to the last *finite* running values.
    if metrics["I"] is None:
        matches_all = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", stderr)
        if matches_all:
            metrics["I"] = float(matches_all[-1])

    # Compute max Momentary/Short-term from running meter lines (offline stats).
    m_vals = re.findall(r"M:\s*(-?\d+(?:\.\d+)?|nan)\b", stderr)
    s_vals = re.findall(r"S:\s*(-?\d+(?:\.\d+)?|nan)\b", stderr)

    def _max_above_floor(values, floor=-70.0):
        best = None
        for v in values:
            if v == "nan":
                continue
            fv = float(v)
            if fv <= floor:
                continue
            if best is None or fv > best:
                best = fv
        return best

    metrics["M_MAX"] = _max_above_floor(m_vals)
    metrics["S_MAX"] = _max_above_floor(s_vals)

    # True peak (dBTP) — try Summary first, then fall back to any TP-like lines.
    metrics["TP"] = _summary_value("TP")
    if metrics["TP"] is None:
        # Some builds print: "TP: -1.23 dBTP"
        tp_all = re.findall(r"TP:\s*(-?\d+(?:\.\d+)?)\s*dBTP", stderr)
        if tp_all:
            metrics["TP"] = float(tp_all[-1])
    if metrics["TP"] is None:
        # Some builds print the label on one line and the value on a following line.
        # Example:
        #   True peak:
        #     Peak: -1.23 dBTP
        # or:
        #   True peak:
        #     Peak: -1.23
        m = re.search(
            r"True\s+peak:\s*(?:\r?\n)+(?P<block>(?:.*\r?\n){0,25})",
            stderr,
            flags=re.IGNORECASE,
        )
        if m:
            block = m.group("block")

            # Prefer explicit dBTP anywhere in the block.
            m_db = re.search(r"(-?\d+(?:\.\d+)?)\s*dBTP\b",
                             block, flags=re.IGNORECASE)
            if m_db:
                metrics["TP"] = float(m_db.group(1))
            else:
                # Next, look specifically for a line containing 'Peak:' and take its number.
                m_peak = re.search(
                    r"(?im)^\s*Peak:\s*(-?\d+(?:\.\d+)?)\s*(?:dBTP|dBFS)?\s*$", block)
                if m_peak:
                    metrics["TP"] = float(m_peak.group(1))

    if metrics["I"] is None:
        raise RuntimeError(
            "Could not parse final integrated LUFS from ffmpeg output.")

    return metrics


def windowed_lufs_max_python(audio: np.ndarray, sr: int, window_sec: float, step_sec: float) -> float | None:
    """\
    Approximate max loudness over time by sliding a fixed window and measuring
    integrated loudness per-window using pyloudnorm.

    Notes:
    - This is NOT a full EBU R128 momentary/short-term implementation.
    - It is a practical offline approximation when pyloudnorm exposes only
      integrated_loudness().

    Returns:
        Max LUFS across windows, or None if audio is too short / no finite values.
    """
    if sr <= 0:
        return None

    win_n = int(round(window_sec * sr))
    step_n = int(round(step_sec * sr))

    # Safety guards
    if win_n <= 0 or step_n <= 0:
        return None
    if audio.size < win_n:
        return None

    meter = pyln.Meter(sr)

    best = None
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


def main(argv=None) -> int:
    # CLI parsing
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
    args = parser.parse_args(argv)

    engine = args.engine
    compare = args.compare
    file_path = args.path if args.path is not None else args.file

    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        return 1

    # ----------------------------
    # Load audio (mono)
    # ----------------------------
    audio, sr = load_audio_mono(file_path)

    # pyloudnorm expects floating point in [-1, 1]
    audio = np.asarray(audio, dtype=np.float64)

    # ----------------------------
    # Basic validity checks (safety net)
    # ----------------------------
    warnings = []

    if audio.size == 0:
        print("Error: Audio contains no samples.")
        return 1

    duration_sec = float(audio.size) / float(sr) if sr else 0.0
    if duration_sec < 3.0:
        warnings.append(
            f"Very short audio ({duration_sec:.2f}s). LUFS/LRA may be unreliable."
        )

    # ----------------------------
    # Peak + silence precheck (before LUFS)
    # ----------------------------
    peak = float(np.max(np.abs(audio)))
    if peak == 0.0:
        # Silence: LUFS will be -inf / undefined depending on engine; exit cleanly.
        print("=" * 40)
        print(" Blue Byte LUFS Analysis ")
        print("=" * 40)
        print(f"File:            {file_path}")
        print(f"Sample Rate:     {sr} Hz")
        if warnings:
            for w in warnings:
                print(f"Warning:         {w}")
        print("Integrated LUFS: -inf (silence)")
        print("Peak:            -inf dBFS")
        print("=" * 40)
        return 0

    peak_dbfs = 20 * np.log10(peak)

    # ----------------------------
    # Measure integrated loudness
    # ----------------------------
    if compare:
        # Python (pyloudnorm)
        meter = pyln.Meter(sr)
        lufs_python = meter.integrated_loudness(audio)

        # Python-side offline approximations for "max momentary" and "max short-term"
        # using windowed integrated loudness.
        mmax_python = windowed_lufs_max_python(
            audio, sr, window_sec=0.4, step_sec=0.1)
        smax_python = windowed_lufs_max_python(
            audio, sr, window_sec=3.0, step_sec=0.5)

        # FFmpeg (ebur128)
        try:
            ff = measure_ebu128_ffmpeg(file_path)
            lufs_ffmpeg = ff["I"]
            mmax_ffmpeg = ff["M_MAX"]
            smax_ffmpeg = ff["S_MAX"]
            lra_ffmpeg = ff["LRA"]
            tp_ffmpeg = ff.get("TP")
        except RuntimeError as e:
            print("Error:", e)
            return 1

        lufs_delta = lufs_ffmpeg - lufs_python
        lufs_i = lufs_ffmpeg  # keep a single value for any downstream use
    else:
        if engine == "python":
            meter = pyln.Meter(sr)
            lufs_i = meter.integrated_loudness(audio)
        elif engine == "ffmpeg":
            try:
                ff = measure_ebu128_ffmpeg(file_path)
                lufs_i = ff["I"]
                mmax_ffmpeg = ff["M_MAX"]
                smax_ffmpeg = ff["S_MAX"]
                lra_ffmpeg = ff["LRA"]
                tp_ffmpeg = ff.get("TP")
            except RuntimeError as e:
                print("Error:", e)
                return 1

    # Guard against non-finite outputs
    if compare:
        if not np.isfinite(lufs_python) or not np.isfinite(lufs_ffmpeg):
            print("Error: Non-finite LUFS value detected.")
            return 1
    else:
        if not np.isfinite(lufs_i):
            print("Error: Non-finite LUFS value detected.")
            return 1

    # ----------------------------
    # Print report
    # ----------------------------
    print("=" * 40)
    print(" Blue Byte LUFS Analysis ")
    print("=" * 40)
    print(f"File:            {file_path}")
    print(f"Sample Rate:     {sr} Hz")
    if warnings:
        for w in warnings:
            print(f"Warning:         {w}")
    if compare:
        print(f"Integrated LUFS (python): {lufs_python:.2f} LUFS")
        print(f"Integrated LUFS (ffmpeg): {lufs_ffmpeg:.2f} LUFS")
        print(f"Delta (ffmpeg - python):  {lufs_delta:+.2f} LU")
        if mmax_python is not None:
            print(f"Momentary Max (python):   {mmax_python:.2f} LUFS")
        if smax_python is not None:
            print(f"Short-term Max (python):  {smax_python:.2f} LUFS")
        if mmax_ffmpeg is not None:
            print(f"Momentary Max (ffmpeg):   {mmax_ffmpeg:.2f} LUFS")
        if smax_ffmpeg is not None:
            print(f"Short-term Max (ffmpeg):  {smax_ffmpeg:.2f} LUFS")
        if lra_ffmpeg is not None:
            print(f"Loudness Range (ffmpeg):  {lra_ffmpeg:.2f} LU")
        if tp_ffmpeg is not None:
            print(f"True Peak (ffmpeg):       {tp_ffmpeg:.2f} dBTP")
    else:
        print(f"Integrated LUFS: {lufs_i:.2f} LUFS")
        if engine == "ffmpeg":
            if mmax_ffmpeg is not None:
                print(f"Momentary Max:   {mmax_ffmpeg:.2f} LUFS")
            if smax_ffmpeg is not None:
                print(f"Short-term Max:  {smax_ffmpeg:.2f} LUFS")
            if lra_ffmpeg is not None:
                print(f"Loudness Range:  {lra_ffmpeg:.2f} LU")
            if tp_ffmpeg is not None:
                print(f"True Peak:       {tp_ffmpeg:.2f} dBTP")
    print(f"Peak:            {peak_dbfs:.2f} dBFS")
    print("=" * 40)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
