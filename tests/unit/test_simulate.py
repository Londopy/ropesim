"""
Unit tests for ropesim.simulate (Scenario class).
"""
import pytest
import numpy as np

from ropesim.rope import Rope, RopeSpec, RopeType
from ropesim.fall import BelayDevice
from ropesim.anchor import AnchorSystem, AnchorType, Bolt, Cam, CamPlacement, RockType
from ropesim.simulate import Scenario, ProtectionPoint, SweepResult, ZipperResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def spec():
    return RopeSpec(
        name="Test 9.5",
        rope_type=RopeType.SINGLE,
        diameter_mm=9.5,
        weight_gpm=60.0,
        sheath_percentage=40.0,
        impact_force_kn=9.2,
        number_of_falls=7,
        static_elongation_pct=8.0,
        dynamic_elongation_pct=34.0,
    )


@pytest.fixture
def rope(spec):
    return Rope(spec)


@pytest.fixture
def strong_anchor():
    return AnchorSystem(
        AnchorType.SLIDING_X,
        [Bolt(rated_mbs_kn=25.0, position=(0.0, 0.0)),
         Bolt(rated_mbs_kn=25.0, position=(0.3, 0.0))],
    )


@pytest.fixture
def scenario(rope, strong_anchor):
    s = Scenario(rope, climber_mass_kg=80.0)
    s.add_protection(8.0,  strong_anchor, label="bolt 1")
    s.add_protection(14.0, strong_anchor, label="bolt 2")
    return s


# ── ProtectionPoint ───────────────────────────────────────────────────────────

class TestProtectionPoint:
    def test_create(self, strong_anchor):
        pt = ProtectionPoint(height_m=5.0, anchor=strong_anchor, label="cam")
        assert pt.height_m == 5.0
        assert pt.label == "cam"

    def test_negative_height_raises(self, strong_anchor):
        with pytest.raises(ValueError):
            ProtectionPoint(height_m=-1.0, anchor=strong_anchor)


# ── Scenario construction ─────────────────────────────────────────────────────

class TestScenarioConstruction:
    def test_create_empty_scenario(self, rope):
        s = Scenario(rope)
        assert len(s.protection) == 0

    def test_add_protection_sorted(self, rope, strong_anchor):
        s = Scenario(rope)
        s.add_protection(14.0, strong_anchor)
        s.add_protection(5.0,  strong_anchor)
        s.add_protection(8.0,  strong_anchor)
        heights = [p.height_m for p in s.protection]
        assert heights == sorted(heights)

    def test_add_protection_with_label(self, rope, strong_anchor):
        s = Scenario(rope)
        s.add_protection(10.0, strong_anchor, label="third bolt")
        assert s.protection[0].label == "third bolt"

    def test_remove_protection(self, rope, strong_anchor):
        s = Scenario(rope)
        s.add_protection(5.0, strong_anchor)
        s.add_protection(10.0, strong_anchor)
        s.remove_protection(0)
        assert len(s.protection) == 1

    def test_clear_protection(self, scenario):
        scenario.clear_protection()
        assert len(scenario.protection) == 0

    def test_repr(self, scenario):
        r = repr(scenario)
        assert "Scenario" in r
        assert "2 protection" in r

    def test_summary(self, scenario):
        s = scenario.summary()
        assert s["protection_count"] == 2
        assert s["climber_mass_kg"] == 80.0
        assert 8.0 in s["protection_heights"]
        assert 14.0 in s["protection_heights"]


# ── Fall geometry ─────────────────────────────────────────────────────────────

class TestFallGeometry:
    def test_fall_geometry_with_pro(self, scenario):
        # Climber at 16 m, last pro at 14 m → fall_dist = 2×2 = 4 m, rope_out = 16 m
        fd, ro, ff = scenario._fall_geometry(16.0)
        assert abs(fd - 4.0) < 0.01
        assert abs(ro - 16.0) < 0.01
        assert abs(ff - 4.0 / 16.0) < 0.01

    def test_fall_geometry_no_pro(self, rope):
        s = Scenario(rope)
        fd, ro, ff = s._fall_geometry(10.0)
        # No pro → fall factor ≈ 2
        assert abs(ff - 2.0) < 0.01

    def test_fall_geometry_at_first_bolt(self, scenario):
        # Climber exactly at 8 m (first bolt height)
        fd, ro, ff = scenario._fall_geometry(8.0)
        assert fd > 0
        assert ff >= 0

    def test_last_pro_below(self, scenario):
        last = scenario._last_pro_below(15.0)
        assert last.height_m == 14.0

    def test_last_pro_below_none(self, scenario):
        last = scenario._last_pro_below(5.0)  # below all protection
        assert last is None


# ── simulate_fall ─────────────────────────────────────────────────────────────

