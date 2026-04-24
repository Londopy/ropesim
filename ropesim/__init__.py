"""
ropesim — Climbing Rope Physics Engine
=======================================

Public API.

    from ropesim import Rope, Fall, FallConditions, AnchorSystem
    from ropesim import Scenario, Bolt, Cam, Nut, Sling, AnchorType
    from ropesim import units, viz, standards

Rust extension (_rustcore) is compiled via ``maturin develop``.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("ropesim")
except PackageNotFoundError:
    __version__ = "0.1.0-dev"

from ropesim.rope import (
    Rope,
    RopeSpec,
    RopeType,
    RopeStandard,
    RopeDatabase,
)
from ropesim.fall import (
    Fall,
    FallConditions,
    FallResult,
    BelayDevice,
    EnergyBudget,
)
from ropesim.anchor import (
    AnchorSystem,
    AnchorType,
    Bolt,
    BoltType,
    Cam,
    CamPlacement,
    Nut,
    Sling,
    SlingMaterial,
    RockType,
    FailureResult,
)
from ropesim.simulate import (
    Scenario,
    ProtectionPoint,
    SweepResult,
    ZipperResult,
)
from ropesim import units, viz, standards

__all__ = [
    # rope
    "Rope", "RopeSpec", "RopeType", "RopeStandard", "RopeDatabase",
    # fall
    "Fall", "FallConditions", "FallResult", "BelayDevice", "EnergyBudget",
    # anchor
    "AnchorSystem", "AnchorType",
    "Bolt", "BoltType",
    "Cam", "CamPlacement",
    "Nut",
    "Sling", "SlingMaterial",
    "RockType",
    "FailureResult",
    # scenario
    "Scenario", "ProtectionPoint", "SweepResult", "ZipperResult",
    # modules
    "units", "viz", "standards",
]
