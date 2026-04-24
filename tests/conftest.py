"""
Shared pytest fixtures and markers.
"""
import pytest

# ---------------------------------------------------------------------------
# Skip marker for tests that require the compiled Rust extension
# ---------------------------------------------------------------------------
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_rust: skip if ropesim._rustcore has not been compiled",
    )


@pytest.fixture(scope="session")
def rustcore():
    """Return the _rustcore module, or skip if not compiled."""
    pytest.importorskip("ropesim._rustcore", reason="Rust extension not compiled — run `maturin develop`")
    from ropesim import _rustcore
    return _rustcore


# ---------------------------------------------------------------------------
# Common rope specs
# ---------------------------------------------------------------------------
from ropesim.rope import RopeSpec, RopeType, RopeStandard

@pytest.fixture
def single_rope_spec():
    return RopeSpec(
        name="Test Single 9.5",
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
def half_rope_spec():
    return RopeSpec(
        name="Test Half 8.0",
        manufacturer="TestCo",
        rope_type=RopeType.HALF,
        standard=RopeStandard.BOTH,
        diameter_mm=8.0,
        weight_gpm=44.0,
        sheath_percentage=35.0,
        impact_force_kn=6.5,
        number_of_falls=5,
        static_elongation_pct=7.0,
        dynamic_elongation_pct=30.0,
        dry_treated=False,
    )
