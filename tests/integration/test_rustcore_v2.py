"""
Integration tests: v0.2.0 Rust extensions.

Tests the new functions added in v0.2.0:
  - compute_haul_system_force / HaulSystem
  - compute_top_rope_impact
  - compute_rappel_load
  - compute_static_elongation_under_weight
"""
import math
import pytest

pytestmark = pytest.mark.requires_rust


# ── HaulSystem enum ───────────────────────────────────────────────────────────

class TestHaulSystemEnum:
    def test_three_to_one_exists(self, rustcore):
        assert hasattr(rustcore, "HaulSystem")
        assert hasattr(rustcore.HaulSystem, "ThreeToOne")

    def test_five_to_one_exists(self, rustcore):
        assert hasattr(rustcore.HaulSystem, "FiveToOne")

    def test_six_to_one_exists(self, rustcore):
        assert hasattr(rustcore.HaulSystem, "SixToOne")

    def test_piggyback_exists(self, rustcore):
        assert hasattr(rustcore.HaulSystem, "Piggyback")


# ── compute_haul_system_force ─────────────────────────────────────────────────

class TestComputeHaulSystemForce:
    def test_returns_haul_result(self, rustcore):
        result = rustcore.compute_haul_system_force(
            load_kg=80.0,
            system=rustcore.HaulSystem.ThreeToOne,
            friction_loss=0.0,
        )
        assert result is not None

    def test_haul_result_has_expected_fields(self, rustcore):
        result = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.ThreeToOne, 0.0)
        assert hasattr(result, "theoretical_ma")
        assert hasattr(result, "actual_ma")
        assert hasattr(result, "hauler_effort_n")
        assert hasattr(result, "anchor_load_n")

    def test_3to1_theoretical_ma(self, rustcore):
        result = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.ThreeToOne, 0.0)
        assert result.theoretical_ma == pytest.approx(3.0, abs=0.1)

    def test_5to1_theoretical_ma(self, rustcore):
        result = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.FiveToOne, 0.0)
        assert result.theoretical_ma == pytest.approx(5.0, abs=0.1)

    def test_6to1_theoretical_ma(self, rustcore):
        result = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.SixToOne, 0.0)
        assert result.theoretical_ma == pytest.approx(6.0, abs=0.1)

    def test_friction_reduces_actual_ma(self, rustcore):
        no_friction  = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.ThreeToOne, 0.0)
        with_friction = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.ThreeToOne, 0.15)
        assert with_friction.actual_ma < no_friction.actual_ma

    def test_hauler_effort_less_than_load(self, rustcore):
        load_n = 80.0 * 9.81
        result = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.ThreeToOne, 0.0)
        assert result.hauler_effort_n < load_n

    def test_higher_ma_less_effort(self, rustcore):
        r3 = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.ThreeToOne, 0.0)
        r5 = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.FiveToOne, 0.0)
        assert r5.hauler_effort_n < r3.hauler_effort_n

    def test_anchor_load_greater_than_weight(self, rustcore):
        # The anchor always bears more than just the load weight
        load_n = 80.0 * 9.81
        result = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.ThreeToOne, 0.0)
        assert result.anchor_load_n >= load_n - 1.0  # within 1 N

    def test_effort_positive(self, rustcore):
        result = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.ThreeToOne, 0.12)
        assert result.hauler_effort_n > 0.0

    def test_heavier_load_more_effort(self, rustcore):
        r60 = rustcore.compute_haul_system_force(60.0, rustcore.HaulSystem.ThreeToOne, 0.0)
        r90 = rustcore.compute_haul_system_force(90.0, rustcore.HaulSystem.ThreeToOne, 0.0)
        assert r90.hauler_effort_n > r60.hauler_effort_n

    def test_piggyback_high_ma(self, rustcore):
        result = rustcore.compute_haul_system_force(80.0, rustcore.HaulSystem.Piggyback, 0.0)
        assert result.theoretical_ma >= 6.0


# ── compute_top_rope_impact ───────────────────────────────────────────────────

