"""Unit tests for v3 physics: twin/half ropes, knots, abrasion, risk,
dynamic belayer.

These run against the compiled Rust core when available and against the
pure-Python fallbacks otherwise -- the models are identical by design.
"""

import math

import pytest

from ropesim import physics_v3 as p3
from ropesim.physics_v3 import (
    ClimbingStyle,
    KnotType,
    SheathCondition,
    SheathRating,
    abrasion_increment,
    accumulate_sheath_wear,
    cord_anchor_strength,
    cumulative_risk,
    daily_exposure,
    dynamic_belay_reduction,
    fall_probability,
    half_rope_forces,
    knot_strength_factor,
    twin_rope_forces,
)

M, FF, K = 80.0, 1.0, 20.0


# ── twin / half ropes ────────────────────────────────────────────────────────

class TestTwinRope:
    def test_equal_stiffness_splits_evenly(self):
        fa, fb = twin_rope_forces(K, K, M, FF, 0.15)
        assert fa == pytest.approx(fb)

    def test_pair_shares_energy(self):
        fa, fb = twin_rope_forces(K, K, M, FF, 0.2)
        single = p3._uiaa_peak_force(M, FF, K)
        assert single < fa + fb < 2.0 * single

    def test_stiffer_strand_takes_more(self):
        fa, fb = twin_rope_forces(30.0, 15.0, M, FF, 0.0)
        assert fa > fb
        assert fa / (fa + fb) == pytest.approx(30.0 / 45.0)

    def test_friction_equalises_and_reduces_total(self):
        fa0, fb0 = twin_rope_forces(30.0, 15.0, M, FF, 0.0)
        fa1, fb1 = twin_rope_forces(30.0, 15.0, M, FF, 0.5)
        assert abs(fa1 - fb1) < abs(fa0 - fb0)
        assert fa1 + fb1 < fa0 + fb0

    def test_degenerate_inputs_finite(self):
        fa, fb = twin_rope_forces(0.0, 0.0, M, FF, 0.0)
        assert math.isfinite(fa) and math.isfinite(fb)


class TestHalfRope:
    def test_only_active_strand_loaded(self):
        fa, fb = half_rope_forces(15.0, 15.0, M, FF, active_rope=0)
        assert fa > 2.0
        assert fb < 0.1 * fa

    def test_symmetry(self):
        fa0, fb0 = half_rope_forces(15.0, 15.0, M, FF, active_rope=0)
        fa1, fb1 = half_rope_forces(15.0, 15.0, M, FF, active_rope=1)
        assert fa0 == pytest.approx(fb1) and fb0 == pytest.approx(fa1)

    def test_invalid_active_rope_raises(self):
        with pytest.raises(ValueError):
            half_rope_forces(15.0, 15.0, M, FF, active_rope=2)


# ── knots ────────────────────────────────────────────────────────────────────

class TestKnots:
    def test_figure_eight_in_published_range(self):
        f = knot_strength_factor(KnotType.FIGURE_EIGHT_RETRACE, 9.5)
        assert 0.75 <= f <= 0.80

    def test_clove_hitch_in_published_range(self):
        f = knot_strength_factor(KnotType.CLOVE_HITCH, 9.5)
        assert 0.60 <= f <= 0.65

    def test_all_knots_reduce_strength(self):
        for knot in KnotType:
            f = knot_strength_factor(knot, 9.8)
            assert 0.4 < f < 1.0, knot

    def test_thinner_rope_loses_more(self):
        assert knot_strength_factor("bowline", 7.7) < knot_strength_factor("bowline", 10.5)

    def test_accepts_string_names(self):
        assert knot_strength_factor("figure_eight_retrace", 9.5) == pytest.approx(
            knot_strength_factor(KnotType.FIGURE_EIGHT_RETRACE, 9.5)
        )

    def test_unknown_knot_raises(self):
        with pytest.raises(ValueError):
            knot_strength_factor("granny_knot", 9.5)

    def test_cordelette_scaling(self):
        one = cord_anchor_strength(14.0, KnotType.OVERHAND_ON_BIGHT, 1)
        three = cord_anchor_strength(14.0, KnotType.OVERHAND_ON_BIGHT, 3)
        assert 2.0 * one < three < 3.0 * one


# ── sheath abrasion ──────────────────────────────────────────────────────────

class TestAbrasion:
    def test_rock_ordering(self):
        args = (5.0, 0.4, 2.0)
        s = abrasion_increment("sandstone", *args)
        g = abrasion_increment("granite", *args)
        l = abrasion_increment("limestone", *args)
        i = abrasion_increment("ice", *args)
        assert s > g > l > i

    def test_zero_contact_zero_wear(self):
        assert abrasion_increment("granite", 0.0, 0.4, 2.0) == 0.0
        assert abrasion_increment("granite", 5.0, 0.0, 2.0) == 0.0

    def test_unknown_rock_raises(self):
        with pytest.raises(ValueError):
            abrasion_increment("marble", 5.0, 0.4, 2.0)

    def test_typical_fall_reasonable_life(self):
        inc = abrasion_increment("granite", 5.0, 0.4, 2.0)
        events = p3.RETIREMENT_THRESHOLD / inc
        assert 20 < events < 500

    def test_accumulation_to_retirement(self):
        cond = SheathCondition()
        assert cond.visual_rating is SheathRating.NEW
        for _ in range(20):
            cond = accumulate_sheath_wear(cond, 0.1)
            if cond.needs_retirement:
                break
        assert cond.needs_retirement
        assert cond.visual_rating is SheathRating.CRITICAL
        assert cond.abrasion_score <= 1.0

    def test_accepts_bare_score(self):
        cond = accumulate_sheath_wear(0.5, 0.05)
        assert cond.abrasion_score > 0.5

    def test_thick_sheath_wears_slower(self):
        a = accumulate_sheath_wear(0.0, 0.1, sheath_pct=45.0)
        b = accumulate_sheath_wear(0.0, 0.1, sheath_pct=30.0)
        assert a.abrasion_score < b.abrasion_score

    def test_falls_remaining_decreases(self):
        c1 = accumulate_sheath_wear(0.0, 0.05)
        c2 = accumulate_sheath_wear(c1, 0.05)
        assert c2.estimated_falls_remaining < c1.estimated_falls_remaining


