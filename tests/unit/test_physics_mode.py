"""
Unit tests for v0.2.0 simulate.py additions:
  - PhysicsMode enum
  - ScenarioType enum
  - RockFaceGeometry (presets + from_obj)
  - Scenario.simulate_fall with mode parameter
  - simulate_fall_async / sweep_fall_positions_async
"""
import asyncio
import math
import os
import tempfile
import pytest

from ropesim.simulate import (
    PhysicsMode,
    ScenarioType,
    RockFaceGeometry,
    Scenario,
)
from ropesim.rope import Rope, RopeSpec, RopeType
from ropesim.anchor import AnchorSystem, AnchorType, Bolt


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def spec():
    return RopeSpec(
        name="PhysicsMode Test 9.5",
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
def bolt():
    return AnchorSystem(AnchorType.SINGLE_POINT, [Bolt(rated_mbs_kn=25.0)])


@pytest.fixture
def scenario(rope, bolt):
    s = Scenario(rope=rope, climber_mass_kg=80.0)
    s.add_protection(5.0,  bolt)
    s.add_protection(10.0, bolt)
    return s


# ── PhysicsMode enum ──────────────────────────────────────────────────────────

class TestPhysicsMode:
    def test_analytical_value(self):
        assert PhysicsMode.ANALYTICAL == "analytical"

    def test_rapier_3d_value(self):
        assert PhysicsMode.RAPIER_3D == "rapier_3d"

    def test_is_str_enum(self):
        assert isinstance(PhysicsMode.ANALYTICAL, str)
        assert isinstance(PhysicsMode.RAPIER_3D, str)

    def test_from_string(self):
        assert PhysicsMode("analytical") is PhysicsMode.ANALYTICAL
        assert PhysicsMode("rapier_3d")  is PhysicsMode.RAPIER_3D

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            PhysicsMode("invalid_mode")


# ── ScenarioType enum ─────────────────────────────────────────────────────────

class TestScenarioType:
    def test_all_values_exist(self):
        assert ScenarioType.LEAD_FALL == "lead_fall"
        assert ScenarioType.TOP_ROPE  == "top_rope"
        assert ScenarioType.RAPPEL    == "rappel"
        assert ScenarioType.HAUL      == "haul"
        assert ScenarioType.LOWER     == "lower"

    def test_from_string(self):
        assert ScenarioType("lead_fall") is ScenarioType.LEAD_FALL

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            ScenarioType("free_solo")


# ── RockFaceGeometry presets ──────────────────────────────────────────────────

class TestRockFaceGeometry:
    def test_vertical_slab_defaults(self):
        face = RockFaceGeometry.vertical_slab()
        assert len(face.vertices) == 4
        assert face.friction == pytest.approx(0.5)
        assert face.preset_name == RockFaceGeometry.VERTICAL_SLAB

    def test_vertical_slab_custom_size(self):
        face = RockFaceGeometry.vertical_slab(width_m=8.0, height_m=50.0)
        xs = [v[0] for v in face.vertices]
        assert min(xs) == pytest.approx(-4.0)
        assert max(xs) == pytest.approx(4.0)

    def test_overhang_defaults(self):
        face = RockFaceGeometry.overhang()
        assert len(face.vertices) == 4
        assert face.friction == pytest.approx(0.4)

    def test_overhang_angle_creates_lean(self):
        face = RockFaceGeometry.overhang(angle_deg=30.0, height_m=40.0)
        zs = [v[2] for v in face.vertices]
        expected_lean = 40.0 * math.tan(math.radians(30.0))
        assert max(zs) == pytest.approx(expected_lean, rel=0.01)

    def test_overhang_zero_angle_no_lean(self):
        face = RockFaceGeometry.overhang(angle_deg=0.0)
        zs = [v[2] for v in face.vertices]
        assert max(abs(z) for z in zs) < 1e-9

    def test_from_obj_loads_vertices(self):
        obj_content = (
            "# simple square\n"
            "v -1.0 0.0 0.0\n"
            "v  1.0 0.0 0.0\n"
            "v  1.0 2.0 0.0\n"
            "v -1.0 2.0 0.0\n"
            "f 1 2 3 4\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as fh:
            fh.write(obj_content)
            tmp_path = fh.name
        try:
            face = RockFaceGeometry.from_obj(tmp_path)
            assert len(face.vertices) == 4
            assert face.vertices[0] == pytest.approx([-1.0, 0.0, 0.0])
        finally:
            os.unlink(tmp_path)

    def test_from_obj_ignores_non_vertex_lines(self):
        obj_content = "# comment\nvn 0 0 1\nvt 0.5 0.5\nv 1 2 3\nf 1 1 1\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as fh:
            fh.write(obj_content)
            tmp_path = fh.name
        try:
            face = RockFaceGeometry.from_obj(tmp_path)
            assert len(face.vertices) == 1
        finally:
            os.unlink(tmp_path)

    def test_custom_friction(self):
        face = RockFaceGeometry.vertical_slab(friction=0.8)
        assert face.friction == pytest.approx(0.8)


# ── Scenario.simulate_fall with PhysicsMode ───────────────────────────────────

class TestSimulateFallPhysicsMode:
    pytestmark = pytest.mark.requires_rust

    def test_analytical_mode_returns_result(self, scenario):
        from ropesim.fall import FallResult
        result = scenario.simulate_fall(12.0, mode=PhysicsMode.ANALYTICAL)
        assert isinstance(result, FallResult)

    def test_analytical_mode_default(self, scenario):
        from ropesim.fall import FallResult
        result = scenario.simulate_fall(12.0)
        assert isinstance(result, FallResult)

    def test_analytical_peak_force_positive(self, scenario):
        result = scenario.simulate_fall(12.0, mode=PhysicsMode.ANALYTICAL)
        assert result.peak_force_kn > 0.0


# ── Async API ─────────────────────────────────────────────────────────────────

class TestAsyncAPI:
    pytestmark = pytest.mark.requires_rust

    def test_simulate_fall_async_returns_result(self, scenario):
        from ropesim.fall import FallResult
        result = asyncio.run(scenario.simulate_fall_async(12.0))
        assert isinstance(result, FallResult)
        assert result.peak_force_kn > 0.0

    def test_sweep_fall_positions_async(self, scenario):
        from ropesim.simulate import SweepResult
        result = asyncio.run(scenario.sweep_fall_positions_async(steps=4))
        assert isinstance(result, SweepResult)
        assert len(result.peak_forces_kn) == 4
