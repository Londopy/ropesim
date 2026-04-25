"""
Unit tests for ropesim.notebook — HTML repr patches.

These tests verify that importing ropesim.notebook attaches _repr_html_()
to the correct classes and that the returned HTML is non-empty and contains
expected content. No Jupyter kernel is needed.
"""
import pytest


# ── Import patch side-effects ─────────────────────────────────────────────────

class TestNotebookPatch:
    def test_import_succeeds(self):
        import ropesim.notebook  # noqa: F401

    def test_rope_gets_repr_html(self):
        import ropesim.notebook  # noqa: F401
        from ropesim.rope import Rope
        assert hasattr(Rope, "_repr_html_")
        assert callable(Rope._repr_html_)

    def test_fall_result_gets_repr_html(self):
        import ropesim.notebook  # noqa: F401
        from ropesim.fall import FallResult
        assert hasattr(FallResult, "_repr_html_")
        assert callable(FallResult._repr_html_)

    def test_anchor_system_gets_repr_html(self):
        import ropesim.notebook  # noqa: F401
        from ropesim.anchor import AnchorSystem
        assert hasattr(AnchorSystem, "_repr_html_")
        assert callable(AnchorSystem._repr_html_)


# ── Rope HTML repr ────────────────────────────────────────────────────────────

@pytest.fixture
def rope():
    import ropesim.notebook  # noqa: F401
    from ropesim.rope import Rope, RopeSpec, RopeType
    spec = RopeSpec(
        name="Notebook Test 9.5",
        manufacturer="TestCo",
        rope_type=RopeType.SINGLE,
        diameter_mm=9.5,
        weight_gpm=60.0,
        sheath_percentage=40.0,
        impact_force_kn=9.2,
        number_of_falls=7,
        static_elongation_pct=8.0,
        dynamic_elongation_pct=34.0,
        dry_treated=True,
    )
    return Rope(spec)


class TestRopeReprHtml:
    def test_returns_string(self, rope):
        html = rope._repr_html_()
        assert isinstance(html, str)

    def test_non_empty(self, rope):
        html = rope._repr_html_()
        assert len(html) > 100

    def test_contains_rope_name(self, rope):
        html = rope._repr_html_()
        assert "Notebook Test 9.5" in html

    def test_contains_diameter(self, rope):
        html = rope._repr_html_()
        assert "9.5" in html

    def test_contains_impact_force(self, rope):
        html = rope._repr_html_()
        assert "9.2" in html

    def test_contains_html_tags(self, rope):
        html = rope._repr_html_()
        assert "<" in html and ">" in html

    def test_dry_treatment_indicated(self, rope):
        html = rope._repr_html_()
        assert "dry" in html.lower() or "Dry" in html


# ── AnchorSystem HTML repr ────────────────────────────────────────────────────

@pytest.fixture
def anchor():
    import ropesim.notebook  # noqa: F401
    from ropesim.anchor import AnchorSystem, AnchorType, Bolt
    return AnchorSystem(
        AnchorType.SLIDING_X,
        [Bolt(rated_mbs_kn=25.0), Bolt(rated_mbs_kn=25.0)],
    )


class TestAnchorReprHtml:
    def test_returns_string(self, anchor):
        html = anchor._repr_html_()
        assert isinstance(html, str)

    def test_non_empty(self, anchor):
        html = anchor._repr_html_()
        assert len(html) > 50

    def test_contains_html(self, anchor):
        html = anchor._repr_html_()
        assert "<" in html


# ── FallResult HTML repr ──────────────────────────────────────────────────────

@pytest.fixture
def fall_result(rope):
    pytest.importorskip("ropesim._rustcore", reason="Rust extension not compiled")
    import ropesim.notebook  # noqa: F401
    from ropesim.fall import Fall, FallConditions, BelayDevice
    cond = FallConditions(
        climber_mass_kg=80.0,
        fall_distance_m=6.0,
        rope_out_m=20.0,
        belay_device=BelayDevice.ATC,
        rope=rope.spec,
    )
    return Fall(cond).simulate()


class TestFallResultReprHtml:
    pytestmark = pytest.mark.requires_rust

    def test_returns_string(self, fall_result):
        html = fall_result._repr_html_()
        assert isinstance(html, str)

    def test_non_empty(self, fall_result):
        html = fall_result._repr_html_()
        assert len(html) > 100

    def test_contains_peak_force(self, fall_result):
        html = fall_result._repr_html_()
        # Should contain the numeric value somewhere
        assert str(round(fall_result.peak_force_kn, 1)) in html or "kN" in html

    def test_contains_fall_factor(self, fall_result):
        html = fall_result._repr_html_()
        assert "fall" in html.lower() or "factor" in html.lower() or "ff" in html.lower()
