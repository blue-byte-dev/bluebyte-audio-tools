import os
import re
import shutil
import subprocess
from typing import Any

import numpy as np
import soundfile as sf
import librosa

try:
    import pyloudnorm as pyln
except Exception:  # optional dependency
    pyln = None


# ---------- File utilities ----------

# Supported input formats (for scanning/loading). Output format support is handled by CLI tools.
ALLOWED_EXTENSIONS: set[str] = {".wav", ".flac", ".ogg", ".aiff", ".aif"}


def list_audio_files(folder: str = ".", allowed_extensions: set[str] | None = None) -> list[str]:
    """Return a sorted list of full paths to supported audio files in `folder`.

    Args:
        folder: Folder to scan.
        allowed_extensions: Optional set of allowed extensions (lowercase, with leading dots).

    Returns:
        Sorted list of full file paths.
    """
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXTENSIONS

    try:
        entries = os.listdir(folder)
    except Exception as e:
        raise RuntimeError(f"Could not read folder '{folder}': {e}")

    audio_files = []
    for name in entries:
        full_path = os.path.join(folder, name)

        if not os.path.isfile(full_path):
            continue

        _, ext = os.path.splitext(name)
        ext = ext.lower()

        if ext not in allowed_extensions:
            continue

        audio_files.append(full_path)

    return sorted(audio_files)


def should_write_file(output_path: str, overwrite: bool, dry_run: bool) -> tuple[bool, str]:
    """Decide whether an output file should be written.

    This is a pure decision helper: it performs no I/O besides checking existence.

    Returns:
        (should_write, reason)
        reason is one of: "new", "overwrite", "dry_run_skip", "exists".
    """
    exists = os.path.exists(output_path)

    if not exists:
        return True, "new"

    if overwrite:
        return True, "overwrite"

    if dry_run:
        return False, "dry_run_skip"

    return False, "exists"

# ---------- Audio utilities ----------


def load_audio_mono(path: str) -> tuple[np.ndarray, int]:
    """Load audio as mono, preserving the original sample rate.

    Args:
        path: Input file path.

    Returns:
        (audio, sr) where audio is a float numpy array and sr is the sample rate.
    """
    try:
        audio, sr = librosa.load(path, sr=None, mono=True)
        return audio, sr
    except Exception as e:
        raise RuntimeError(f"Error loading '{path}': {e}")


def peak_value(audio: np.ndarray) -> float:
    """Return peak absolute amplitude of a numpy audio array."""
    return float(np.max(np.abs(audio)))


def peak_normalise(audio: np.ndarray, target_peak: float = 0.9) -> tuple[np.ndarray, float, float]:
    """Peak-normalise audio to `target_peak`.

    Returns:
        (normalized_audio, peak_before, peak_after)
    """
    peak_before = peak_value(audio)

    if peak_before == 0:
        raise ValueError("Audio is silent (peak = 0).")

    normalized = audio / peak_before * target_peak
    peak_after = peak_value(normalized)

    return normalized, peak_before, peak_after


def save_audio(path: str, audio: np.ndarray, sr: int) -> None:
    """Write audio to disk using soundfile."""
    try:
        sf.write(path, audio, sr)
    except Exception as e:
        raise RuntimeError(f"Error saving '{path}': {e}")


# ---------- Loudness (LUFS) utilities ----------


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _db_from_linear(x: float) -> float:
    if x <= 0:
        return float("-inf")
    return float(20.0 * np.log10(x))


def _linear_from_db(db: float) -> float:
    return float(10 ** (db / 20.0))


def compute_gain_db(
    measured_lufs: float,
    target_lufs: float,
    min_gain_db: float = -24.0,
    max_gain_db: float = 24.0,
) -> float:
    """Compute gain in dB to move measured LUFS to target LUFS, with clamping."""
    gain = float(target_lufs - measured_lufs)
    return float(_clamp(gain, min_gain_db, max_gain_db))


def load_audio_sf(path: str) -> tuple[np.ndarray, int]:
    """Load audio via soundfile (keeps channels). Returns (audio, sr).

    Audio is returned as float32/float64 numpy array.
    """
    try:
        audio, sr = sf.read(path, always_2d=False)
        return audio, int(sr)
    except Exception as e:
        raise RuntimeError(f"Error loading '{path}' with soundfile: {e}")


def _mono_float(audio: np.ndarray) -> np.ndarray:
    """Convert audio to mono float array."""
    a = np.asarray(audio)
    if a.ndim == 1:
        return a.astype(float)
    # shape: (n, ch)
    return a.mean(axis=1).astype(float)