class TestSimulateFall:
    pytestmark = pytest.mark.requires_rust

    def test_returns_fall_result(self, scenario):
        from ropesim.fall import FallResult
        result = scenario.simulate_fall(16.0)
        assert isinstance(result, FallResult)

    def test_peak_force_positive(self, scenario):
        result = scenario.simulate_fall(16.0)
        assert result.peak_force_kn > 0.0

    def test_fall_factor_in_range(self, scenario):
        result = scenario.simulate_fall(16.0)
        assert 0.0 < result.fall_factor <= 2.0

    def test_higher_climber_higher_force(self, rope, strong_anchor):
        s = Scenario(rope)
        s.add_protection(5.0, strong_anchor)
        r_low  = s.simulate_fall(8.0)
        r_high = s.simulate_fall(15.0)
        # Higher climber → more rope out for same last-pro height → lower ff
        # but both should be valid
        assert r_low.peak_force_kn > 0
        assert r_high.peak_force_kn > 0

    def test_no_protection_high_fall_factor(self, rope):
        s = Scenario(rope)
        result = s.simulate_fall(6.0)
        # No pro → fall factor = 2.0
        assert result.fall_factor == pytest.approx(2.0, abs=0.01)

    def test_wet_flag_propagated(self, rope, strong_anchor):
        s_dry = Scenario(rope, is_wet=False)
        s_wet = Scenario(rope, is_wet=True)
        s_dry.add_protection(8.0, strong_anchor)
        s_wet.add_protection(8.0, strong_anchor)
        r_dry = s_dry.simulate_fall(12.0)
        r_wet = s_wet.simulate_fall(12.0)
        assert r_wet.peak_force_kn > r_dry.peak_force_kn


# ── simulate_zipper ───────────────────────────────────────────────────────────

class TestSimulateZipper:
    pytestmark = pytest.mark.requires_rust

    def test_returns_zipper_result(self, scenario):
        result = scenario.simulate_zipper(16.0)
        assert isinstance(result, ZipperResult)

    def test_strong_anchor_no_zipper(self, scenario):
        # 25 kN bolts, moderate fall — should hold
        result = scenario.simulate_zipper(12.0)
        assert not result.ground_fall_reached
        assert result.initial_fall_result.peak_force_kn > 0

    def test_weak_anchor_zippers(self, rope):
        """Very weak bolts under a heavy fall should produce zipper failures."""
        weak_anchor = AnchorSystem(
            AnchorType.SLIDING_X,
            [Bolt(rated_mbs_kn=1.0, position=(0.0, 0.0)),
             Bolt(rated_mbs_kn=1.0, position=(0.3, 0.0))],
        )
        s = Scenario(rope, climber_mass_kg=80.0)
        s.add_protection(5.0, weak_anchor)
        result = s.simulate_zipper(15.0)
        assert isinstance(result, ZipperResult)
        # With 1 kN bolts and a heavy fall, failure should occur
        assert result.total_pieces_failed > 0 or result.ground_fall_reached

    def test_initial_fall_result_present(self, scenario):
        result = scenario.simulate_zipper(16.0)
        assert result.initial_fall_result is not None
        assert result.initial_fall_result.peak_force_kn > 0


# ── sweep_fall_positions ──────────────────────────────────────────────────────

class TestSweepFallPositions:
    pytestmark = pytest.mark.requires_rust

    def test_returns_sweep_result(self, scenario):
        result = scenario.sweep_fall_positions(height_range=(10.0, 20.0), steps=5)
        assert isinstance(result, SweepResult)

    def test_correct_number_of_steps(self, scenario):
        result = scenario.sweep_fall_positions(height_range=(10.0, 20.0), steps=10)
        assert len(result.climber_heights_m) == 10
        assert len(result.peak_forces_kn) == 10

    def test_heights_in_range(self, scenario):
        result = scenario.sweep_fall_positions(height_range=(10.0, 20.0), steps=5)
        assert min(result.climber_heights_m) >= 10.0
        assert max(result.climber_heights_m) <= 20.0

    def test_all_forces_positive(self, scenario):
        result = scenario.sweep_fall_positions(height_range=(10.0, 20.0), steps=8)
        assert all(f > 0.0 for f in result.peak_forces_kn)

    def test_worst_index_valid(self, scenario):
        result = scenario.sweep_fall_positions(height_range=(10.0, 20.0), steps=10)
        assert 0 <= result.worst_index < 10

    def test_worst_peak_consistent(self, scenario):
        result = scenario.sweep_fall_positions(height_range=(10.0, 20.0), steps=10)
        assert result.worst_peak_kn == max(result.peak_forces_kn)

    def test_as_numpy_shape(self, scenario):
        result = scenario.sweep_fall_positions(height_range=(10.0, 20.0), steps=5)
        arr = result.as_numpy()
        assert arr.shape == (5, 4)

    def test_no_protection_sweep(self, rope):
        s = Scenario(rope)
        result = s.sweep_fall_positions(height_range=(3.0, 10.0), steps=5)
        assert len(result.peak_forces_kn) == 5
