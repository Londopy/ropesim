"""
Unit tests for guide-mode self-locking belay device friction model.
Tests: BelayDevice variants, is_guide_mode, compute_effective_friction,
solve_guide_mode_friction, GUIDE_MODE_LOCKING_PARAMS, FallResult.guide_mode_used.
"""
import pytest

from ropesim.fall import (
    BelayDevice,
    FallConditions,
    Fall,
    GUIDE_MODE_LOCKING_PARAMS,
    GUIDE_MODE_DEVICES,
    is_guide_mode,
    compute_effective_friction,
    solve_guide_mode_friction,
    BELAY_FRICTION_COEFFICIENTS as BELAY_FRICTION,
)
from ropesim.rope import RopeSpec, RopeType


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def rope_spec():
    return RopeSpec(
        name="Guide Test 9.5",
        rope_type=RopeType.SINGLE,
        diameter_mm=9.5,
        weight_gpm=60.0,
        sheath_percentage=40.0,
        impact_force_kn=9.2,
        number_of_falls=7,
        static_elongation_pct=8.0,
        dynamic_elongation_pct=34.0,
    )


# ── BelayDevice enum completeness ─────────────────────────────────────────────

class TestBelayDeviceEnum:
    def test_guide_mode_devices_exist(self):
        assert hasattr(BelayDevice, "REVERSO_GUIDE")
        assert hasattr(BelayDevice, "MEGAJUL")
        assert hasattr(BelayDevice, "GIGA_JUL")
        assert hasattr(BelayDevice, "CLICK_UP")
        assert hasattr(BelayDevice, "I_DEVICE")
        assert hasattr(BelayDevice, "SUM")

    def test_classic_devices_still_present(self):
        assert hasattr(BelayDevice, "ATC")
        assert hasattr(BelayDevice, "GRIGRI")
        assert hasattr(BelayDevice, "MUNTER")
        assert hasattr(BelayDevice, "REVERSO")

    def test_all_guide_devices_in_friction_table(self):
        guide_devices = [
            BelayDevice.REVERSO_GUIDE,
            BelayDevice.MEGAJUL,
            BelayDevice.GIGA_JUL,
            BelayDevice.CLICK_UP,
            BelayDevice.I_DEVICE,
            BelayDevice.SUM,
        ]
        for d in guide_devices:
            assert d in BELAY_FRICTION, f"{d} missing from BELAY_FRICTION"

    def test_all_guide_devices_in_locking_params(self):
        guide_devices = [
            BelayDevice.REVERSO_GUIDE,
            BelayDevice.MEGAJUL,
            BelayDevice.GIGA_JUL,
            BelayDevice.CLICK_UP,
            BelayDevice.I_DEVICE,
            BelayDevice.SUM,
        ]
        for d in guide_devices:
            assert d in GUIDE_MODE_LOCKING_PARAMS, f"{d} missing from GUIDE_MODE_LOCKING_PARAMS"


# ── is_guide_mode ─────────────────────────────────────────────────────────────

class TestIsGuideMode:
    def test_reverso_guide_is_guide_mode(self):
        assert is_guide_mode(BelayDevice.REVERSO_GUIDE) is True

    def test_megajul_is_guide_mode(self):
        assert is_guide_mode(BelayDevice.MEGAJUL) is True

    def test_giga_jul_is_guide_mode(self):
        assert is_guide_mode(BelayDevice.GIGA_JUL) is True

    def test_click_up_is_guide_mode(self):
        assert is_guide_mode(BelayDevice.CLICK_UP) is True

    def test_i_device_is_guide_mode(self):
        assert is_guide_mode(BelayDevice.I_DEVICE) is True

    def test_sum_is_guide_mode(self):
        assert is_guide_mode(BelayDevice.SUM) is True

    def test_atc_not_guide_mode(self):
        assert is_guide_mode(BelayDevice.ATC) is False

    def test_grigri_not_guide_mode(self):
        assert is_guide_mode(BelayDevice.GRIGRI) is False

    def test_munter_not_guide_mode(self):
        assert is_guide_mode(BelayDevice.MUNTER) is False

    def test_reverso_not_guide_mode(self):
        assert is_guide_mode(BelayDevice.REVERSO) is False


# ── compute_effective_friction ────────────────────────────────────────────────

