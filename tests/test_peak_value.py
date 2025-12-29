from bb_audio import peak_value
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_peak_value_basic():
    audio = np.array([0.0, 0.5, -0.25], dtype=float)
    assert peak_value(audio) == 0.5


def test_peak_value_all_negative():
    audio = np.array([-0.1, -0.9, -0.2], dtype=float)
    assert peak_value(audio) == 0.9


def test_peak_value_zero_array():
    audio = np.zeros(10, dtype=float)
    assert peak_value(audio) == 0.0
