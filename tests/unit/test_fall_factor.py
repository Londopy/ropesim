"""
Unit tests for fall factor computation.

Tests are written against both the Python fallback path and, when the Rust
extension is available, against the compiled _rustcore function directly.
"""
import pytest


# ── Pure-Python / fallback logic ──────────────────────────────────────────────

def _py_fall_factor(fall_distance: float, rope_out: float) -> float:
    """Mirror of the Rust logic for pure-Python testing."""
    if rope_out <= 0:
        raise ValueError("rope_out must be > 0")
    return min(fall_distance / rope_out, 2.0)


class TestFallFactorPython:
    def test_typical(self):
        ff = _py_fall_factor(6.0, 20.0)
        assert abs(ff - 0.30) < 1e-9

    def test_worst_case(self):
        # Fall distance == 2× rope out → ff = 2.0 (worst factor on lead)
        ff = _py_fall_factor(10.0, 5.0)
        assert ff == 2.0

    def test_clamp_above_two(self):
        ff = _py_fall_factor(100.0, 1.0)
        assert ff == 2.0

    def test_zero_factor(self):
        ff = _py_fall_factor(0.0, 10.0)
        assert ff == 0.0

    def test_rope_out_zero_raises(self):
        with pytest.raises((ValueError, ZeroDivisionError)):
            _py_fall_factor(5.0, 0.0)

    def test_rope_out_negative_raises(self):
        with pytest.raises((ValueError, ZeroDivisionError)):
            _py_fall_factor(5.0, -1.0)

    def test_ff_equals_one(self):
        # Exactly at belay device → ff = 1.0
        ff = _py_fall_factor(10.0, 10.0)
        assert abs(ff - 1.0) < 1e-9

    def test_small_fall(self):
        # Typical sport climb: 1 m above last bolt, 15 m rope out
        ff = _py_fall_factor(2.0, 15.0)
        assert abs(ff - 2.0 / 15.0) < 1e-9


# ── Rust-backed tests (skipped if extension not compiled) ─────────────────────

@pytest.mark.requires_rust
class TestFallFactorRust:
    def test_typical(self, rustcore):
        ff = rustcore.compute_fall_factor(6.0, 20.0)
        assert abs(ff - 0.30) < 1e-9

    def test_clamp(self, rustcore):
        ff = rustcore.compute_fall_factor(100.0, 1.0)
        assert ff == pytest.approx(2.0)

    def test_zero_distance(self, rustcore):
        ff = rustcore.compute_fall_factor(0.0, 10.0)
        assert ff == pytest.approx(0.0)

    def test_rope_out_zero_raises(self, rustcore):
        with pytest.raises(ValueError):
            rustcore.compute_fall_factor(5.0, 0.0)

    def test_rope_out_negative_raises(self, rustcore):
        with pytest.raises(ValueError):
            rustcore.compute_fall_factor(5.0, -3.0)

    def test_ff_one(self, rustcore):
        ff = rustcore.compute_fall_factor(10.0, 10.0)
        assert ff == pytest.approx(1.0)

    def test_result_range(self, rustcore):
        for rope_out in [1.0, 5.0, 30.0, 60.0]:
            for dist in [0.5, 2.0, rope_out * 2.5]:
                ff = rustcore.compute_fall_factor(dist, rope_out)
                assert 0.0 <= ff <= 2.0
