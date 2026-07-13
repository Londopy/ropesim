"""
Unit tests for the v4 physics: nonlinear rope model, capstan route friction,
and two-body belayer dynamics.
"""
import math

import pytest

pytest.importorskip("ropesim._rustcore", reason="Rust extension not compiled")

from ropesim import _rustcore as rc
from ropesim import (
    capstan_ratio,
    nonlinear_impact_force,
    route_friction,
    route_transmission,
    two_body_catch,
)

G = 9.81
EN892_FF = 1.772


# ─── Nonlinear rope model ────────────────────────────────────────────────────

class TestNonlinearCalibration:
    def test_exact_at_en892_point(self):
        """Calibration must reproduce the rated force at the test point."""
        r = rc.calibrate_nonlinear_rope(8.2, 33.0, 80.0)
        f = rc.compute_impact_force_nonlinear(80.0, EN892_FF, r, 0.0)
        assert f == pytest.approx(8.2, abs=1e-6)

    def test_exact_elongation_at_en892_point(self):
        """Force at the calibration strain equals the rated impact force."""
        r = rc.calibrate_nonlinear_rope(8.2, 33.0, 80.0)
        assert r.force_at_strain(0.33) == pytest.approx(8.2, abs=1e-9)

    def test_energy_matches_at_test_point(self):
        """Stored energy at eps* equals mg(ff + eps*) — the fall energy."""
        r = rc.calibrate_nonlinear_rope(9.0, 35.0, 80.0)
        mg = 80.0 * G / 1000.0
        # integrate F numerically
        n, e_star = 20000, 0.35
        u = sum(r.force_at_strain((i + 0.5) * e_star / n) for i in range(n)) * e_star / n
        assert u == pytest.approx(mg * (EN892_FF + 0.35), rel=1e-4)

    def test_force_monotone_increasing(self):
        r = rc.calibrate_nonlinear_rope(8.2, 33.0, 80.0)
        prev = 0.0
        for i in range(1, 200):
            f = r.force_at_strain(i * 0.005)  # up to 100 % strain
            assert f >= prev
            prev = f

    def test_zero_strain_zero_force(self):
        r = rc.calibrate_nonlinear_rope(8.2, 33.0, 80.0)
        assert r.force_at_strain(0.0) == 0.0
        assert r.force_at_strain(-0.1) == 0.0

    def test_stiffer_than_linear_at_low_ff(self):
        """Real ropes are stiff early: nonlinear > linear prediction at low ff."""
        r = rc.calibrate_nonlinear_rope(8.2, 33.0, 80.0)
        k_lin = rc.compute_stiffness_from_spec(8.2, 33.0, 80.0)
        f_nl = rc.compute_impact_force_nonlinear(70.0, 0.3, r, 0.0)
        f_lin = rc.compute_impact_force_uiaa(70.0, 0.3, k_lin, 0.0)
        assert f_nl > f_lin

    def test_monotone_in_fall_factor(self):
        r = rc.calibrate_nonlinear_rope(8.2, 33.0, 80.0)
        forces = [rc.compute_impact_force_nonlinear(80.0, ff, r, 0.0)
                  for ff in (0.1, 0.5, 1.0, 1.5, 2.0)]
        assert all(a < b for a, b in zip(forces, forces[1:]))

    def test_monotone_in_mass(self):
        r = rc.calibrate_nonlinear_rope(8.2, 33.0, 80.0)
        f60 = rc.compute_impact_force_nonlinear(60.0, 1.0, r, 0.0)
        f90 = rc.compute_impact_force_nonlinear(90.0, 1.0, r, 0.0)
        assert f90 > f60

    def test_belay_friction_reduces_force(self):
        r = rc.calibrate_nonlinear_rope(8.2, 33.0, 80.0)
        f0 = rc.compute_impact_force_nonlinear(80.0, 1.0, r, 0.0)
        f3 = rc.compute_impact_force_nonlinear(80.0, 1.0, r, 0.3)
        assert f3 == pytest.approx(f0 * 0.7, rel=1e-9)

    def test_invalid_spec_raises(self):
        with pytest.raises(ValueError):
            rc.calibrate_nonlinear_rope(-1.0, 33.0, 80.0)
        with pytest.raises(ValueError):
            rc.calibrate_nonlinear_rope(8.2, 0.0, 80.0)

    def test_rk4_matches_energy_solution_undamped(self):
        """Undamped RK4 peak must equal the energy-balance peak."""
        r = rc.calibrate_nonlinear_rope(8.2, 33.0, 80.0)
        rope_out, ff = 5.0, EN892_FF
        curve = rc.compute_force_curve_nonlinear(80.0, ff * rope_out, rope_out, r, 0.0, 0.1)
        f_energy = rc.compute_impact_force_nonlinear(80.0, ff, r, 0.0)
        assert max(curve) == pytest.approx(f_energy, rel=1e-3)

    def test_rk4_converges_across_timesteps(self):
        """Regression for the old 3000-step cap: fine dt must not truncate."""
        r = rc.calibrate_nonlinear_rope(8.2, 33.0, 80.0)
        peaks = [max(rc.compute_force_curve_nonlinear(80.0, 5.0, 10.0, r, 0.0, ts))
                 for ts in (1.0, 0.1, 0.01)]
        assert max(peaks) - min(peaks) < 1e-3

    def test_python_facade(self, single_rope_spec):
        f = nonlinear_impact_force(single_rope_spec, 80.0, 1.0)
        assert 3.0 < f < single_rope_spec.impact_force_kn + 0.5


