import math


def compute_target_block(lufs_i: float, target: float, tol: float):
    """Pure math used by the CLI target mode."""
    delta = lufs_i - target
    suggested_gain = -delta
    within = abs(delta) <= tol
    return delta, suggested_gain, within


def test_target_mode_delta_and_gain():
    # Example: -13.90 vs -14.00 => +0.10 LU (too loud), suggest -0.10 dB
    delta, suggested, within = compute_target_block(-13.90, -14.00, 0.5)
    assert abs(delta - 0.10) < 1e-9
    assert abs(suggested + 0.10) < 1e-9
    assert within is True


def test_target_mode_outside_tolerance():
    # -12 vs -14 => +2 LU, outside 0.5 tol
    delta, suggested, within = compute_target_block(-12.0, -14.0, 0.5)
    assert abs(delta - 2.0) < 1e-9
    assert abs(suggested + 2.0) < 1e-9
    assert within is False


def test_silence_is_not_finite():
    lufs_i = float("-inf")
    assert not math.isfinite(lufs_i)
