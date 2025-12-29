from bb_audio import peak_normalise
import sys
from pathlib import Path
import numpy as np

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_peak_normalise_scales_correctly():
    audio = np.array([0.0, 0.5, -0.5], dtype=float)

    normalized, peak_before, peak_after = peak_normalise(
        audio, target_peak=0.9)

    assert peak_before == 0.5
    assert np.isclose(peak_after, 0.9)
    assert np.isclose(np.max(np.abs(normalized)), 0.9)


def test_peak_normalise_preserves_shape():
    audio = np.array([0.2, -0.4, 0.1], dtype=float)

    normalized, _, _ = peak_normalise(audio)

    assert normalized.shape == audio.shape


def test_peak_normalise_silent_audio_raises():
    audio = np.zeros(5, dtype=float)

    try:
        peak_normalise(audio)
        assert False, "Expected ValueError for silent audio"
    except ValueError:
        assert True