# ─── Capstan route friction ──────────────────────────────────────────────────

class TestCapstan:
    def test_ratio_identity_zero_angle(self):
        assert rc.capstan_tension_ratio(0.3, 0.0) == 1.0

    def test_ratio_identity_zero_mu(self):
        assert rc.capstan_tension_ratio(0.0, math.pi) == 1.0

    def test_ratio_exponential(self):
        assert rc.capstan_tension_ratio(0.2, math.pi) == pytest.approx(math.exp(0.2 * math.pi))

    def test_python_facade_degrees(self):
        assert capstan_ratio(0.2, 180.0) == pytest.approx(math.exp(0.2 * math.pi))

    def test_top_piece_load_is_sum_of_tensions(self):
        """θ=180°: piece load = T_in + T_out (pulley effect)."""
        rf = rc.compute_route_friction(8.0, [180.0], 0.25)
        t_out = 8.0 * math.exp(-0.25 * math.pi)
        assert rf.piece_loads_kn[0] == pytest.approx(8.0 + t_out, rel=1e-9)

    def test_straight_rope_no_load(self):
        """θ=0: no direction change, no friction, no piece load."""
        rf = rc.compute_route_friction(8.0, [0.0], 0.25)
        assert rf.piece_loads_kn[0] == pytest.approx(0.0, abs=1e-9)
        assert rf.belay_tension_kn == pytest.approx(8.0)

    def test_tensions_decay_toward_belayer(self):
        rf = rc.compute_route_friction(8.0, [170.0, 30.0, 20.0], 0.2)
        t = rf.segment_tensions_kn
        assert len(t) == 4
        assert all(a > b for a, b in zip(t, t[1:]))

    def test_drag_factor_is_total_capstan_product(self):
        angles = [170.0, 45.0, 30.0]
        rf = rc.compute_route_friction(8.0, angles, 0.2)
        expected = math.exp(0.2 * sum(math.radians(a) for a in angles))
        assert rf.drag_factor == pytest.approx(expected, rel=1e-9)

    def test_transmission_fraction_inverse_of_drag(self):
        angles = [160.0, 20.0, 20.0]
        frac = route_transmission(angles, mu=0.2)
        rf = route_friction(8.0, angles, mu=0.2)
        assert frac == pytest.approx(1.0 / rf.drag_factor, rel=1e-9)

    def test_pulley_effect_magnitude_realistic(self):
        """Top piece sees ~1.4–1.9x the climber-side tension (Petzl: ~1.6)."""
        rf = rc.compute_route_friction(8.0, [170.0], 0.2)
        ratio = rf.piece_loads_kn[0] / 8.0
        assert 1.4 < ratio < 1.9

    def test_negative_inputs_raise(self):
        with pytest.raises(ValueError):
            rc.compute_route_friction(-1.0, [90.0], 0.2)