def measure_lufs_python(audio: np.ndarray, sr: int) -> dict[str, Any]:
    """Measure integrated LUFS and windowed LUFS maxima using pyloudnorm.

    Returns keys:
      - lufs_i
      - momentary_max (approx, max over 0.4s windows)
      - short_term_max (approx, max over 3.0s windows)
    """
    if pyln is None:
        raise RuntimeError(
            "pyloudnorm is not installed. Install it or use engine='ffmpeg'.")

    mono = _mono_float(audio)
    meter = pyln.Meter(sr)  # BS.1770

    lufs_i = float(meter.integrated_loudness(mono))

    def window_max(window_s: float) -> float | None:
        win = int(round(window_s * sr))
        if win <= 0 or mono.size < win:
            return None
        # Step = half window for speed; good enough for a max indicator
        step = max(1, win // 2)
        best = None
        for start in range(0, mono.size - win + 1, step):
            seg = mono[start: start + win]
            v = float(meter.integrated_loudness(seg))
            if not np.isfinite(v):
                continue
            if best is None or v > best:
                best = v
        return best

    momentary_max = window_max(0.4)
    short_term_max = window_max(3.0)

    return {
        "lufs_i": lufs_i,
        "momentary_max": momentary_max,
        "short_term_max": short_term_max,
    }


_EBUR_LINE_RE = re.compile(
    r"\bM:\s*([-+0-9.]+|nan)\b.*?\bS:\s*([-+0-9.]+|nan)\b")
_EBUR_SUMMARY_I_RE = re.compile(r"\bI:\s*([-+0-9.]+)\s*LUFS\b")
_EBUR_SUMMARY_LRA_RE = re.compile(r"\bLRA:\s*([-+0-9.]+)\s*LU\b")
_EBUR_TP_RE = re.compile(r"\bTP:\s*([-+0-9.]+)\s*dBTP\b")


def _ffmpeg_required() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg not found on PATH.")
    return path


def measure_ebu128_ffmpeg(path: str) -> dict[str, Any]:
    """Measure EBU R128 stats using ffmpeg ebur128.

    Returns keys (when available):
      - lufs_i
      - lra
      - momentary_max
      - short_term_max
      - true_peak
    """
    _ffmpeg_required()

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        path,
        "-filter_complex",
        "ebur128=peak=true",
        "-f",
        "null",
        "-",
    ]

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, check=False)
    except Exception as e:
        raise RuntimeError(f"Error running ffmpeg: {e}")

    text = proc.stderr or ""

    # Track max M and S across per-timestamp lines.
    m_best = None
    s_best = None
    for line in text.splitlines():
        m = _EBUR_LINE_RE.search(line)
        if not m:
            continue
        m_val_s, s_val_s = m.group(1), m.group(2)
        try:
            m_val = float(m_val_s)
            s_val = float(s_val_s)
        except Exception:
            continue
        if np.isfinite(m_val):
            if m_best is None or m_val > m_best:
                m_best = m_val
        if np.isfinite(s_val):
            if s_best is None or s_val > s_best:
                s_best = s_val

    # Summary block values
    lufs_i = None
    lra = None
    tp = None
    for line in text.splitlines():
        mi = _EBUR_SUMMARY_I_RE.search(line)
        if mi:
            try:
                lufs_i = float(mi.group(1))
            except Exception:
                pass
        mlra = _EBUR_SUMMARY_LRA_RE.search(line)
        if mlra:
            try:
                lra = float(mlra.group(1))
            except Exception:
                pass
        mtp = _EBUR_TP_RE.search(line)
        if mtp:
            try:
                tp = float(mtp.group(1))
            except Exception:
                pass

    if lufs_i is None:
        # Some ffmpeg builds only print summary at the end; if parsing failed, surface stderr.
        raise RuntimeError("Failed to parse ffmpeg ebur128 output.")

    return {
        "lufs_i": lufs_i,
        "lra": lra,
        "momentary_max": m_best,
        "short_term_max": s_best,
        "true_peak": tp,
    }


