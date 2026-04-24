"""
ropesim.units
=============
SI ↔ Imperial unit conversions used throughout the library.

All primary calculations use SI (kN, kg, m).  Call these helpers when
displaying results to users who prefer Imperial units.
"""

from __future__ import annotations


class Units:
    """Static unit-conversion helpers."""

    # ── Force ────────────────────────────────────────────────────────────────
    @staticmethod
    def kn_to_lbf(kn: float) -> float:
        """kilo-Newtons → pounds-force  (1 kN = 224.809 lbf)."""
        return kn * 224.809

    @staticmethod
    def lbf_to_kn(lbf: float) -> float:
        """pounds-force → kilo-Newtons."""
        return lbf / 224.809

    @staticmethod
    def n_to_lbf(n: float) -> float:
        """Newtons → pounds-force."""
        return n * 0.224809

    @staticmethod
    def lbf_to_n(lbf: float) -> float:
        """pounds-force → Newtons."""
        return lbf / 0.224809

    # ── Mass ─────────────────────────────────────────────────────────────────
    @staticmethod
    def kg_to_lb(kg: float) -> float:
        """kilograms → pounds  (1 kg = 2.20462 lb)."""
        return kg * 2.20462

    @staticmethod
    def lb_to_kg(lb: float) -> float:
        """pounds → kilograms."""
        return lb / 2.20462

    # ── Length ───────────────────────────────────────────────────────────────
    @staticmethod
    def m_to_ft(m: float) -> float:
        """metres → feet  (1 m = 3.28084 ft)."""
        return m * 3.28084

    @staticmethod
    def ft_to_m(ft: float) -> float:
        """feet → metres."""
        return ft / 3.28084

    @staticmethod
    def mm_to_in(mm: float) -> float:
        """millimetres → inches."""
        return mm / 25.4

    @staticmethod
    def in_to_mm(inches: float) -> float:
        """inches → millimetres."""
        return inches * 25.4

    # ── Energy ───────────────────────────────────────────────────────────────
    @staticmethod
    def j_to_ftlbf(j: float) -> float:
        """Joules → foot-pounds-force  (1 J = 0.737562 ft·lbf)."""
        return j * 0.737562

    @staticmethod
    def ftlbf_to_j(ftlbf: float) -> float:
        """foot-pounds-force → Joules."""
        return ftlbf / 0.737562

    # ── Temperature ──────────────────────────────────────────────────────────
    @staticmethod
    def celsius_to_fahrenheit(c: float) -> float:
        return c * 9.0 / 5.0 + 32.0

    @staticmethod
    def fahrenheit_to_celsius(f: float) -> float:
        return (f - 32.0) * 5.0 / 9.0

    # ── Acceleration (g-force) ───────────────────────────────────────────────
    @staticmethod
    def kn_to_g(force_kn: float, mass_kg: float) -> float:
        """Convert kN force to g-force for a given mass."""
        if mass_kg <= 0:
            raise ValueError("mass_kg must be positive")
        return (force_kn * 1000.0) / (mass_kg * 9.81)

    # ── Weight per length ────────────────────────────────────────────────────
    @staticmethod
    def gpm_to_oz_per_ft(gpm: float) -> float:
        """grams-per-metre → ounces-per-foot."""
        return gpm * 0.030481  # 1 g/m = 0.030481 oz/ft

    @staticmethod
    def oz_per_ft_to_gpm(oz_per_ft: float) -> float:
        return oz_per_ft / 0.030481