class TestComputeEffectiveFriction:
    def test_returns_float(self):
        mu = compute_effective_friction(BelayDevice.REVERSO_GUIDE, 6.0)
        assert isinstance(mu, float)

    def test_increases_with_force(self):
        d = BelayDevice.REVERSO_GUIDE
        mu_low  = compute_effective_friction(d, 2.0)
        mu_mid  = compute_effective_friction(d, 6.0)
        mu_high = compute_effective_friction(d, 12.0)
        assert mu_low < mu_mid < mu_high

    def test_capped_at_mu_max(self):
        d = BelayDevice.REVERSO_GUIDE
        mu_max = GUIDE_MODE_LOCKING_PARAMS[d][2]
        mu = compute_effective_friction(d, 999.0)
        assert mu <= mu_max + 1e-9

    def test_base_friction_at_zero_force(self):
        d = BelayDevice.MEGAJUL
        mu_base = GUIDE_MODE_LOCKING_PARAMS[d][0]
        mu = compute_effective_friction(d, 0.0)
        assert mu == pytest.approx(mu_base, rel=0.01)

    def test_non_guide_device_returns_fixed_friction(self):
        mu = compute_effective_friction(BelayDevice.ATC, 6.0)
        assert mu == pytest.approx(BELAY_FRICTION[BelayDevice.ATC], rel=0.01)

    def test_all_guide_devices_return_positive(self):
        for d in GUIDE_MODE_DEVICES:
            mu = compute_effective_friction(d, 5.0)
            assert mu > 0.0, f"{d} returned non-positive friction"

    def test_all_guide_devices_bounded(self):
        for d in GUIDE_MODE_DEVICES:
            mu_max = GUIDE_MODE_LOCKING_PARAMS[d][2]
            assert compute_effective_friction(d, 100.0) <= mu_max + 1e-9


# ── solve_guide_mode_friction ─────────────────────────────────────────────────

class TestSolveGuideModeFriction:
    def test_returns_tuple(self):
        result = solve_guide_mode_friction(
            BelayDevice.REVERSO_GUIDE, 80.0, 0.5, 20.0
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_friction_in_valid_range(self):
        mu, peak = solve_guide_mode_friction(
            BelayDevice.REVERSO_GUIDE, 80.0, 0.5, 20.0
        )
        assert 0.0 < mu <= 1.0

    def test_peak_force_positive(self):
        mu, peak = solve_guide_mode_friction(
            BelayDevice.REVERSO_GUIDE, 80.0, 0.5, 20.0
        )
        assert peak > 0.0

    def test_self_consistency(self):
        device = BelayDevice.REVERSO_GUIDE
        mu, peak = solve_guide_mode_friction(device, 80.0, 0.5, 20.0)
        expected_mu = compute_effective_friction(device, peak)
        assert abs(mu - expected_mu) < 0.01


# ── GUIDE_MODE_LOCKING_PARAMS table ──────────────────────────────────────────

class TestLockingParamsTable:
    def test_all_params_have_three_values(self):
        for device, params in GUIDE_MODE_LOCKING_PARAMS.items():
            assert len(params) == 3, f"{device} params should be (mu_base, k_lock, mu_max)"

    def test_mu_base_less_than_mu_max(self):
        for device, (mu_base, k_lock, mu_max) in GUIDE_MODE_LOCKING_PARAMS.items():
            assert mu_base < mu_max, f"{device}: mu_base >= mu_max"

    def test_k_lock_positive(self):
        for device, (mu_base, k_lock, mu_max) in GUIDE_MODE_LOCKING_PARAMS.items():
            assert k_lock > 0.0, f"{device}: k_lock not positive"

    def test_mu_max_below_one(self):
        for device, (mu_base, k_lock, mu_max) in GUIDE_MODE_LOCKING_PARAMS.items():
            assert mu_max < 1.0, f"{device}: mu_max >= 1.0 (unrealistic)"


# ── FallResult.guide_mode_used ────────────────────────────────────────────────

class TestGuideModeFallResult:
    pytestmark = pytest.mark.requires_rust

    def test_guide_mode_used_true_for_guide_device(self, rope_spec):
        cond = FallConditions(
            climber_mass_kg=80.0,
            fall_distance_m=6.0,
            rope_out_m=20.0,
            belay_device=BelayDevice.REVERSO_GUIDE,
            rope=rope_spec,
        )
        result = Fall(cond).simulate()
        assert result.guide_mode_used is True

    def test_guide_mode_used_false_for_atc(self, rope_spec):
        cond = FallConditions(
            climber_mass_kg=80.0,
            fall_distance_m=6.0,
            rope_out_m=20.0,
            belay_device=BelayDevice.ATC,
            rope=rope_spec,
        )
        result = Fall(cond).simulate()
        assert result.guide_mode_used is False

    def test_guide_mode_lower_or_equal_force(self, rope_spec):
        cond_atc = FallConditions(
            climber_mass_kg=80.0, fall_distance_m=6.0, rope_out_m=20.0,
            belay_device=BelayDevice.ATC, rope=rope_spec,
        )
        cond_guide = FallConditions(
            climber_mass_kg=80.0, fall_distance_m=6.0, rope_out_m=20.0,
            belay_device=BelayDevice.REVERSO_GUIDE, rope=rope_spec,
        )
        r_atc   = Fall(cond_atc).simulate()
        r_guide = Fall(cond_guide).simulate()
        # Guide mode has higher friction -> lower force transmitted
        assert r_guide.peak_force_kn <= r_atc.peak_force_kn + 0.1

    def test_all_guide_devices_simulate_ok(self, rope_spec):
        guide_devices = list(GUIDE_MODE_DEVICES)
        for d in guide_devices:
            cond = FallConditions(
                climber_mass_kg=80.0, fall_distance_m=5.0, rope_out_m=18.0,
                belay_device=d, rope=rope_spec,
            )
            result = Fall(cond).simulate()
            assert result.peak_force_kn > 0.0, f"Zero force for {d}"
            assert result.guide_mode_used is True
