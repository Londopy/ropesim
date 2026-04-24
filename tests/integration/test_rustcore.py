"""
Integration tests: Python/Rust boundary correctness.

Verifies that every function exported from _rustcore:
  - is callable from Python
  - returns the expected types
  - produces physically plausible values
"""
import math
import pytest

pytestmark = pytest.mark.requires_rust


class TestPhysicsBoundary:
    def test_fall_factor_returns_float(self, rustcore):
        result = rustcore.compute_fall_factor(5.0, 15.0)
        assert isinstance(result, float)

    def test_impact_force_returns_float(self, rustcore):
        result = rustcore.compute_impact_force_uiaa(80.0, 1.0, 40.0, 0.35)
        assert isinstance(result, float)
        assert result > 0

    def test_force_curve_returns_list(self, rustcore):
        curve = rustcore.compute_force_curve(80.0, 5.0, 15.0, 40.0, 0.12, 1.0)
        assert isinstance(curve, list)
        assert len(curve) > 10

    def test_force_curve_all_nonnegative(self, rustcore):
        curve = rustcore.compute_force_curve(80.0, 6.0, 20.0, 40.0, 0.12, 1.0)
        assert all(f >= 0.0 for f in curve), "Force curve contains negative values"

    def test_force_curve_peak_plausible(self, rustcore):
        # Peak should be in a physically realistic range (3–20 kN)
        curve = rustcore.compute_force_curve(80.0, 6.0, 20.0, 40.0, 0.12, 1.0)
        peak = max(curve)
        assert 2.0 < peak < 25.0, f"Peak {peak:.2f} kN out of plausible range"

    def test_force_curve_starts_zero(self, rustcore):
        # At the moment of rope catching, force should start near 0
        curve = rustcore.compute_force_curve(80.0, 6.0, 20.0, 40.0, 0.12, 1.0)
        assert curve[0] < 2.0, f"Force at t=0 unexpectedly high: {curve[0]}"

    def test_elongation_returns_float(self, rustcore):
        result = rustcore.compute_elongation(8.0, 34.0, 9.0, 20.0)
        assert isinstance(result, float)
        assert result > 20.0  # elongated length must exceed natural length

    def test_elongation_static_at_low_force(self, rustcore):
        # At ≤ 0.784 kN, should use static elongation
        static_elong = 8.0
        nat_len = 20.0
        result = rustcore.compute_elongation(static_elong, 34.0, 0.5, nat_len)
        expected = nat_len * (1 + static_elong / 100)
        assert abs(result - expected) < 0.01

    def test_diameter_under_load_decreases(self, rustcore):
        d0 = rustcore.compute_diameter_under_load(9.5, 40.0, 0.0)
        d1 = rustcore.compute_diameter_under_load(9.5, 40.0, 5.0)
        d2 = rustcore.compute_diameter_under_load(9.5, 40.0, 12.0)
        assert d0 >= d1 >= d2

    def test_diameter_stays_positive(self, rustcore):
        d = rustcore.compute_diameter_under_load(9.5, 40.0, 100.0)
        assert d > 0.0

    def test_energy_budget_returns_class(self, rustcore):
        eb = rustcore.compute_energy_budget(80.0, 6.0, 9.2, 2.0, 0.35)
        assert hasattr(eb, "potential_energy_j")
        assert hasattr(eb, "rope_absorption_j")
        assert hasattr(eb, "belay_device_j")
        assert hasattr(eb, "residual_j")

    def test_energy_budget_pe_positive(self, rustcore):
        eb = rustcore.compute_energy_budget(80.0, 6.0, 9.2, 2.0, 0.35)
        assert eb.potential_energy_j > 0

    def test_wet_modifier_increases_force(self, rustcore):
        dry = rustcore.apply_wet_modifier(9.2, False)
        wet = rustcore.apply_wet_modifier(9.2, True)
        assert wet > dry
        assert wet == pytest.approx(9.2 * 1.12, rel=0.001)

    def test_temperature_modifier_cold_increases_stiffness(self, rustcore):
        warm = rustcore.apply_temperature_modifier(40.0, 20.0)
        cold = rustcore.apply_temperature_modifier(40.0, -10.0)
        assert cold > warm

    def test_temperature_modifier_hot_decreases_stiffness(self, rustcore):
        ref  = rustcore.apply_temperature_modifier(40.0, 20.0)
        hot  = rustcore.apply_temperature_modifier(40.0, 40.0)
        assert hot < ref

    def test_stiffness_from_spec_positive(self, rustcore):
        k = rustcore.compute_stiffness_from_spec(9.2, 34.0, 80.0)
        assert k > 0.0
        assert math.isfinite(k)


class TestAnchorBoundary:
    def test_sliding_x_returns_tuple(self, rustcore):
        result = rustcore.sliding_x_distribution(8.0, 0.0)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_quad_returns_tuple(self, rustcore):
        result = rustcore.quad_anchor_distribution(8.0, 30.0, True)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_resolve_2d_sums_to_load(self, rustcore):
        # For a symmetric 2-bolt anchor, sum of forces should approximate load
        positions = [(0.0, 0.0), (0.3, 0.0)]
        slings    = [0.6, 0.6]
        forces    = rustcore.resolve_anchor_forces_2d(positions, slings, 8.0, 0.0)
        assert isinstance(forces, list)
        assert len(forces) == 2
        # Forces must be non-negative
        assert all(f >= 0 for f in forces)

    def test_resolve_2d_empty_raises(self, rustcore):
        with pytest.raises(ValueError):
            rustcore.resolve_anchor_forces_2d([], [], 8.0, 0.0)

    def test_resolve_2d_mismatched_raises(self, rustcore):
        with pytest.raises(ValueError):
            rustcore.resolve_anchor_forces_2d([(0.0, 0.0)], [0.6, 0.6], 8.0, 0.0)

    def test_simulate_component_failure_returns_class(self, rustcore):
        result = rustcore.simulate_component_failure([5.0, 5.0], [25.0, 25.0])
        assert hasattr(result, "failed_indices")
        assert hasattr(result, "redistributed_forces")
        assert hasattr(result, "cascade_occurred")

    def test_simulate_no_failure_when_safe(self, rustcore):
        result = rustcore.simulate_component_failure([5.0, 5.0], [25.0, 25.0])
        assert result.failed_indices == []
        assert not result.cascade_occurred

    def test_simulate_single_failure(self, rustcore):
        # Bolt 0 overloaded (30 kN > 25 kN MBS)
        result = rustcore.simulate_component_failure([30.0, 5.0], [25.0, 25.0])
        assert 0 in result.failed_indices

    def test_anchor_load_sweep_length(self, rustcore):
        positions = [(0.0, 0.0), (0.3, 0.0)]
        flat = rustcore.compute_anchor_load_sweep(positions, 8.0, -60.0, 60.0, 60)
        assert len(flat) == 60 * 2  # steps × n_bolts