def analyse_loudness(
    path: str,
    engine: str = "python",
    compare: bool = False,
    target_lufs: float | None = None,
    tolerance: float = 0.5,
    apply: bool = False,
    force_apply: bool = False,
    output_path: str | None = None,
    dry_run: bool = False,
    allow_clip: bool = False,
    true_peak_limit: float = -1.0,
    min_gain_db: float = -24.0,
    max_gain_db: float = 24.0,
) -> dict[str, Any]:
    """High-level loudness analysis with optional target-mode apply.

    This is backend logic (no printing). CLI tools should call this and format output.
    """
    audio, sr = load_audio_sf(path)
    mono = _mono_float(audio)

    # Sample peak (linear and dBFS)
    peak_lin = peak_value(mono)
    peak_dbfs = _db_from_linear(peak_lin)

    result: dict[str, Any] = {
        "path": path,
        "sr": sr,
        "peak_dbfs": peak_dbfs,
    }

    # Silence detection
    if peak_lin == 0:
        result.update(
            {
                "lufs_i": float("-inf"),
                "momentary_max": None,
                "short_term_max": None,
                "lra": None,
                "true_peak": None,
                "target_lufs": target_lufs,
                "tolerance": tolerance,
                "within_tolerance": None,
                "suggested_gain_db": None,
                "apply_action": "silence",
                "output_path": None,
            }
        )
        return result

    # Measure (python)
    lufs_py = None
    m_py = None
    s_py = None
    if engine == "python" or compare:
        py_stats = measure_lufs_python(mono, sr)
        lufs_py = py_stats["lufs_i"]
        m_py = py_stats["momentary_max"]
        s_py = py_stats["short_term_max"]
        result.update({
            "lufs_i_python": lufs_py,
            "momentary_max_python": m_py,
            "short_term_max_python": s_py,
        })

    # Measure (ffmpeg)
    lufs_ff = None
    m_ff = None
    s_ff = None
    lra_ff = None
    tp_ff = None
    if engine == "ffmpeg" or compare:
        ff_stats = measure_ebu128_ffmpeg(path)
        lufs_ff = ff_stats["lufs_i"]
        m_ff = ff_stats.get("momentary_max")
        s_ff = ff_stats.get("short_term_max")
        lra_ff = ff_stats.get("lra")
        tp_ff = ff_stats.get("true_peak")
        result.update({
            "lufs_i_ffmpeg": lufs_ff,
            "momentary_max_ffmpeg": m_ff,
            "short_term_max_ffmpeg": s_ff,
            "lra_ffmpeg": lra_ff,
            "true_peak_ffmpeg": tp_ff,
        })

    # Choose reference integrated LUFS
    if compare:
        ref_lufs = lufs_ff
        ref_engine = "ffmpeg"
        delta_lu = None
        if lufs_py is not None and lufs_ff is not None:
            delta_lu = float(lufs_ff - lufs_py)
        result.update({
            "ref_engine": ref_engine,
            "delta_ffmpeg_minus_python": delta_lu,
        })
    else:
        if engine == "ffmpeg":
            ref_lufs = lufs_ff
            ref_engine = "ffmpeg"
        else:
            ref_lufs = lufs_py
            ref_engine = "python"
        result.update({
            "ref_engine": ref_engine,
        })

    result["lufs_i"] = ref_lufs
    result["momentary_max"] = m_ff if ref_engine == "ffmpeg" else m_py
    result["short_term_max"] = s_ff if ref_engine == "ffmpeg" else s_py
    result["lra"] = lra_ff if ref_engine == "ffmpeg" else None
    result["true_peak"] = tp_ff if ref_engine == "ffmpeg" else None

    # Target compliance
    if target_lufs is not None and ref_lufs is not None and np.isfinite(ref_lufs):
        delta = float(ref_lufs - target_lufs)
        within = bool(abs(delta) <= tolerance)
        gain_db = compute_gain_db(
            ref_lufs, target_lufs, min_gain_db, max_gain_db)
        gain_lin = _linear_from_db(gain_db)
        pred_peak_lin = peak_lin * gain_lin
        pred_peak_dbfs = _db_from_linear(pred_peak_lin)

        pred_tp = None
        if tp_ff is not None:
            pred_tp = float(tp_ff + gain_db)

        result.update({
            "target_lufs": float(target_lufs),
            "tolerance": float(tolerance),
            "delta_lu": float(delta),
            "within_tolerance": within,
            "suggested_gain_db": float(gain_db),
            "pred_peak_dbfs": float(pred_peak_dbfs),
            "pred_true_peak_dbtp": pred_tp,
            "true_peak_limit": float(true_peak_limit),
        })

        # Apply mode
        if apply:
            if within and not force_apply:
                result.update({
                    "apply_action": "skip_compliant",
                    "output_path": None,
                    "dry_run": bool(dry_run),
                })
                return result

            # Abort on predicted clipping unless allowed
            if pred_peak_lin > 1.0 and not allow_clip:
                result.update({
                    "apply_action": "aborted_clip",
                    "output_path": None,
                    "dry_run": bool(dry_run),
                })
                return result

            # Decide output path
            if output_path is None:
                base = os.path.basename(path)
                output_path = os.path.join(
                    os.path.dirname(path), f"targeted_{base}")

            result.update({
                "output_path": output_path,
                "apply_gain_db": float(gain_db),
                "dry_run": bool(dry_run),
            })

            if dry_run:
                result["apply_action"] = "dry_run"
                return result

            out_audio = audio * gain_lin
            try:
                sf.write(output_path, out_audio, sr)
            except Exception as e:
                raise RuntimeError(f"Error writing '{output_path}': {e}")

            result["apply_action"] = "wrote"
            return result

    # No target mode (or non-finite LUFS)
    result.update({
        "target_lufs": target_lufs,
        "tolerance": tolerance,
        "within_tolerance": None,
        "suggested_gain_db": None,
        "apply_action": None,
        "output_path": None,
    })
    return result