# ─── Two-body belayer dynamics ───────────────────────────────────────────────

class TestTwoBody:
    K = 20.0  # typical length-normalised stiffness, kN

    def test_reduction_emerges_positive(self):
        """A liftable belayer must reduce peak force vs a rigid anchor."""
        r = two_body_catch(80.0, 65.0, 4.0, 5.0, self.K)
        assert r.reduction_pct > 0.0
        assert r.peak_climber_kn < r.peak_fixed_anchor_kn

    def test_reduction_in_published_band(self):
        """Belayer-lift soft catch: ~5–35 % for common mass ratios."""
        for belayer in (55.0, 70.0, 90.0):
            r = two_body_catch(80.0, belayer, 4.0, 5.0, self.K)
            assert 3.0 < r.reduction_pct < 40.0, (belayer, r.reduction_pct)

    def test_lighter_belayer_softer_catch(self):
        reductions = [two_body_catch(80.0, b, 4.0, 5.0, self.K).reduction_pct
                      for b in (110.0, 80.0, 55.0)]
        assert reductions[0] < reductions[1] < reductions[2]

    def test_lighter_belayer_lifts_higher(self):
        lifts = [two_body_catch(80.0, b, 4.0, 5.0, self.K).max_belayer_lift_m
                 for b in (110.0, 80.0, 55.0)]
        assert lifts[0] < lifts[1] < lifts[2]

    def test_very_heavy_belayer_approaches_fixed_anchor(self):
        r = two_body_catch(80.0, 100000.0, 4.0, 5.0, self.K)
        assert r.reduction_pct == pytest.approx(0.0, abs=1.0)
        assert r.max_belayer_lift_m < 0.02

    def test_fixed_anchor_matches_linear_theory_undamped(self):
        """With an immovable belayer and zeta=0 the peak must match the
        analytic energy solution for the climber-side rope segment."""
        mg = 80.0 * G / 1000.0
        rope_out, fall = 5.0, 4.0
        r = two_body_catch(80.0, 1e9, fall, rope_out, self.K,
                           damping_ratio=0.0, timestep_ms=0.05)
        ff = fall / rope_out
        f_an = mg + math.sqrt(mg * mg + 2.0 * mg * ff * self.K)
        assert r.peak_climber_kn == pytest.approx(f_an, rel=5e-3)

    def test_top_piece_load_between_1x_and_2x_climber_peak(self):
        r = two_body_catch(80.0, 70.0, 4.0, 5.0, self.K)
        assert r.peak_climber_kn < r.peak_top_piece_kn < 2.0 * r.peak_climber_kn

    def test_belay_tension_capstan_consistent(self):
        mu, theta = 0.25, 170.0
        r = two_body_catch(80.0, 70.0, 4.0, 5.0, self.K, mu_top=mu, theta_top_deg=theta)
        beta = math.exp(-mu * math.radians(theta))
        assert r.peak_belay_kn == pytest.approx(r.peak_climber_kn * beta, rel=1e-6)

    def test_force_curve_returned(self):
        r = two_body_catch(80.0, 70.0, 4.0, 5.0, self.K)
        assert len(r.force_curve_kn) > 100
        assert max(r.force_curve_kn) == pytest.approx(r.peak_climber_kn, rel=1e-9)

    def test_invalid_inputs_raise(self):
        with pytest.raises(ValueError):
            two_body_catch(0.0, 70.0, 4.0, 5.0, self.K)
        with pytest.raises(ValueError):
            two_body_catch(80.0, -5.0, 4.0, 5.0, self.K)

    def test_rope_spec_accepted(self, single_rope_spec):
        r = two_body_catch(80.0, 70.0, 4.0, 5.0, single_rope_spec)
        assert r.peak_climber_kn > 1.0
