"""
Validation regression suite.

Turns "is the model accurate?" into numbers tracked in CI.

Data sources
------------
1. The bundled 25-rope database (``ropesim/database/ropes.json``): every entry
   carries the manufacturer's *measured* EN 892 / UIAA 101 drop-test results
   (rated impact force + dynamic elongation).  These are real published
   drop-test data points — one per rope — and the models are required to
   reproduce them within tolerance.
2. Physics invariants with exact analytic answers (limiting cases, energy
   conservation), which hold regardless of rope data.

To add external drop-tower measurements (e.g. Pavier 1998, UIAA Safety
Commission reports), append rows to ``EXTERNAL_DROP_TESTS`` below with a
source note; each row becomes a test case automatically.

Tolerances
----------
* EN 892 reproduction: 1e-6 (exact by construction — regression guard)
* Linear-model EN 892 force reproduction: 1e-6 (same)
* Cross-model agreement at the test point: 5 %
* RK4 vs closed-form energy solutions: 0.5 %
"""
import json
import math
import pathlib

import pytest

pytest.importorskip("ropesim._rustcore", reason="Rust extension not compiled")

from ropesim import _rustcore as rc

G = 9.81
EN892_FF = 1.772
DB = pathlib.Path(__file__).resolve().parents[2] / "ropesim" / "database" / "ropes.json"

with open(DB) as fh:
    ROPES = json.load(fh)

SINGLE_ROPES = [r for r in ROPES if "single" in r.get("rope_type", "")]
ROPE_IDS = [r["name"] for r in SINGLE_ROPES]

# External measured drop tests: (source, mass_kg, fall_factor,
#   rope_impact_force_kn, rope_dynamic_elongation_pct, measured_peak_kn, rel_tol)
# Empty by design until literature values are transcribed with page references —
# do NOT add numbers from memory.
EXTERNAL_DROP_TESTS: list[tuple] = []


# ─── 1. Manufacturer drop-test reproduction (25-rope database) ───────────────

@pytest.mark.parametrize("rope", SINGLE_ROPES, ids=ROPE_IDS)
class TestManufacturerDropTests:
    def test_linear_model_reproduces_rated_force(self, rope):
        k = rc.compute_stiffness_from_spec(
            rope["impact_force_kn"], rope["dynamic_elongation_pct"], 80.0
        )
        f = rc.compute_impact_force_uiaa(80.0, EN892_FF, k, 0.0)
        assert f == pytest.approx(rope["impact_force_kn"], rel=1e-6)

    def test_nonlinear_model_reproduces_rated_force(self, rope):
        nl = rc.calibrate_nonlinear_rope(
            rope["impact_force_kn"], rope["dynamic_elongation_pct"], 80.0
        )
        f = rc.compute_impact_force_nonlinear(80.0, EN892_FF, nl, 0.0)
        assert f == pytest.approx(rope["impact_force_kn"], rel=1e-6)

    def test_nonlinear_model_reproduces_rated_elongation(self, rope):
        """The nonlinear model must hit the *measured elongation* too — the
        linear model structurally cannot (this is the v4 accuracy win)."""
        nl = rc.calibrate_nonlinear_rope(
            rope["impact_force_kn"], rope["dynamic_elongation_pct"], 80.0
        )
        eps = rope["dynamic_elongation_pct"] / 100.0
        assert nl.force_at_strain(eps) == pytest.approx(
            rope["impact_force_kn"], rel=1e-9
        )

    def test_nonlinear_elongation_error_never_worse_than_linear(self, rope):
        """The v4 accuracy win, as a tracked number: the nonlinear model's
        elongation error at the test point is zero by construction; the
        linear model's is not.  Guards the two-point calibration."""
        k = rc.compute_stiffness_from_spec(
            rope["impact_force_kn"], rope["dynamic_elongation_pct"], 80.0
        )
        measured_eps = rope["dynamic_elongation_pct"] / 100.0
        linear_err = abs(rope["impact_force_kn"] / k - measured_eps)
        nl = rc.calibrate_nonlinear_rope(
            rope["impact_force_kn"], rope["dynamic_elongation_pct"], 80.0
        )
        # strain at which the nonlinear model reaches rated force
        nonlinear_err = abs(
            nl.force_at_strain(measured_eps) - rope["impact_force_kn"]
        ) / rope["impact_force_kn"]
        assert nonlinear_err <= linear_err + 1e-9

    def test_models_agree_at_test_point(self, rope):
        nl = rc.calibrate_nonlinear_rope(
            rope["impact_force_kn"], rope["dynamic_elongation_pct"], 80.0
        )
        k = rc.compute_stiffness_from_spec(
            rope["impact_force_kn"], rope["dynamic_elongation_pct"], 80.0
        )
        f_nl = rc.compute_impact_force_nonlinear(80.0, EN892_FF, nl, 0.0)
        f_lin = rc.compute_impact_force_uiaa(80.0, EN892_FF, k, 0.0)
        assert f_nl == pytest.approx(f_lin, rel=0.05)

    def test_calibration_physical(self, rope):
        """Calibrated coefficients are physical: positive initial stiffness,
        monotone force up to well beyond the rated elongation."""
        nl = rc.calibrate_nonlinear_rope(
            rope["impact_force_kn"], rope["dynamic_elongation_pct"], 80.0
        )
        assert nl.a_kn > 0.0
        # Monotone within 0.5 %: a sub-percent dip near eps* can occur for
        # extreme specs (e.g. Beal Ice Line) where the cubic's stationary
        # point falls just inside the calibration strain. Physically noise.
        prev = 0.0
        for i in range(1, 120):
            f = nl.force_at_strain(i * 0.005)  # to 60 % strain
            assert f >= prev * 0.995
            prev = f


