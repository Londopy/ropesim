"""
Unit tests for UIAA impact force model.

Reference values computed against the published EN 892 formula:
  F = m·g + √( (m·g)² + 2·m·g·ff·k )

with m = 80 kg, g = 9.81 m/s², various fall factors and stiffnesses.
"""
import math
import pytest

G = 9.81

def _impact_force_ref(mass_kg: float, ff: float, k_kn: float, friction: float = 0.0) -> float:
    """Reference Python implementation of the UIAA formula."""
    mg = mass_kg * G / 1000.0  # kN
    raw = mg + math.sqrt(mg * mg + 2 * mg * ff * k_kn)
    return raw * (1.0 - friction)


class TestImpactForcePython:
    """Validation of the reference formula at known inputs."""

    def test_zero_fall_factor(self):
        # ff = 0 → only static weight
        f = _impact_force_ref(80.0, 0.0, 40.0)
        mg_kn = 80.0 * G / 1000.0
        # F = mg + sqrt(mg^2) = 2*mg
        assert abs(f - 2 * mg_kn) < 0.01

    def test_symmetry_with_mass(self):
        # Heavier climber → higher force at same ff and k
        f_light = _impact_force_ref(60.0, 1.0, 40.0)
        f_heavy = _impact_force_ref(90.0, 1.0, 40.0)
        assert f_heavy > f_light

    def test_force_increases_with_ff(self):
        forces = [_impact_force_ref(80.0, ff, 40.0) for ff in [0.3, 0.7, 1.0, 1.5, 2.0]]
        assert all(forces[i] < forces[i + 1] for i in range(len(forces) - 1))

    def test_force_increases_with_stiffness(self):
        forces = [_impact_force_ref(80.0, 1.0, k) for k in [20.0, 40.0, 60.0, 80.0]]
        assert all(forces[i] < forces[i + 1] for i in range(len(forces) - 1))

    def test_friction_reduces_force(self):
        f_no_friction   = _impact_force_ref(80.0, 1.0, 40.0, friction=0.0)
        f_with_friction = _impact_force_ref(80.0, 1.0, 40.0, friction=0.35)
        assert f_with_friction < f_no_friction

    def test_en892_order_of_magnitude(self):
        # Real EN 892 single rope: impact ~8–12 kN at ff=1.77, k≈40 kN
        f = _impact_force_ref(80.0, 1.77, 40.0)
        assert 6.0 < f < 15.0, f"Force {f:.2f} kN out of expected range"

    def test_stiffness_from_spec_roundtrip(self):
        """Back-calculate k from known (F, ff) and verify the forward formula recovers F."""
        target_f = 9.2  # kN — typical single rope impact
        ff = 1.772
        mg = 80.0 * G / 1000.0
        k = ((target_f - mg) ** 2 - mg ** 2) / (2 * mg * ff)
        recovered = _impact_force_ref(80.0, ff, k)
        assert abs(recovered - target_f) < 0.01, f"Roundtrip failed: {recovered:.4f} vs {target_f}"


@pytest.mark.requires_rust
class TestImpactForceRust:
    def test_zero_ff(self, rustcore):
        f = rustcore.compute_impact_force_uiaa(80.0, 0.0, 40.0, 0.0)
        mg = 80.0 * G / 1000.0
        assert f == pytest.approx(2 * mg, abs=0.05)

    def test_positive_and_finite(self, rustcore):
        for ff in [0.2, 0.5, 1.0, 1.5, 2.0]:
            f = rustcore.compute_impact_force_uiaa(80.0, ff, 40.0, 0.0)
            assert f > 0.0 and math.isfinite(f)

    def test_friction_reduces_force(self, rustcore):
        f0 = rustcore.compute_impact_force_uiaa(80.0, 1.0, 40.0, 0.0)
        f1 = rustcore.compute_impact_force_uiaa(80.0, 1.0, 40.0, 0.35)
        assert f1 < f0

    def test_matches_reference(self, rustcore):
        """Rust result should match Python reference within 1%."""
        ff, k, friction = 1.0, 40.0, 0.35
        ref  = _impact_force_ref(80.0, ff, k, friction)
        rust = rustcore.compute_impact_force_uiaa(80.0, ff, k, friction)
        assert abs(rust - ref) / ref < 0.01, f"Rust={rust:.4f} ref={ref:.4f}"

    def test_stiffness_from_spec(self, rustcore):
        """compute_stiffness_from_spec should yield k s.t. forward formula ≈ original F."""
        target_f = 9.2
        k = rustcore.compute_stiffness_from_spec(target_f, 34.0, 80.0)
        assert k > 0.0
        recovered = rustcore.compute_impact_force_uiaa(80.0, 1.772, k, 0.0)
        assert abs(recovered - target_f) < 0.5, f"Recovered={recovered:.3f} target={target_f}"
