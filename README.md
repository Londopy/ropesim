# RopeSim

**Climbing rope physics engine and GUI simulator**

RopeSim models lead-fall dynamics using a damped spring / RK4 integration in
Rust, exposed to Python via PyO3/Maturin.  It ships a full Python API, an
expanded CLI with 20+ commands, a PySide6 desktop GUI with a 3D Vispy viewport,
Jupyter notebook integration, and an optional Rapier3D full-physics simulation
mode.

[![CI](https://github.com/Londopy/ropesim/actions/workflows/ci.yml/badge.svg)](https://github.com/Londopy/ropesim/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ropesim)](https://pypi.org/project/ropesim/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/ropesim)](https://pypi.org/project/ropesim/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features

- **UIAA 101 / EN 892** impact-force model with belay-device friction, wet-rope modifier, and temperature correction
- **RK4 force-time curve** — full damped spring integration in Rust for accurate energy modelling
- **Rapier3D full-physics mode** — rope modelled as a capsule-chain rigid-body simulation (optional)
- **Parallel batch sweeps** via Rayon — sweep 200 fall positions in milliseconds
- **Anchor system physics** — sliding-X, quad, cordelette, trad gear with load distribution and progressive failure
- **Guide-mode self-locking belay devices** — Reverso Guide, Mega Jul, Giga Jul, Click Up, I-Device, Sum with load-dependent friction model
- **Mechanical advantage / haul systems** — 3:1, 5:1, 6:1, piggyback with friction-corrected MA
- **Top-rope and rappel models** — catch and anchor-load estimation
- **Rope diameter under load** — estimates radial compression at any applied force
- **Rope degradation model** — stiffness and impact-force drift with falls taken
- **25-rope database** covering Beal, Mammut, Sterling, Petzl, Edelrid, Black Diamond, and more
- **PySide6 GUI** — drag-and-drop route builder, live simulation, 2D/3D viewport toggle, fall animation, matplotlib plots, PDF/CSV export
- **3D Vispy viewport** — rope tension heatmap, gear load markers, climber tracker, force arrows, turntable camera, frame-scrubber playback
- **Jupyter notebook integration** — rich HTML/SVG repr for Rope, FallResult, AnchorSystem; five example notebooks
- **CLI** — 20+ commands across `rope`, `scenario`, `validate`, `report`, `toprope`, `rappel`, `haul`, and `interactive` subcommand groups

---

## Installation

### Pre-built wheel (recommended)

```bash
pip install ropesim                  # physics library + CLI only
pip install "ropesim[gui]"           # + PySide6 GUI (2D canvas)
pip install "ropesim[gui,vispy]"     # + 3D Vispy viewport
```

Or grab everything at once:

```bash
pip install "ropesim[all]"
```

### From source (requires Rust toolchain)

```bash
git clone https://github.com/Londopy/ropesim.git
cd ropesim
pip install maturin
maturin develop --release      # compiles Rust, installs in editable mode
pip install -e ".[all]"        # optional GUI + notebook deps
```

> **Python 3.14+** users building from source need one extra step:
> `set PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` (Windows) or
> `export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` (Linux/macOS) before running
> `maturin develop`. PyPI wheel installs are unaffected.

---

## Demo

A self-contained demo script exercises every feature of the library and saves
eight matplotlib plots to your working directory:

```bash
python demo.py
```

This covers: units, standards lookup, rope database search, rope physics
helpers, fall simulation, anchor systems, scenario builder, sweep and zipper
analysis, visualisations, and the low-level Rust core API.

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
    fall_distance_m=10.0,   # fell 2 x 5 m above last pro
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

### Guide-mode self-locking belay devices

```python
from ropesim.fall import BelayDevice, FallConditions, Fall
from ropesim.simulate import compute_effective_friction, is_guide_mode

device = BelayDevice.REVERSO_GUIDE

# Check if it uses the self-locking model
print(is_guide_mode(device))  # True

# Effective friction increases with load
for kn in [3.0, 6.0, 9.0, 12.0]:
    mu = compute_effective_friction(device, kn)
    print(f"{kn:.0f} kN -> mu_eff = {mu:.3f}")

# Simulate — guide-mode friction solved automatically
conditions = FallConditions(
    climber_mass_kg=80.0,
    fall_distance_m=8.0,
    rope_out_m=18.0,
    belay_device=device,
    rope=RopeDatabase().get("Beal Opera 8.5 Dry"),
)
result = Fall(conditions).simulate()
print(f"Guide-mode active : {result.guide_mode_used}")
print(f"Peak force        : {result.peak_force_kn:.2f} kN")
```

### Rapier3D full-physics mode

```python
from ropesim.simulate import Scenario, PhysicsMode, ScenarioType
from ropesim.rope import Rope, RopeDatabase
from ropesim.anchor import AnchorSystem, AnchorType, Bolt

rope = Rope(RopeDatabase().get("Mammut Crag Classic 10.2"))
scenario = Scenario(rope=rope, climber_mass_kg=80.0)

for h in [4.0, 9.0, 14.0]:
    scenario.add_protection(h, AnchorSystem(AnchorType.SINGLE_POINT, [Bolt(rated_mbs_kn=25.0)]))

# Full Rapier3D rigid-body simulation
result = scenario.simulate_fall(
    climber_height_m=16.0,
    mode=PhysicsMode.RAPIER_3D,
)
print(f"Physics mode : {result.mode}")
print(f"Peak force   : {result.peak_force_kn:.2f} kN")
print(f"Frames       : {len(result.frames)}")

# Frame-by-frame playback
from ropesim.replay import SimulationReplay
replay = SimulationReplay(result.frames)
print(f"Duration     : {replay.total_time_seconds:.2f} s")
print(f"Peak anchor  : {replay.peak_anchor_force_kn():.2f} kN")
peak_frame = replay.peak_force_frame()
print(f"Rope shape at peak: {replay.frame(peak_frame).link_positions[:3]}")
```

### Rope physics helpers

```python
from ropesim.rope import Rope, RopeDatabase

rope = Rope(RopeDatabase().get("Beal Opera 8.5 Dry"))

# Elongation at a given force
print(rope.elongation_at_force(9.0))         # metres

# Estimated rope diameter under load
for kn in [0, 3, 6, 9, 12]:
    print(f"{kn} kN -> {rope.diameter_under_load(kn):.3f} mm")

# Degradation after repeated falls
worn = rope.degrade(falls_taken=10)
print(worn.retirement_warning(falls_taken=10))

# EN 892 / UIAA 101 compliance check
print(rope.validate_standard_compliance())
```

### Scenario builder (multi-pitch / gear placement)

```python
from ropesim.rope import Rope, RopeDatabase
from ropesim.anchor import AnchorSystem, AnchorType, Bolt
from ropesim.simulate import Scenario

rope = Rope(RopeDatabase().get("Beal Opera 8.5 Dry"))
scenario = Scenario(rope=rope, climber_mass_kg=75.0)

for height in [3.0, 7.0, 12.0]:
    anchor = AnchorSystem(AnchorType.SINGLE_POINT, [Bolt(rated_mbs_kn=25.0)])
    scenario.add_protection(height, anchor, label=f"B{int(height)}")

# Simulate a fall from 15 m
result = scenario.simulate_fall(climber_height_m=15.0)
print(f"Peak: {result.peak_force_kn:.2f} kN  FF: {result.fall_factor:.3f}")

# Sweep all positions
sweep = scenario.sweep_fall_positions(steps=60)
print(f"Worst position: {sweep.worst_height_m:.1f} m -> {sweep.worst_peak_kn:.2f} kN")

# Zipper failure cascade
zipper = scenario.simulate_zipper(climber_height_m=15.0)
print(f"Pieces failed: {zipper.total_pieces_failed}  ground fall: {zipper.ground_fall_reached}")
```

### Haul systems and top-rope / rappel models

```python
from ropesim._rustcore import (
    compute_haul_system_force, HaulSystem,
    compute_top_rope_impact,
    compute_rappel_load,
)

# 3:1 Z-pulley haul system
haul = compute_haul_system_force(load_kg=80.0, system=HaulSystem.ThreeToOne, friction_loss=0.12)
print(f"Theoretical MA : {haul.theoretical_ma}")
print(f"Actual MA      : {haul.actual_ma:.2f}  (friction corrected)")
print(f"Hauler effort  : {haul.hauler_effort_n / 1000:.2f} kN")

# Top-rope catch
tr = compute_top_rope_impact(stiffness_kn=18.0, mass_kg=75.0, slack_m=0.5,
                              rope_length_m=25.0, friction=0.35)
print(f"Top-rope peak  : {tr:.2f} kN")

# Rappel anchor load
rappel = compute_rappel_load(mass_kg=80.0, friction=0.25, speed_mps=1.2, sudden_stop=False)
print(f"Rappel load    : {rappel:.2f} kN")
```

### Anchor systems

```python
from ropesim.anchor import AnchorSystem, AnchorType, Bolt, BoltType, RockType

bolt = Bolt(bolt_type=BoltType.GLUE_IN, rated_mbs_kn=25.0,
            age_years=3, rock_type=RockType.GRANITE)
anchor = AnchorSystem(AnchorType.SLIDING_X, [bolt, bolt])

# Force on each component vs load angle
dist = anchor.load_distribution(load_kn=9.0, load_angle_deg=30)
print(dist)

# How much of each bolt's MBS is left
margins = anchor.safety_margins(load_kn=9.0)
print(margins)

# Progressive failure under extreme load
failure = anchor.simulate_failure(load_kn=40.0)
print(f"Cascade: {failure.cascade_occurred}  failed: {failure.failed_indices}")
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

### Visualisations

```python
from ropesim import viz
import matplotlib.pyplot as plt

# Force-time curve
fig, ax = viz.plot_force_curve(result, dark=True)

# Energy budget breakdown
fig, ax = viz.plot_energy_budget(result, dark=True)

# Rope elongation vs applied force
fig, ax = viz.plot_rope_elongation(rope, force_range=(0, 15), dark=True)

# Rope diameter under load
fig, ax = viz.plot_diameter_under_load(rope, force_range=(0, 12), dark=True)

# Anchor force distribution vs load angle
fig, ax = viz.plot_anchor_distribution(anchor, load_kn=9.0, dark=True)

# Compare multiple ropes / scenarios on one chart
fig, ax = viz.plot_comparison([result1, result2], ["Rope A", "Rope B"], dark=True)

plt.show()
```

### Jupyter notebook integration

RopeSim ships rich HTML reprs for all major objects — they render automatically
in JupyterLab and VS Code notebooks without any extra calls.

```python
import ropesim.notebook  # activates _repr_html_ patches

rope     # renders as HTML spec card with EN 892 compliance badge
result   # renders as summary table + inline force-time curve PNG
anchor   # renders as inline SVG bolt-and-sling diagram
```

Five example notebooks are included in `notebooks/`:

| Notebook | Contents |
|----------|----------|
| `01_basic_fall_simulation.ipynb` | Fundamentals, device comparison, force curve |
| `02_anchor_comparison.ipynb` | Sliding-X / quad / cordelette angle sweep, heatmaps |
| `03_rope_database_exploration.ipynb` | Scatter plots, bar charts, retirement calculator |
| `04_scenario_builder.ipynb` | Trad pitch, position sweep, zipper analysis |
| `05_rapier_3d_simulation.ipynb` | PyRopeSimWorld, SimulationReplay, 3D link plots |

---

## CLI

RopeSim ships a unified `ropesim-cli` entry point with subcommand groups.

```bash
# ---- Rope database ----
ropesim-cli rope list                              # all ropes
ropesim-cli rope list --type dry_single --diameter 9.5
ropesim-cli rope show "Beal Opera 8.5 Dry"        # full spec card
ropesim-cli rope compare "Beal Opera 8.5 Dry" "Mammut Crag Classic 10.2"
ropesim-cli rope add                               # interactive prompt
ropesim-cli rope import --file my_rope.json
ropesim-cli rope retire "Mammut Crag Classic 10.2" --falls-taken 40

# ---- Scenario runner ----
ropesim-cli scenario run    --file pitch.json --height 15
ropesim-cli scenario sweep  --file pitch.json
ropesim-cli scenario zipper --file pitch.json --height 15
ropesim-cli scenario build                         # interactive builder

# ---- Validation ----
ropesim-cli validate rope     --name "Mammut Crag Classic 10.2"
ropesim-cli validate scenario --file pitch.json
ropesim-cli validate system   --rope "Beal Opera 8.5 Dry" --load 80

# ---- Reports ----
ropesim-cli report --scenario pitch.json           # multi-page PDF

# ---- Specialty calculations ----
ropesim-cli toprope --rope "Beal Opera 8.5 Dry" --slack 0.5
ropesim-cli rappel  --mass 80
ropesim-cli haul    --system 3:1 --load 80

# ---- Classic commands (still available) ----
ropesim-cli simulate --mass 80 --fall-dist 8 --rope-out 20 \
    --rope "Beal Opera 8.5 Dry" --device grigri
ropesim-cli anchor --type sliding_x --load 9.5 --angle 60
ropesim-cli sweep  --rope "Mammut Crag Classic 10.2" --mass 80 --steps 20
ropesim-cli validate-rope --name "Mammut Crag Classic 10.2"
ropesim-cli list-ropes

# ---- REPL ----
ropesim-cli interactive        # Python REPL with all ropesim symbols pre-loaded
```

Add `--format json` (or `--json` on classic commands) to any command for
machine-readable output.

---

## GUI

```bash
ropesim          # launch the desktop GUI (requires pip install "ropesim[gui]")
```

### Demo mode

The fastest way to see everything in action: click **Demo Route** in the left
panel (or press `F8`).

It automatically builds a realistic mixed trad/sport route, runs a fall
simulation and a full position sweep, and mirrors the result to the 3D viewport.

**Manual workflow:**
1. Select a rope from the left panel
2. Click **+ Bolt**, **+ Cam**, or **+ Nut** to place protection on the wall
3. Set climber mass and height
4. Press **Run Fall Simulation** — watch the animation, results appear in the right panel
5. Press **Sweep All Positions** to see peak force vs climber height across the whole route
6. **Zipper Analysis** models sequential gear-ripping under high loads
7. Toggle **[2D] / [3D]** in the toolbar to switch between the 2D canvas and the 3D Vispy viewport
8. Toggle **[Analytical] / [Rapier 3D]** to switch physics modes (3D mode mirrors to 3D viewport automatically)
9. Export results as PDF or CSV from the File menu

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `F8` | Demo route (auto-build + simulate) |
| `F5` | Run fall simulation |
| `F6` | Sweep all positions |
| `F7` | Zipper analysis |
| `B` / `C` / `N` | Add bolt / cam / nut |
| `F` | Fit canvas to view |
| `Ctrl+Scroll` | Zoom canvas |
| `Middle-drag` | Pan canvas |
| `Delete` | Remove selected gear |
| `R` (3D view) | Reset camera |

**3D viewport controls (when 3D tab is active):**

| Input | Action |
|-------|--------|
| Left-drag | Orbit / turntable rotate |
| Middle-drag | Pan |
| Scroll | Zoom |
| `R` | Reset to default view |
| Front / Side / Top / Iso buttons | Preset camera angles |
| Play / Pause / Stop bar | Frame-by-frame Rapier playback |
| Speed selector | 0.1x to 2x playback speed |

---

## Physics model

### Analytical mode (default)

The impact force is computed using the UIAA 101 analytic formula:

```
F = mg + sqrt((mg)^2 + 2*mg*ff*k_eff)
```

where `k_eff` is the length-normalised rope stiffness back-calculated from the
EN 892 test-mass drop (80 kg, fall factor 1.77).  The full force-time curve is
obtained by integrating the damped spring equation with a 4th-order
Runge-Kutta solver at 1 ms resolution.

Modifiers applied:

- **Belay device friction** (Grigri: 55 %, ATC: 35 %, Munter: 45 % ...)
- **Guide-mode self-locking friction** for Reverso Guide / Mega Jul / Giga Jul / Click Up / I-Device / Sum: `mu_eff(F) = min(mu_base + k_lock * F_kN, mu_max)`, solved by fixed-point iteration
- **Wet rope** +12 % impact force (EN 892 s.6.1.3)
- **Temperature** — stiffness increases ~2 % per 10 deg C below 20 deg C
- **Rope age / degradation** — elongation and stiffness drift modelled from published UIAA fatigue data
- **Edge friction** — rope running over a ledge reduces effective belay friction

### Rapier 3D mode (optional)

When `PhysicsMode.RAPIER_3D` is requested, the rope is modelled as a chain of
capsule rigid bodies connected by `SphericalJoint` constraints inside a full
Rapier3D 0.21 pipeline (broad phase, narrow phase, CCD, island manager).

Force estimation uses mom