class TestComputeTopRopeImpact:
    def test_returns_float(self, rustcore):
        result = rustcore.compute_top_rope_impact(
            stiffness_kn=18.0,
            mass_kg=75.0,
            slack_m=0.5,
            rope_length_m=25.0,
            friction=0.35,
        )
        assert isinstance(result, float)

    def test_positive_force(self, rustcore):
        result = rustcore.compute_top_rope_impact(18.0, 75.0, 0.5, 25.0, 0.35)
        assert result > 0.0

    def test_plausible_range(self, rustcore):
        result = rustcore.compute_top_rope_impact(18.0, 75.0, 0.5, 25.0, 0.35)
        assert 0.5 < result < 15.0, f"Top-rope impact {result:.2f} kN out of range"

    def test_more_slack_higher_force(self, rustcore):
        low  = rustcore.compute_top_rope_impact(18.0, 75.0, 0.2, 25.0, 0.35)
        high = rustcore.compute_top_rope_impact(18.0, 75.0, 2.0, 25.0, 0.35)
        assert high > low

    def test_heavier_climber_higher_force(self, rustcore):
        light = rustcore.compute_top_rope_impact(18.0, 55.0, 0.5, 25.0, 0.35)
        heavy = rustcore.compute_top_rope_impact(18.0, 90.0, 0.5, 25.0, 0.35)
        assert heavy > light

    def test_zero_slack_low_force(self, rustcore):
        result = rustcore.compute_top_rope_impact(18.0, 75.0, 0.0, 25.0, 0.35)
        assert result < rustcore.compute_top_rope_impact(18.0, 75.0, 1.0, 25.0, 0.35)

    def test_higher_friction_lower_force(self, rustcore):
        low_f  = rustcore.compute_top_rope_impact(18.0, 75.0, 0.5, 25.0, 0.1)
        high_f = rustcore.compute_top_rope_impact(18.0, 75.0, 0.5, 25.0, 0.6)
        assert high_f < low_f


# ── compute_rappel_load ───────────────────────────────────────────────────────

class TestComputeRappelLoad:
    def test_returns_float(self, rustcore):
        result = rustcore.compute_rappel_load(
            mass_kg=80.0,
            friction=0.25,
            speed_mps=1.2,
            sudden_stop=False,
        )
        assert isinstance(result, float)

    def test_positive_load(self, rustcore):
        result = rustcore.compute_rappel_load(80.0, 0.25, 1.2, False)
        assert result > 0.0

    def test_sudden_stop_higher_load(self, rustcore):
        normal = rustcore.compute_rappel_load(80.0, 0.25, 1.2, False)
        stop   = rustcore.compute_rappel_load(80.0, 0.25, 1.2, True)
        assert stop > normal

    def test_heavier_climber_higher_load(self, rustcore):
        light = rustcore.compute_rappel_load(60.0, 0.25, 1.0, False)
        heavy = rustcore.compute_rappel_load(90.0, 0.25, 1.0, False)
        assert heavy > light

    def test_static_rappel_plausible(self, rustcore):
        # At rest (speed=0, no sudden stop), load should be close to body weight
        weight_kn = 80.0 * 9.81 / 1000
        result = rustcore.compute_rappel_load(80.0, 0.0, 0.0, False)
        assert result == pytest.approx(weight_kn, rel=0.10)

    def test_finite_result(self, rustcore):
        result = rustcore.compute_rappel_load(80.0, 0.25, 1.2, False)
        assert math.isfinite(result)


# ── compute_static_elongation_under_weight ────────────────────────────────────

class TestComputeStaticElongation:
    def test_returns_float(self, rustcore):
        result = rustcore.compute_static_elongation_under_weight(
            static_elong_pct=8.0,
            load_kg=80.0,
            length_m=30.0,
        )
        assert isinstance(result, float)

    def test_elongation_positive(self, rustcore):
        result = rustcore.compute_static_elongation_under_weight(8.0, 80.0, 30.0)
        assert result > 0.0

    def test_longer_rope_more_stretch(self, rustcore):
        short = rustcore.compute_static_elongation_under_weight(8.0, 80.0, 10.0)
        long_ = rustcore.compute_static_elongation_under_weight(8.0, 80.0, 50.0)
        assert long_ > short

    def test_higher_pct_more_stretch(self, rustcore):
        low  = rustcore.compute_static_elongation_under_weight(4.0, 80.0, 30.0)
        high = rustcore.compute_static_elongation_under_weight(12.0, 80.0, 30.0)
        assert high > low

    def test_heavier_load_more_stretch(self, rustcore):
        light = rustcore.compute_static_elongation_under_weight(8.0, 40.0, 30.0)
        heavy = rustcore.compute_static_elongation_under_weight(8.0, 120.0, 30.0)
        assert heavy > light

    def test_proportional_to_length(self, rustcore):
        e10 = rustcore.compute_static_elongation_under_weight(8.0, 80.0, 10.0)
        e20 = rustcore.compute_static_elongation_under_weight(8.0, 80.0, 20.0)
        assert e20 == pytest.approx(e10 * 2.0, rel=0.05)
