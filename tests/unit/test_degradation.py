"""
Unit tests for rope degradation model and retirement warnings.
"""
import pytest
from ropesim.rope import Rope, RopeSpec, RopeType, RopeStandard


def _rope(falls: int = 7) -> Rope:
    spec = RopeSpec(
        name="Degradation Test",
        manufacturer="TestCo",
        rope_type=RopeType.SINGLE,
        standard=RopeStandard.BOTH,
        diameter_mm=9.5,
        weight_gpm=60.0,
        sheath_percentage=40.0,
        impact_force_kn=9.2,
        number_of_falls=falls,
        static_elongation_pct=8.0,
        dynamic_elongation_pct=34.0,
        dry_treated=False,
    )
    return Rope(spec)


class TestDegradationModel:
    def test_zero_falls_unchanged(self):
        r = _rope()
        degraded = r.degrade(0)
        assert degraded.spec.impact_force_kn == r.spec.impact_force_kn
        assert degraded.spec.static_elongation_pct == r.spec.static_elongation_pct

    def test_impact_force_increases_with_falls(self):
        r = _rope(10)
        r1 = r.degrade(3)
        r2 = r.degrade(8)
        assert r2.spec.impact_force_kn >= r1.spec.impact_force_kn

    def test_elongation_decreases_with_falls(self):
        r = _rope(10)
        r1 = r.degrade(3)
        r2 = r.degrade(9)
        assert r2.spec.dynamic_elongation_pct <= r1.spec.dynamic_elongation_pct

    def test_static_less_than_dynamic_after_degradation(self):
        r = _rope(10)
        degraded = r.degrade(9)
        assert degraded.spec.static_elongation_pct < degraded.spec.dynamic_elongation_pct

    def test_degraded_name_includes_falls(self):
        r = _rope()
        degraded = r.degrade(4)
        assert "4 falls" in degraded.spec.name

    def test_fall_count_decremented(self):
        r = _rope(10)
        degraded = r.degrade(3)
        assert degraded.spec.number_of_falls == 7


class TestRetirementWarning:
    def test_no_warning_fresh_rope(self):
        r = _rope(10)
        assert r.retirement_warning(0) is None
        assert r.retirement_warning(1) is None

    def test_no_warning_below_80_pct(self):
        r = _rope(10)
        assert r.retirement_warning(7) is None  # 70% of 10

    def test_warning_above_80_pct(self):
        r = _rope(10)
        w = r.retirement_warning(9)   # 90% of rated
        assert w is not None
        assert "%" in w

    def test_retirement_at_rated_falls(self):
        r = _rope(7)
        w = r.retirement_warning(7)
        assert w is not None
        assert "retire" in w.lower()

    def test_retirement_above_rated_falls(self):
        r = _rope(7)
        w = r.retirement_warning(10)
        assert w is not None
        assert "retire" in w.lower()

    def test_warning_contains_count(self):
        r = _rope(7)
        w = r.retirement_warning(6)
        assert w is not None
        assert "6" in w