# ── fall probability / risk ──────────────────────────────────────────────────

class TestRisk:
    def test_probability_monotonic_in_grade(self):
        easy = fall_probability(9.0, 12.0)
        limit = fall_probability(12.0, 12.0)
        over = fall_probability(13.0, 12.0)
        assert easy < limit < over
        assert easy < 0.05
        assert over > 0.9

    def test_at_limit_moderate(self):
        assert 0.3 <= fall_probability(11.0, 11.0) <= 0.7

    def test_style_ordering(self):
        t = fall_probability(11.0, 11.0, ClimbingStyle.TRAD)
        s = fall_probability(11.0, 11.0, ClimbingStyle.SPORT)
        b = fall_probability(11.0, 11.0, ClimbingStyle.BOULDER)
        assert t < s < b

    def test_bounded(self):
        for r, c in [(5.0, 15.0), (15.0, 5.0), (10.0, 10.0)]:
            assert 0.01 <= fall_probability(r, c) <= 0.95

    def test_unknown_style_raises(self):
        with pytest.raises(ValueError):
            fall_probability(10.0, 10.0, "aid")

    def test_cumulative_risk_scaling(self):
        r5 = cumulative_risk(0.5, 5, 6.0, 8)
        r10 = cumulative_risk(0.5, 10, 6.0, 8)
        assert r5.expected_falls == pytest.approx(2.5)
        assert r10.expected_total_force_kn > r5.expected_total_force_kn
        assert r10.rope_life_consumed_pct > r5.rope_life_consumed_pct

    def test_prior_falls_consume_life(self):
        fresh = cumulative_risk(0.5, 4, 7.0, 8, falls_taken_so_far=0)
        used = cumulative_risk(0.5, 4, 7.0, 8, falls_taken_so_far=6)
        assert used.rope_life_consumed_pct > fresh.rope_life_consumed_pct
        assert used.retirement_climbs_remaining < fresh.retirement_climbs_remaining

    def test_daily_exposure_aggregates(self):
        report = daily_exposure([(0.3, 3), (0.6, 5), (0.1, 2)], 6.0, 8)
        assert report.total_expected_falls == pytest.approx(0.3 * 3 + 0.6 * 5 + 0.1 * 2)
        assert not report.retirement_projected
        assert report.critical_pitch_index == -1

    def test_daily_exposure_flags_critical_pitch(self):
        report = daily_exposure([(0.1, 1), (0.9, 10)], 9.0, 2, falls_taken_so_far=1)
        assert report.retirement_projected
        assert report.critical_pitch_index == 1


# ── dynamic belayer ──────────────────────────────────────────────────────────

class TestDynamicBelay:
    def test_light_belayer_softer_catch(self):
        light = dynamic_belay_reduction(80.0, 55.0, "atc")
        heavy = dynamic_belay_reduction(80.0, 110.0, "atc")
        assert light < heavy

    def test_soft_catch_reduces_force(self):
        hard = dynamic_belay_reduction(80.0, 75.0, "grigri")
        soft = dynamic_belay_reduction(80.0, 75.0, "grigri", soft_catch_technique=True)
        assert soft < hard

    def test_soft_catch_light_climber_30_to_45_pct(self):
        f = dynamic_belay_reduction(55.0, 80.0, "atc", soft_catch_technique=True)
        assert 0.55 <= f <= 0.75

    def test_tube_softer_than_grigri(self):
        assert dynamic_belay_reduction(80.0, 75.0, "atc") < dynamic_belay_reduction(
            80.0, 75.0, "grigri"
        )

    def test_standing_softer_than_sitting(self):
        stand = dynamic_belay_reduction(80.0, 70.0, "atc", belayer_standing=True)
        sit = dynamic_belay_reduction(80.0, 70.0, "atc", belayer_standing=False)
        assert stand < sit

    def test_always_bounded(self):
        for mc in (40.0, 80.0, 120.0):
            for mb in (40.0, 80.0, 120.0):
                for soft in (False, True):
                    f = dynamic_belay_reduction(mc, mb, "atc", soft_catch_technique=soft)
                    assert 0.55 <= f <= 1.0

    def test_unknown_device_raises(self):
        with pytest.raises(ValueError):
            dynamic_belay_reduction(80.0, 75.0, "figure_eight_descender")


# ── public API surface ───────────────────────────────────────────────────────

def test_v3_exports_available_from_package_root():
    import ropesim

    for name in (
        "twin_rope_forces",
        "half_rope_forces",
        "knot_strength_factor",
        "cord_anchor_strength",
        "abrasion_increment",
        "accumulate_sheath_wear",
        "fall_probability",
        "cumulative_risk",
        "daily_exposure",
        "dynamic_belay_reduction",
        "KnotType",
        "ClimbingStyle",
        "SheathCondition",
    ):
        assert hasattr(ropesim, name), name
