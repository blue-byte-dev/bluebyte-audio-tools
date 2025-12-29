import os
import numpy as np
import soundfile as sf
import librosa


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
