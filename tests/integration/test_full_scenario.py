"""
Integration tests: end-to-end simulation pipeline.

Exercises the full chain: Rope → FallConditions → Fall.simulate() → FallResult,
and AnchorSystem → load_distribution / simulate_failure.
"""
import pytest
import numpy as np

pytestmark = pytest.mark.requires_rust

from ropesim.rope import Rope, RopeSpec, RopeType, RopeStandard
from ropesim.fall import Fall, FallConditions, BelayDevice, FallResult
from ropesim.anchor import (
    AnchorSystem, AnchorType, Bolt, Cam, Nut, Sling,
    RockType, CamPlacement, BoltType, SlingMaterial,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def standard_spec():
    return RopeSpec(
        name="Integration Test Rope 9.5",
        manufacturer="TestCo",
        rope_type=RopeType.SINGLE,
        standard=RopeStandard.BOTH,
        diameter_mm=9.5,
        weight_gpm=60.0,
        sheath_percentage=40.0,
        impact_force_kn=9.2,
        number_of_falls=7,
        static_elongation_pct=8.0,
        dynamic_elongation_pct=34.0,
        dry_treated=False,
    )


@pytest.fixture
def standard_conditions(standard_spec):
    return FallConditions(
        climber_mass_kg=80.0,
        fall_distance_m=6.0,
        rope_out_m=20.0,
        belay_device=BelayDevice.ATC,
        rope=standard_spec,
        is_wet=False,
        temperature_celsius=20.0,
        timestep_ms=1.0,
        damping_ratio=0.12,
    )


# ── Fall simulation ───────────────────────────────────────────────────────────

class TestFallSimulation:
    def test_simulate_returns_result(self, standard_conditions):
        result = Fall(standard_conditions).simulate()
        assert isinstance(result, FallResult)

    def test_fall_factor_matches_conditions(self, standard_conditions):
        result = Fall(standard_conditions).simulate()
        expected_ff = 6.0 / 20.0  # 0.30
        assert abs(result.fall_factor - expected_ff) < 0.001

    def test_peak_force_positive(self, standard_conditions):
        result = Fall(standard_conditions).simulate()
        assert result.peak_force_kn > 0.0

    def test_peak_force_plausible_range(self, standard_conditions):
        result = Fall(standard_conditions).simulate()
        assert 2.0 < result.peak_force_kn < 15.0, \
            f"Peak force {result.peak_force_kn:.2f} kN out of range"

    def test_lbf_conversion_consistent(self, standard_conditions):
        result = Fall(standard_conditions).simulate()
        from ropesim.units import Units
        expected_lbf = Units.kn_to_lbf(result.peak_force_kn)
        assert abs(result.peak_force_lbf - expected_lbf) < 1.0

    def test_force_curve_is_list_of_floats(self, standard_conditions):
        result = Fall(standard_conditions).simulate()
        assert isinstance(result.force_curve, list)
        assert all(isinstance(v, float) for v in result.force_curve)

    def test_force_curve_peak_consistent(self, standard_conditions):
        result = Fall(standard_conditions).simulate()
        curve_peak = max(result.force_curve)
        # Curve peak should be within 50% of analytic peak (two different models)
        assert abs(curve_peak - result.peak_force_kn) / result.peak_force_kn < 0.50

    def test_elongation_positive(self, standard_conditions):
        result = Fall(standard_conditions).simulate()
        assert result.elongation_m > 0.0

    def test_energy_budget_positive_pe(self, standard_conditions):
        result = Fall(standard_conditions).simulate()
        assert result.energy_budget.potential_energy_j > 0.0

    def test_energy_budget_rope_absorbs(self, standard_conditions):
        result = Fall(standard_conditions).simulate()
        assert result.energy_budget.rope_absorption_j > 0.0

    def test_grigri_lower_force_than_atc(self, standard_spec):
        """Grigri has higher friction → lower force transmitted to anchor."""
        cond_atc = FallConditions(
            climber_mass_kg=80.0, fall_distance_m=6.0, rope_out_m=20.0,
            belay_device=BelayDevice.ATC, rope=standard_spec
        )
        cond_grigri = FallConditions(
            climber_mass_kg=80.0, fall_distance_m=6.0, rope_out_m=20.0,
            belay_device=BelayDevice.GRIGRI, rope=standard_spec
        )
        r_atc    = Fall(cond_atc).simulate()
        r_grigri = Fall(cond_grigri).simulate()
        assert r_grigri.peak_force_kn < r_atc.peak_force_kn

    def test_wet_rope_higher_force(self, standard_spec):
        dry = FallConditions(
            climber_mass_kg=80.0, fall_distance_m=6.0, rope_out_m=20.0,
            belay_device=BelayDevice.ATC, rope=standard_spec, is_wet=False
        )
        wet = FallConditions(
            climber_mass_kg=80.0, fall_distance_m=6.0, rope_out_m=20.0,
            belay_device=BelayDevice.ATC, rope=standard_spec, is_wet=True
        )
        assert Fall(wet).simulate().peak_force_kn > Fall(dry).simulate().peak_force_kn

    def test_higher_ff_higher_force(self, standard_spec):
        c_low = FallConditions(
            climber_mass_kg=80.0, fall_distance_m=3.0, rope_out_m=30.0,
            belay_device=BelayDevice.ATC, rope=standard_spec
        )
        c_high = FallConditions(
            climber_mass_kg=80.0, fall_distance_m=10.0, rope_out_m=10.0,
            belay_device=BelayDevice.ATC, rope=standard_spec
        )
        assert Fall(c_high).simulate().peak_force_kn > Fall(c_low).simulate().peak_force_kn

    def test_warnings_list(self, standard_conditions):
        result = Fall(standard_conditions).simulate()
        assert isinstance(result.warnings, list)

    def test_high_ff_generates_warning(self, standard_spec):
        cond = FallConditions(
            climber_mass_kg=80.0, fall_distance_m=15.0, rope_out_m=10.0,  # ff=1.5
            belay_device=BelayDevice.ATC, rope=standard_spec
        )
        result = Fall(cond).simulate()
        assert any("fall factor" in w.lower() or "ff" in w.lower() for w in result.warnings)

    def test_force_curve_numpy(self, standard_conditions):
        fall = Fall(standard_conditions)
        arr = fall.force_curve_numpy()
        assert isinstance(arr, np.ndarray)
        assert arr.ndim == 1
        assert len(arr) > 0


# ── Anchor system ─────────────────────────────────────────────────────────────

class TestAnchorSystemIntegration:
    def test_sliding_x_full_pipeline(self):
        anchor = AnchorSystem(
            AnchorType.SLIDING_X,
            [
                Bolt(rated_mbs_kn=25.0, position=(0.0, 0.0)),
                Bolt(rated_mbs_kn=25.0, position=(0.3, 0.0)),
            ],
        )
        dist = anchor.load_distribution(8.0, 0.0)
        assert len(dist) == 2
        assert abs(dist["0"] - 4.0) < 0.01
        assert abs(dist["1"] - 4.0) < 0.01

    def test_quad_anchor_full_pipeline(self):
        anchor = AnchorSystem(
            AnchorType.QUAD,
            [
                Bolt(rated_mbs_kn=25.0, position=(0.0, 0.0)),
                Bolt(rated_mbs_kn=25.0, position=(0.4, 0.0)),
            ],
        )
        dist = anchor.load_distribution(8.0, 0.0)
        assert abs(dist["0"] - 4.0) < 0.01

    def test_safety_margins_safe_for_light_load(self):
        anchor = AnchorSystem(
            AnchorType.SLIDING_X,
            [Bolt(rated_mbs_kn=25.0), Bolt(rated_mbs_kn=25.0)],
        )
        margins = anchor.safety_margins(8.0)
        for v in margins.values():
            assert v > 0.0

    def test_simulate_failure_no_cascade_light_load(self):
        anchor = AnchorSystem(
            AnchorType.SLIDING_X,
            [Bolt(rated_mbs_kn=25.0), Bolt(rated_mbs_kn=25.0)],
        )
        result = anchor.simulate_failure(8.0)
        assert result.failed_indices == []
        assert not result.cascade_occurred

    def test_simulate_failure_with_overload(self):
        """An anchor massively overloaded should fail."""
        anchor = AnchorSystem(
            AnchorType.SLIDING_X,
            [
                Bolt(rated_mbs_kn=5.0, position=(0.0, 0.0)),   # weak bolt
                Bolt(rated_mbs_kn=25.0, position=(0.3, 0.0)),
            ],
        )
        result = anchor.simulate_failure(15.0)  # 15 kN on a 5 kN bolt
        assert len(result.failed_indices) > 0

    def test_cam_effective_mbs_below_rated(self):
        # A cam at marginal placement in sandstone should have reduced MBS
        cam = Cam(
            rated_mbs_kn=14.0,
            placement=CamPlacement.MARGINAL,
            rock_type=RockType.SANDSTONE,
        )
        assert cam.effective_mbs() < 14.0

    def test_nut_perfect_granite(self):
        nut = Nut(rated_mbs_kn=12.0, placement=CamPlacement.PERFECT, rock_type=RockType.GRANITE)
        assert nut.effective_mbs() == pytest.approx(12.0, rel=0.01)

    def test_corroded_bolt_lower_mbs(self):
        clean  = Bolt(rated_mbs_kn=25.0, corrosion_level=0.0)
        rusty  = Bolt(rated_mbs_kn=25.0, corrosion_level=0.8)
        assert rusty.effective_mbs() < clean.effective_mbs()

    def test_aged_bolt_lower_mbs(self):
        new_bolt = Bolt(rated_mbs_kn=25.0, age_years=0.0)
        old_bolt = Bolt(rated_mbs_kn=25.0, age_years=20.0)
        assert old_bolt.effective_mbs() < new_bolt.effective_mbs()

    def test_dyneema_lower_elongation_than_nylon(self):
        nylon   = Sling(material=SlingMaterial.NYLON)
        dyneema = Sling(material=SlingMaterial.DYNEEMA)
        assert dyneema.elongation_factor() < nylon.elongation_factor()

    def test_uv_degraded_sling_lower_mbs(self):
        fresh = Sling(rated_mbs_kn=22.0, uv_degradation=0.0)
        faded = Sling(rated_mbs_kn=22.0, uv_degradation=1.0)
        assert faded.effective_mbs() < fresh.effective_mbs()


# ── Database-to-simulation roundtrip ─────────────────────────────────────────

class TestDatabaseToSimulation:
    def test_simulate_with_bundled_rope(self):
        rope = Rope.from_db("Beal Opera 8.5 Dry")
        conditions = FallConditions(
            climber_mass_kg=75.0,
            fall_distance_m=4.0,
            rope_out_m=18.0,
            belay_device=BelayDevice.GRIGRI,
            rope=rope.spec,
        )
        result = Fall(conditions).simulate()
        assert result.peak_force_kn > 0
        assert len(result.force_curve) > 0

    def test_simulate_multiple_ropes(self):
        """Each bundled rope should produce a valid simulation result."""
        from ropesim.rope import RopeDatabase
        db = RopeDatabase()
        for spec in db.load()[:5]:  # test first 5 for speed
            cond = FallConditions(
                climber_mass_kg=80.0,
                fall_distance_m=5.0,
                rope_out_m=15.0,
                belay_device=BelayDevice.ATC,
                rope=spec,
            )
            result = Fall(cond).simulate()
            assert result.peak_force_kn > 0, f"Failed for {spec.name}"
            assert 0 <= result.fall_factor <= 2.0