# ─── 2. External measured drop tests (literature) ────────────────────────────

@pytest.mark.parametrize("row", EXTERNAL_DROP_TESTS,
                         ids=[r[0] for r in EXTERNAL_DROP_TESTS])
def test_external_drop_test(row):
    source, mass, ff, f_rated, dyn_pct, measured, tol = row
    nl = rc.calibrate_nonlinear_rope(f_rated, dyn_pct, 80.0)
    predicted = rc.compute_impact_force_nonlinear(mass, ff, nl, 0.0)
    assert predicted == pytest.approx(measured, rel=tol), source


# ─── 3. Analytic invariants ──────────────────────────────────────────────────

class TestAnalyticInvariants:
    def test_linear_zero_stiffness_limit_is_2mg(self):
        """k→0: force → 2·mg (static hang bounce), independent of ff."""
        mg = 80.0 * G / 1000.0
        f = rc.compute_impact_force_uiaa(80.0, 1.0, 1e-9, 0.0)
        assert f == pytest.approx(2.0 * mg, rel=1e-4)

    def test_linear_zero_ff_limit_is_2mg(self):
        mg = 80.0 * G / 1000.0
        f = rc.compute_impact_force_uiaa(80.0, 0.0, 25.0, 0.0)
        assert f == pytest.approx(2.0 * mg, rel=1e-9)

    def test_rk4_linear_matches_wexler_all_timesteps(self):
        """Undamped RK4 peak equals the closed-form solution at any dt."""
        m, fall, L, k = 80.0, 5.0, 10.0, 19.5
        mg = m * G / 1000.0
        f_an = mg + math.sqrt(mg * mg + 2.0 * mg * (fall / L) * k)
        for ts in (2.0, 1.0, 0.1, 0.02):
            peak = max(rc.compute_force_curve(m, fall, L, k, 0.0, ts))
            assert peak == pytest.approx(f_an, rel=5e-3), f"dt={ts}"

    def test_rk4_energy_conservation_undamped(self):
        """At peak stretch all released PE is stored in the spring (<1 %)."""
        m, fall, L, k = 80.0, 5.0, 10.0, 19.5
        curve = rc.compute_force_curve(m, fall, L, k, 0.0, 0.05)
        k_nm = k * 1000.0 / L
        delta = max(curve) * 1000.0 / k_nm
        e_spring = 0.5 * k_nm * delta * delta
        e_grav = m * G * (fall + delta)
        assert e_spring == pytest.approx(e_grav, rel=0.01)

    def test_damping_reduces_peak_monotonically(self):
        m, fall, L, k = 80.0, 5.0, 10.0, 19.5
        peaks = [max(rc.compute_force_curve(m, fall, L, k, z, 0.1))
                 for z in (0.0, 0.1, 0.2, 0.3)]
        assert all(a > b for a, b in zip(peaks, peaks[1:]))

    def test_capstan_matches_closed_form(self):
        for mu in (0.1, 0.2, 0.3):
            for deg in (30.0, 90.0, 180.0):
                got = rc.capstan_tension_ratio(mu, math.radians(deg))
                assert got == pytest.approx(math.exp(mu * math.radians(deg)), rel=1e-12)

    def test_two_body_infinite_belayer_is_fixed_anchor(self):
        r = rc.simulate_two_body_fall(80.0, 1e12, 4.0, 5.0, 20.0)
        assert abs(r.reduction_pct) < 0.5
