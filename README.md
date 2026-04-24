# RopeSim

**Climbing rope physics engine and GUI simulator — UIAA 101 / EN 892**

RopeSim models lead-fall dynamics using a damped spring / RK4 integration in
Rust, exposed to Python via PyO3/Maturin.  It ships a full Python API, a
five-command CLI, and a PySide6 desktop GUI.

[![CI](https://github.com/Londopy/ropesim/actions/workflows/ci.yml/badge.svg)](https://github.com/Londopy/ropesim/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ropesim)](https://pypi.org/project/ropesim/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/ropesim)](https://pypi.org/project/ropesim/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features

- **UIAA 101 / EN 892** impact-force model with belay-device friction, wet-rope modifier, and temperature correction
- **RK4 force-time curve** — full damped spring integration in Rust for accurate energy modelling
- **Parallel batch sweeps** via Rayon — sweep 200 fall positions in milliseconds
- **Anchor system physics** — sliding-X, quad, 2-bolt cordelette with load distribution
- **25-rope database** covering Beal, Mammut, Sterling, Petzl, Edelrid, Black Diamond, and more
- **PySide6 GUI** — drag-and-drop route builder, live simulation, fall animation, matplotlib plots, PDF/CSV export
- **CLI** — five commands: `simulate`, `anchor`, `list-ropes`, `validate-rope`, `sweep`

---

## Installation

### Pre-built wheel (recommended)

```bash
pip install ropesim            # physics library + CLI only
pip install "ropesim[gui]"     # + PySide6 GUI
```

### From source (requires Rust toolchain)

```bash
git clone https://github.com/Londopy/ropesim.git
cd ropesim
pip install maturin
maturin develop --release      # compiles Rust, installs in editable mode
pip install ".[gui]"           # optional GUI deps
```

---

## Quick start — Python API

```python
from ropesim.rope import RopeDatabase
from ropesim.fall import FallConditions, Fall, BelayDevice

# Load a rope from the bundled database
spec = RopeDatabase().get("Mammut Crag Classic 10.2")

# Simulate a factor-0.5 fall on 20 m of rope
conditions = FallConditions(
    climber_mass_kg=80.0,
    fall_distance_m=10.0,   # fell 2 × 5 m above last pro
    rope_out_m=20.0,
    belay_device=BelayDevice.GRIGRI,
    rope=spec,
)
result = Fall(conditions).simulate()

print(f"Peak impact force : {result.peak_force_kn:.2f} kN")
print(f"Fall factor       : {result.fall_factor:.3f}")
print(f"Energy absorbed   : {result.energy_budget.rope_absorption_j:.0f} J")
print(f"Warnings          : {result.warnings or 'none'}")
```

### Scenario builder (multi-pitch / gear placement)

```python
from ropesim.rope import Rope, RopeDatabase
from ropesim.anchor import AnchorSystem, AnchorType, Bolt
from ropesim.simulate import Scenario

rope = Rope(RopeDatabase().get("Beal Opera 8.5 Dry"))
scenario = Scenario(rope=rope, climber_mass_kg=75.0)

# Place three bolts
for height in [3.0, 7.0, 12.0]:
    anchor = AnchorSystem(AnchorType.SINGLE_POINT, [Bolt(rated_mbs_kn=25.0)])
    scenario.add_protection(height, anchor, label=f"B{int(height)}")

# Simulate a fall from 15 m
result = scenario.simulate_fall(climber_height_m=15.0)
print(f"Peak: {result.peak_force_kn:.2f} kN  FF: {result.fall_factor:.3f}")

# Sweep all positions
sweep = scenario.sweep_fall_positions(steps=60)
print(f"Worst position: {sweep.worst_height_m:.1f} m → {sweep.worst_peak_kn:.2f} kN")
```

### Batch parallel sweep (Rust/Rayon)

```python
from ropesim._rustcore import batch_sweep_fall_factors
import numpy as np

fall_factors = np.linspace(0.1, 2.0, 200).tolist()
peak_forces  = batch_sweep_fall_factors(
    mass_kg=80.0,
    ff_values=fall_factors,
    stiffness_kn=20.0,
    belay_friction=0.35,
)
print(f"Max peak: {max(peak_forces):.2f} kN at FF {fall_factors[peak_forces.index(max(peak_forces))]:.2f}")
```

---

## CLI

```bash
# List all ropes in the database
ropesim-cli list-ropes

# Simulate a single fall
ropesim-cli simulate --mass 80 --fall-distance 8 --rope-out 20 --device grigri

# Anchor force distribution
ropesim-cli anchor --type sliding_x --load-kn 9.5 --angle 60

# Sweep fall positions
ropesim-cli sweep --mass 80 --rope "Beal Opera 8.5 Dry" --steps 50

# Validate rope data
ropesim-cli validate-rope --name "Mammut Crag Classic 10.2"
```

Add `--json` to any command for machine-readable output.

---

## GUI

```bash
ropesim          # launch the desktop GUI (requires pip install "ropesim[gui]")
```

<!-- Screenshot placeholder -->
<!-- ![RopeSim GUI](docs/screenshot.png) -->

**Workflow:**
1. Select a rope from the left panel
2. Double-click the canvas or use the toolbar to place bolts, cams, or nuts
3. Set climber mass and height
4. Press **F5** (or ▶ Run) to simulate a fall — watch the animation
5. Press **F6** to sweep all positions and see the force-vs-height plot
6. Export results as PDF or CSV from the File menu

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `F5` | Run fall simulation |
| `F6` | Sweep all positions |
| `F7` | Zipper analysis |
| `B` / `C` / `N` | Add bolt / cam / nut |
| `F` | Fit canvas to view |
| `Ctrl+Scroll` | Zoom canvas |
| `Middle-drag` | Pan canvas |
| `Delete` | Remove selected gear |

---

## Physics model

The impact force is computed using the UIAA 101 analytic formula:

```
F = mg + √((mg)² + 2·mg·ff·k_eff)
```

where `k_eff` is the length-normalised rope stiffness back-calculated from the
EN 892 test-mass drop (80 kg, fall factor 1.77).  The full force-time curve is
obtained by integrating the damped spring equation with a 4th-order
Runge-Kutta solver at 1 ms resolution.

Modifiers applied:
- **Belay device friction** (Grigri: 55%, ATC: 35%, Munter: 45% …)
- **Wet rope** +12 % impact force (EN 892 §6.1.3)
- **Temperature** — stiffness increases ~2 % per 10 °C below 20 °C
- **Rope age / degradation** — elongation and stiffness drift modelled from
  published UIAA fatigue data

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev,gui]"

# Run tests (no Rust required)
pytest -m "not requires_rust"

# Run full suite (after maturin develop)
pytest

# Benchmarks
pytest -m benchmark --benchmark-only
```

---

## License

MIT — see [LICENSE](LICENSE).
