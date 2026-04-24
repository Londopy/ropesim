"""
ropesim.gui.models
==================
Observable route model — holds all mutable state for the current session.
Emits Qt signals whenever something changes so the canvas and results panel
can redraw themselves without tight coupling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union

from PySide6.QtCore import QObject, Signal

from ropesim.rope import Rope, RopeDatabase, RopeType
from ropesim.fall import BelayDevice, FallResult
from ropesim.anchor import (
    AnchorSystem, AnchorType, Bolt, BoltType, Cam, CamPlacement,
    Nut, RockType,
)
from ropesim.simulate import Scenario, SweepResult


# ── Gear item (what the canvas tracks) ────────────────────────────────────────

@dataclass
class GearItem:
    """A single piece of protection placed on the route."""

    kind: str            # "bolt" | "cam" | "nut"
    height_m: float      # metres above belay (0 = belay station)
    x_offset: float      # horizontal offset on wall (cosmetic, metres)
    label:  str = ""
    # The underlying pydantic model:
    bolt:   Optional[Bolt] = None
    cam:    Optional[Cam]  = None
    nut:    Optional[Nut]  = None

    @property
    def component(self) -> Union[Bolt, Cam, Nut]:
        if self.kind == "bolt":
            return self.bolt
        if self.kind == "cam":
            return self.cam
        return self.nut

    @property
    def effective_mbs(self) -> float:
        c = self.component
        return c.effective_mbs() if c else 0.0

    def to_anchor_system(self) -> AnchorSystem:
        comp = self.component
        if comp is None:
            comp = Bolt()
        return AnchorSystem(AnchorType.SINGLE_POINT, [comp])


# ── Route model ────────────────────────────────────────────────────────────────

class RouteModel(QObject):
    """
    Central mutable state for the current route.

    All GUI components should read from and write to this model.
    Signals fire whenever any sub-state changes so panels stay in sync.
    """

    # Signals
    rope_changed       = Signal()
    gear_changed       = Signal()          # any gear added / removed / moved
    climber_changed    = Signal()          # climber height or mass changed
    settings_changed   = Signal()          # device, wet, temp, etc.
    result_ready       = Signal(object)    # FallResult
    sweep_ready        = Signal(object)    # SweepResult
    simulation_error   = Signal(str)       # error message string

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)

        # ── Rope ─────────────────────────────────────────────────────────────
        db = RopeDatabase()
        specs = db.load()
        self.rope: Rope = Rope(specs[0]) if specs else self._default_rope()

        # ── Protection ────────────────────────────────────────────────────────
        self.gear: List[GearItem] = []

        # ── Climber ───────────────────────────────────────────────────────────
        self.climber_height_m: float  = 10.0
        self.climber_mass_kg:  float  = 80.0
        self.belay_height_m:   float  = 0.0

        # ── Environment / device ──────────────────────────────────────────────
        self.belay_device:    BelayDevice = BelayDevice.ATC
        self.is_wet:          bool        = False
        self.temperature_c:   float       = 20.0
        self.damping_ratio:   float       = 0.12

        # ── Last simulation result ────────────────────────────────────────────
        self.last_result:       Optional[FallResult]  = None
        self.last_sweep:        Optional[SweepResult] = None
        self.simulation_running: bool                 = False

    # ── Rope ──────────────────────────────────────────────────────────────────

    def set_rope(self, rope: Rope) -> None:
        self.rope = rope
        self.rope_changed.emit()

    def set_rope_by_name(self, name: str) -> bool:
        spec = RopeDatabase().get(name)
        if spec is None:
            return False
        self.rope = Rope(spec)
        self.rope_changed.emit()
        return True

    # ── Gear ──────────────────────────────────────────────────────────────────

    def add_gear(self, item: GearItem) -> None:
        self.gear.append(item)
        self.gear.sort(key=lambda g: g.height_m)
        self.gear_changed.emit()

    def remove_gear(self, index: int) -> None:
        if 0 <= index < len(self.gear):
            self.gear.pop(index)
            self.gear_changed.emit()

    def move_gear(self, index: int, new_height_m: float, new_x: float) -> None:
        if 0 <= index < len(self.gear):
            self.gear[index].height_m = new_height_m
            self.gear[index].x_offset = new_x
            self.gear.sort(key=lambda g: g.height_m)
            self.gear_changed.emit()

    def update_gear(self, index: int, item: GearItem) -> None:
        if 0 <= index < len(self.gear):
            self.gear[index] = item
            self.gear_changed.emit()

    def clear_gear(self) -> None:
        self.gear.clear()
        self.gear_changed.emit()

    # ── Climber ───────────────────────────────────────────────────────────────

    def set_climber_height(self, height_m: float) -> None:
        self.climber_height_m = max(self.belay_height_m, height_m)
        self.climber_changed.emit()

    def set_climber_mass(self, mass_kg: float) -> None:
        self.climber_mass_kg = mass_kg
        self.climber_changed.emit()

    # ── Settings ──────────────────────────────────────────────────────────────

    def set_device(self, device: BelayDevice) -> None:
        self.belay_device = device
        self.settings_changed.emit()

    def set_wet(self, wet: bool) -> None:
        self.is_wet = wet
        self.settings_changed.emit()

    def set_temperature(self, temp_c: float) -> None:
        self.temperature_c = temp_c
        self.settings_changed.emit()

    # ── Build scenario ─────────────────────────────────────────────────────────

    def build_scenario(self) -> Scenario:
        """Create a Scenario from current model state."""
        scenario = Scenario(
            rope             = self.rope,
            climber_mass_kg  = self.climber_mass_kg,
            belay_device     = self.belay_device,
            belay_height_m   = self.belay_height_m,
            is_wet           = self.is_wet,
            temperature_c    = self.temperature_c,
            damping_ratio    = self.damping_ratio,
        )
        for g in self.gear:
            scenario.add_protection(
                g.height_m,
                g.to_anchor_system(),
                label=g.label or g.kind,
            )
        return scenario

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _default_rope() -> Rope:
        from ropesim.rope import RopeSpec, RopeStandard
        spec = RopeSpec(
            name                   = "Default 9.5mm",
            rope_type              = RopeType.SINGLE,
            standard               = RopeStandard.BOTH,
            diameter_mm            = 9.5,
            weight_gpm             = 62.0,
            sheath_percentage      = 40.0,
            impact_force_kn        = 9.2,
            number_of_falls        = 7,
            static_elongation_pct  = 8.5,
            dynamic_elongation_pct = 34.0,
        )
        return Rope(spec)

    def all_rope_names(self) -> list[str]:
        return [s.name for s in RopeDatabase().load()]
