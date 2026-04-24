"""
Unit tests for EN 892 compliance validation.
"""
import pytest
from pydantic import ValidationError

from ropesim.rope import RopeSpec, RopeType, RopeStandard
from ropesim import standards


def _make_spec(**overrides) -> RopeSpec:
    """Build a compliant base spec with optional overrides."""
    base = dict(
        name="Compliant 9.5mm Single",
        manufacturer="TestCo",
        rope_type=RopeType.SINGLE,
        standard=RopeStandard.BOTH,
        diameter_mm=9.5,
        weight_gpm=60.0,
        sheath_percentage=40.0,
        impact_force_kn=9.0,
        number_of_falls=7,
        static_elongation_pct=8.0,
        dynamic_elongation_pct=34.0,
        dry_treated=False,
    )
    base.update(overrides)
    return RopeSpec(**base)


class TestEN892Compliance:
    def test_compliant_spec_passes(self):
        spec = _make_spec()
        violations = standards.validate_rope(spec)
        assert violations == []

    def test_impact_force_too_high(self):
        spec = _make_spec(impact_force_kn=13.0)  # > 12 kN limit
        violations = standards.validate_rope(spec)
        assert any("impact force" in v.lower() for v in violations)

    def test_half_rope_impact_force_limit(self):
        spec = _make_spec(
            rope_type=RopeType.HALF,
            diameter_mm=8.2,
            impact_force_kn=9.0,  # > 8.0 kN limit for half ropes
        )
        violations = standards.validate_rope(spec)
        assert any("impact force" in v.lower() for v in violations)

    def test_fall_count_too_low(self):
        spec = _make_spec(number_of_falls=3)  # < 5 minimum for single
        violations = standards.validate_rope(spec)
        assert any("fall count" in v.lower() for v in violations)

    def test_static_elongation_too_high(self):
        spec = _make_spec(static_elongation_pct=11.0)  # > 10% limit
        violations = standards.validate_rope(spec)
        assert any("static elongation" in v.lower() for v in violations)

    def test_dynamic_elongation_too_high(self):
        spec = _make_spec(dynamic_elongation_pct=42.0)  # > 40% limit
        violations = standards.validate_rope(spec)
        assert any("dynamic elongation" in v.lower() for v in violations)

    def test_diameter_too_small(self):
        # 8.0 mm is below the 8.5 mm minimum for single ropes
        spec = _make_spec(diameter_mm=8.0)
        violations = standards.validate_rope(spec)
        assert any("diameter" in v.lower() for v in violations)

    def test_diameter_too_large(self):
        spec = _make_spec(diameter_mm=11.5)
        violations = standards.validate_rope(spec)
        assert any("diameter" in v.lower() for v in violations)

    def test_multiple_violations_reported(self):
        spec = _make_spec(impact_force_kn=13.0, number_of_falls=2)
        violations = standards.validate_rope(spec)
        assert len(violations) >= 2

    def test_compliant_half_rope(self):
        spec = _make_spec(
            rope_type=RopeType.HALF,
            diameter_mm=8.2,
            impact_force_kn=6.5,
            number_of_falls=5,
            static_elongation_pct=7.0,
            dynamic_elongation_pct=30.0,
        )
        violations = standards.validate_rope(spec)
        assert violations == []

    def test_twin_rope_minimum_falls(self):
        spec = _make_spec(
            rope_type=RopeType.TWIN,
            diameter_mm=7.5,
            impact_force_kn=9.0,
            number_of_falls=10,  # < 12 minimum for twin
        )
        violations = standards.validate_rope(spec)
        assert any("fall count" in v.lower() for v in violations)


class TestPydanticValidation:
    def test_invalid_diameter_rejected(self):
        with pytest.raises(ValidationError):
            _make_spec(diameter_mm=3.0)  # below 5.0 minimum

    def test_dynamic_below_static_rejected(self):
        with pytest.raises(ValidationError):
            _make_spec(static_elongation_pct=20.0, dynamic_elongation_pct=10.0)

    def test_negative_falls_rejected(self):
        with pytest.raises(ValidationError):
            _make_spec(number_of_falls=0)

    def test_impact_force_zero_rejected(self):
        with pytest.raises(ValidationError):
            _make_spec(impact_force_kn=0.0)


class TestStandardsReference:
    def test_reference_returns_dict(self):
        ref = standards.reference()
        assert isinstance(ref, dict)
        assert "EN 892:2012+A3:2023" in ref
        assert "UIAA 101" in ref

    def test_reference_contains_limits(self):
        ref = standards.reference()
        en = ref["EN 892:2012+A3:2023"]
        assert "key_limits" in en
        assert en["key_limits"]["max_impact_force_single_kn"] == 12.0
