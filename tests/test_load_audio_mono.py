import bb_audio
import sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_load_audio_mono_calls_librosa_with_expected_args(monkeypatch):
    captured = {}

    def fake_load(path, sr=None, mono=True):
        captured["path"] = path
        captured["sr"] = sr
        captured["mono"] = mono
        return np.array([0.0, 0.1], dtype=float), 44100

    monkeypatch.setattr(bb_audio.librosa, "load", fake_load)

    audio, sr = bb_audio.load_audio_mono("test.wav")

    assert sr == 44100
    assert isinstance(audio, np.ndarray)
    assert audio.shape == (2,)
    assert captured["path"] == "test.wav"
    assert captured["sr"] is None
    assert captured["mono"] is True


def test_load_audio_mono_propagates_exceptions(monkeypatch):
    def fake_load(*args, **kwargs):
        raise RuntimeError("decode failed")

    monkeypatch.setattr(bb_audio.librosa, "load", fake_load)

    with pytest.raises(RuntimeError):
        bb_audio.load_audio_mono("bad.wav")
