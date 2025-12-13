import os
import numpy as np
import soundfile as sf
import librosa


# ---------- File utilities ----------

ALLOWED_EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif"}


def list_audio_files(folder=".", allowed_extensions=ALLOWED_EXTENSIONS):
    """Return a sorted list of full paths to supported audio files in `folder`."""
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


# ---------- Audio utilities ----------

def load_audio_mono(path):
    """Load audio as mono, preserving original sample rate."""
    try:
        audio, sr = librosa.load(path, sr=None, mono=True)
        return audio, sr
    except Exception as e:
        raise RuntimeError(f"Error loading '{path}': {e}")


def peak_value(audio):
    """Return peak absolute amplitude of a numpy audio array."""
    return float(np.max(np.abs(audio)))


def peak_normalise(audio, target_peak=0.9):
    """
    Peak-normalise audio to `target_peak`.
    Returns (normalized_audio, peak_before, peak_after).
    """
    peak_before = peak_value(audio)

    if peak_before == 0:
        raise ValueError("Audio is silent (peak = 0).")

    normalized = audio / peak_before * target_peak
    peak_after = peak_value(normalized)

    return normalized, peak_before, peak_after


def save_audio(path, audio, sr):
    """Write audio to disk using soundfile."""
    try:
        sf.write(path, audio, sr)
    except Exception as e:
        raise RuntimeError(f"Error saving '{path}': {e}")
