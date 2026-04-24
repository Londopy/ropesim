"""
Unit tests for anchor force distribution.

Key invariant for a 2-bolt self-equalising anchor (sliding-X / quad) at 0°:
  each bolt carries exactly load/2.
"""
import math
import pytest

from ropesim.anchor import (
    AnchorSystem, AnchorType, Bolt, RockType,
)


# ── Pure-Python / geometry checks ─────────────────────────────────────────────

def _sliding_x_ref(load_kn: float, angle_deg: float) -> tuple[float, float]:
    """Reference: F_bolt = load / (2·cos(θ/2))."""
    theta = math.radians(min(angle_deg, 170.0))
    f = load_kn / (2.0 * math.cos(theta / 2))
    return f, f


class TestSlidingXGeometry:
    def test_equal_distribution_at_zero(self):
        fa, fb = _sliding_x_ref(10.0, 0.0)
        assert abs(fa - 5.0) < 1e-9
        assert abs(fb - 5.0) < 1e-9

    def test_force_increases_with_angle(self):
        loads = [_sliding_x_ref(10.0, a)[0] for a in [0, 30, 60, 90, 120]]
        assert all(loads[i] <= loads[i + 1] for i in range(len(loads) - 1))

    def test_60_degree_factor(self):
        # At 60°, each bolt carries load/√3 ≈ 0.577·load
        fa, fb = _sliding_x_ref(10.0, 60.0)
        expected = 10.0 / math.sqrt(3)
        assert abs(fa - expected) < 0.01

    def test_90_degree_factor(self):
        # At 90°, cos(45°) = 1/√2 → each bolt carries load/√2
        fa, _ = _sliding_x_ref(10.0, 90.0)
        expected = 10.0 / math.sqrt(2)
        assert abs(fa - expected) < 0.01

    def test_symmetry(self):
        fa, fb = _sliding_x_ref(8.5, 45.0)
        assert fa == fb


class TestAnchorSystemPython:
    """Tests that can run without the Rust extension (fallback not available for
    distribute — these are integration tests and will skip without Rust)."""

    def test_construction(self):
        a = AnchorSystem(
            AnchorType.SLIDING_X,
            [Bolt(position=(0.0, 0.0)), Bolt(position=(0.3, 0.0))],
        )
        assert len(a.components) == 2
        assert a.is_redundant()

    def test_weakest_component(self):
        bolts = [
            Bolt(rated_mbs_kn=25.0, corrosion_level=0.0),
            Bolt(rated_mbs_kn=25.0, corrosion_level=0.5),  # weaker
        ]
        a = AnchorSystem(AnchorType.SLIDING_X, bolts)
        weak = a.weakest_component()
        assert weak.corrosion_level == 0.5

    def test_single_component_not_redundant(self):
        a = AnchorSystem(AnchorType.SINGLE_POINT, [Bolt()])
        assert not a.is_redundant()

    def test_empty_components_raises(self):
        with pytest.raises(ValueError):
            AnchorSystem(AnchorType.SLIDING_X, [])


@pytest.mark.requires_rust
class TestAnchorDistributionRust:
    def test_sliding_x_equal_at_zero(self, rustcore):
        fa, fb = rustcore.sliding_x_distribution(10.0, 0.0)
        assert abs(fa - 5.0) < 0.001
        assert abs(fb - 5.0) < 0.001

    def test_sliding_x_self_equalising(self, rustcore):
        # Should always be equal on both bolts
        for angle in [0, 30, 60, 90]:
            fa, fb = rustcore.sliding_x_distribution(10.0, float(angle))
            assert abs(fa - fb) < 1e-9

    def test_sliding_x_force_increases_with_angle(self, rustcore):
        forces = [rustcore.sliding_x_distribution(10.0, float(a))[0] for a in [0, 30, 60, 90]]
        assert all(forces[i] <= forces[i + 1] for i in range(len(forces) - 1))

    def test_quad_equal_at_zero(self, rustcore):
        fa, fb = rustcore.quad_anchor_distribution(10.0, 0.0, True)
        assert abs(fa - 5.0) < 0.001
        assert abs(fb - 5.0) < 0.001

    def test_quad_limiter_caps_angle(self, rustcore):
        # With limiter, force at 90° should be no more than force at 60°
        f_60  = rustcore.quad_anchor_distribution(10.0, 60.0,  True)[0]
        f_90  = rustcore.quad_anchor_distribution(10.0, 90.0,  True)[0]
        f_90_no = rustcore.quad_anchor_distribution(10.0, 90.0, False)[0]
        assert f_90 <= f_90_no  # limiter should reduce or equal no-limiter
        assert f_90 == pytest.approx(f_60, rel=0.01)  # clamped to 60°

    def test_anchor_system_load_distribution_rust(self, rustcore):
        a = AnchorSystem(
            AnchorType.SLIDING_X,
            [Bolt(position=(0.0, 0.0)), Bolt(position=(0.3, 0.0))],
        )
        dist = a.load_distribution(8.0, 0.0)
        assert "0" in dist and "1" in dist
        assert abs(dist["0"] - 4.0) < 0.01
        assert abs(dist["1"] - 4.0) < 0.01

    def test_load_sweep_shape(self, rustcore):
        import numpy as np
        a = AnchorSystem(
            AnchorType.SLIDING_X,
            [Bolt(position=(0.0, 0.0)), Bolt(position=(0.5, 0.0))],
        )
        sweep = a.load_sweep(8.0, (-60.0, 60.0), steps=60)
        assert sweep.shape == (60, 2)

    def test_safety_margins_positive(self, rustcore):
        a = AnchorSystem(
            AnchorType.SLIDING_X,
            [Bolt(rated_mbs_kn=25.0, position=(0.0, 0.0)),
             Bolt(rated_mbs_kn=25.0, position=(0.3, 0.0))],
        )
        margins = a.safety_margins(8.0)
        for v in margins.values():
            assert v > 0, f"Safety margin {v} should be positive for a light load"
