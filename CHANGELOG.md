# Changelog

All notable changes to **ropesim** will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

## [0.1.0] - 2026-04-24

### Added
- **Rust core** (`ropesim._rustcore`) via PyO3 + maturin
  - `compute_fall_factor` — UIAA fall factor with clamping & validation
  - `compute_impact_force_uiaa` — full UIAA 101 / EN 892 impact force model
  - `compute_force_curve` — RK4 damped-spring ODE integration
  - `compute_stiffness_from_spec` — back-calculates rope spring constant from EN test data
  - `compute_elongation` — static/dynamic elongation interpolation
  - `compute_diameter_under_load` — radial compression under axial load
  - `compute_energy_budget` — PE / rope / belay / residual energy partitioning
  - `apply_wet_modifier` — EN 892 wet-condition force adjustment
  - `apply_temperature_modifier` — nylon stiffness vs temperature model
  - `sliding_x_distribution` — self-equalizing 2-bolt anchor force model
  - `quad_anchor_distribution` — pre-equalized quad anchor force model
  - `resolve_anchor_forces_2d` — 2-D vector force resolution for arbitrary bolt layouts
- **Python library**
  - `Rope` / `RopeSpec` / `RopeDatabase` with Pydantic v2 validation
  - `Fall` / `FallConditions` / `FallResult` with full simulation pipeline
  - `AnchorSystem` / `Bolt` / `Cam` / `Nut` / `Sling` with effective-MBS modelling
  - `standards.py` — EN 892:2012+A3:2023 and UIAA 101 compliance checks
  - `units.py` — SI ↔ Imperial unit conversions
  - `viz.py` — matplotlib dark-theme plots (force curve, anchor distribution, energy budget, elongation, heatmap, comparison)
- **Database**
  - `ropes.json` seeded with 12 real ropes (Beal, Mammut, Sterling, Black Diamond, Petzl, Edelrid, Tendon, Maxim, BlueWater)
  - `anchors.json` seeded with 10 common hardware entries
- **Tests**
  - Full pytest suite: 7 unit test modules + 2 integration modules
- **CI** (`.github/workflows/ci.yml`) — build wheels for Linux/macOS/Windows on Python 3.11 & 3.12
