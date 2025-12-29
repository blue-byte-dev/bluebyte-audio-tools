import bb_audio
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_save_audio_calls_soundfile_write(monkeypatch, tmp_path):
    calls = {}

    def fake_write(path, audio, sr):
        calls["path"] = path
        calls["sr"] = sr
        calls["audio"] = audio

    monkeypatch.setattr(bb_audio.sf, "write", fake_write)

    out = tmp_path / "out.wav"
    audio = np.array([0.2, -0.2], dtype=float)

    bb_audio.save_audio(str(out), audio, 48000)

    assert calls["path"] == str(out)
    assert calls["sr"] == 48000
    assert np.allclose(calls["audio"], audio)
