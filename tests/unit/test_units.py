"""
Unit tests for unit conversions.

All conversions should be invertible (round-trip) within floating-point precision.
"""
import pytest
from ropesim.units import Units


# ── Round-trip invariants ─────────────────────────────────────────────────────

class TestForceConversions:
    def test_kn_lbf_roundtrip(self):
        for kn in [0.0, 1.0, 8.9, 12.0, 100.0]:
            assert Units.lbf_to_kn(Units.kn_to_lbf(kn)) == pytest.approx(kn, rel=1e-9)

    def test_kn_to_lbf_known(self):
        # 1 kN = 224.809 lbf
        assert Units.kn_to_lbf(1.0) == pytest.approx(224.809, rel=1e-4)

    def test_lbf_to_kn_known(self):
        assert Units.lbf_to_kn(224.809) == pytest.approx(1.0, rel=1e-4)

    def test_kn_to_lbf_zero(self):
        assert Units.kn_to_lbf(0.0) == 0.0

    def test_n_lbf_roundtrip(self):
        for n in [0.0, 100.0, 9810.0]:
            assert Units.lbf_to_n(Units.n_to_lbf(n)) == pytest.approx(n, rel=1e-9)


class TestMassConversions:
    def test_kg_lb_roundtrip(self):
        for kg in [0.0, 1.0, 80.0, 100.0]:
            assert Units.lb_to_kg(Units.kg_to_lb(kg)) == pytest.approx(kg, rel=1e-9)

    def test_kg_to_lb_known(self):
        assert Units.kg_to_lb(1.0) == pytest.approx(2.20462, rel=1e-4)

    def test_lb_to_kg_known(self):
        assert Units.lb_to_kg(2.20462) == pytest.approx(1.0, rel=1e-4)


class TestLengthConversions:
    def test_m_ft_roundtrip(self):
        for m in [0.0, 1.0, 20.0, 60.0]:
            assert Units.ft_to_m(Units.m_to_ft(m)) == pytest.approx(m, rel=1e-9)

    def test_m_to_ft_known(self):
        assert Units.m_to_ft(1.0) == pytest.approx(3.28084, rel=1e-4)

    def test_ft_to_m_known(self):
        assert Units.ft_to_m(3.28084) == pytest.approx(1.0, rel=1e-4)

    def test_mm_in_roundtrip(self):
        for mm in [0.0, 9.5, 25.4, 100.0]:
            assert Units.in_to_mm(Units.mm_to_in(mm)) == pytest.approx(mm, rel=1e-9)

    def test_25_4mm_is_1_inch(self):
        assert Units.mm_to_in(25.4) == pytest.approx(1.0, rel=1e-9)


class TestEnergyConversions:
    def test_j_ftlbf_roundtrip(self):
        for j in [0.0, 100.0, 5000.0]:
            assert Units.ftlbf_to_j(Units.j_to_ftlbf(j)) == pytest.approx(j, rel=1e-9)

    def test_1j_in_ftlbf(self):
        assert Units.j_to_ftlbf(1.0) == pytest.approx(0.737562, rel=1e-4)


class TestTemperatureConversions:
    def test_celsius_fahrenheit_roundtrip(self):
        for c in [-20.0, 0.0, 20.0, 37.0]:
            assert Units.fahrenheit_to_celsius(Units.celsius_to_fahrenheit(c)) == pytest.approx(c, abs=1e-9)

    def test_0c_is_32f(self):
        assert Units.celsius_to_fahrenheit(0.0) == pytest.approx(32.0)

    def test_100c_is_212f(self):
        assert Units.celsius_to_fahrenheit(100.0) == pytest.approx(212.0)


class TestGForce:
    def test_g_force_calculation(self):
        # 9.81 kN on 100 kg mass = 10.0 g (approx)
        g = Units.kn_to_g(9.81, 100.0)
        assert g == pytest.approx(10.0, rel=0.01)

    def test_zero_mass_raises(self):
        with pytest.raises(ValueError):
            Units.kn_to_g(10.0, 0.0)

    def test_1g_at_body_weight(self):
        # 80 kg climber hanging static = 80kg × 9.81 / 1000 = 0.7848 kN = 1g
        force_kn = 80.0 * 9.81 / 1000.0
        g = Units.kn_to_g(force_kn, 80.0)
        assert g == pytest.approx(1.0, rel=0.001)
