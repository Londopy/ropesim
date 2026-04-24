"""
demo.py — RopeSim feature tour
==============================
Run this file to see every major feature of the ropesim library in action.

    python demo.py

The Rust extension must be installed first:
    pip install ropesim              # from PyPI (recommended)
    # or, from source:
    maturin develop --release && pip install -e ".[all]"
"""

import textwrap

# ── helpers ───────────────────────────────────────────────────────────────────

def section(title: str) -> None:
    width = 70
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print('═' * width)

def sub(title: str) -> None:
    print(f"\n── {title} {'─' * max(0, 64 - len(title))}")


# ═════════════════════════════════════════════════════════════════════════════
# 1.  UNITS
# ═════════════════════════════════════════════════════════════════════════════
section("1. Units — conversion helpers")

from ropesim.units import Units

print(f"  12 kN  → {Units.kn_to_lbf(12):.1f} lbf")
print(f"  2700 lbf → {Units.lbf_to_kn(2700):.2f} kN")
print(f"  80 kg  → {Units.kg_to_lb(80):.1f} lb")
print(f"  6.0 m  → {Units.m_to_ft(6.0):.2f} ft")
print(f"  10 mm  → {Units.mm_to_in(10):.3f} in")
print(f"  1000 J → {Units.j_to_ftlbf(1000):.1f} ft·lbf")
print(f"  -15 °C → {Units.celsius_to_fahrenheit(-15):.1f} °F")
print(f"  12 kN on 80 kg climber → {Units.kn_to_g(12.0, 80.0):.2f} g")
print(f"  62 g/m → {Units.gpm_to_oz_per_ft(62):.3f} oz/ft")


# ═════════════════════════════════════════════════════════════════════════════
# 2.  STANDARDS reference
# ═════════════════════════════════════════════════════════════════════════════
section("2. Standards — EN 892 / UIAA 101 limits")

from ropesim import standards

print(f"  Max impact force (single): {standards.MAX_IMPACT_FORCE_KN['single']} kN")
print(f"  Max impact force (half):   {standards.MAX_IMPACT_FORCE_KN['half']} kN")
print(f"  Min UIAA falls (single):   {standards.MIN_FALLS['single']}")
print(f"  Max static elongation:     {standards.MAX_STATIC_ELONGATION_PCT['single']} %")
print(f"  Max dynamic elongation:    {standards.MAX_DYNAMIC_ELONGATION_PCT['single']} %")
print(f"  Bolt min MBS recommended:  {standards.BOLT_MIN_RECOMMENDED_MBS_KN} kN")
print(f"  Connector major-axis MBS:  {standards.CONNECTOR_MAJOR_AXIS_MBS_KN} kN")


# ═════════════════════════════════════════════════════════════════════════════
# 3.  ROPE DATABASE
# ═════════════════════════════════════════════════════════════════════════════
section("3. Rope database — search & lookup")

from ropesim.rope import Rope, RopeDatabase, RopeType

db = RopeDatabase()
print(f"  Total ropes in database: {len(db)}")

sub("3a. List all single ropes")
singles = db.search(rope_type=RopeType.SINGLE)
for s in singles[:5]:
    print(f"  {s.name:<35} {s.diameter_mm} mm  {s.impact_force_kn} kN  {s.number_of_falls} falls")
if len(singles) > 5:
    print(f"  … and {len(singles) - 5} more")

sub("3b. Search by keyword")
results = db.search(query="dry")
print(f"  'dry' search → {len(results)} ropes")
for r in results[:3]:
    print(f"    {r.name}")

sub("3c. Get a specific rope and inspect its spec")
spec = db.get("Beal Opera 8.5 Dry")
print(f"  Name:             {spec.name}")
print(f"  Manufacturer:     {spec.manufacturer}")
print(f"  Diameter:         {spec.diameter_mm} mm")
print(f"  Weight:           {spec.weight_gpm} g/m")
print(f"  Impact force:     {spec.impact_force_kn} kN")
print(f"  UIAA falls:       {spec.number_of_falls}")
print(f"  Dyn. elongation:  {spec.dynamic_elongation_pct} %")
print(f"  Stat. elongation: {spec.static_elongation_pct} %")
print(f"  Dry treated:      {spec.dry_treated}")
print(f"  Rope type:        {spec.rope_type.value}")


# ═════════════════════════════════════════════════════════════════════════════
# 4.  ROPE class — physics helpers
# ═════════════════════════════════════════════════════════════════════════════
section("4. Rope — physics helpers")

rope = Rope(spec)

sub("4a. Effective stiffness")
print(f"  Effective stiffness: {rope.effective_stiffness():.2f} kN")

sub("4b. Elongation at various forces")
for kn in [1.0, 5.0, 9.0, 12.0]:
    elong = rope.elongation_at_force(kn)
    pct = (elong / spec.length_m - 1.0) * 100 if spec.length_m else 0
    print(f"  {kn:5.1f} kN → rope length {elong:.2f} m  ({pct:+.1f} %)")

sub("4c. Diameter under load")
for kn in [0.0, 3.0, 6.0, 9.0, 12.0]:
    d = rope.diameter_under_load(kn)
    print(f"  {kn:5.1f} kN → diameter {d:.3f} mm")

sub("4d. Degradation with falls")
degraded = rope.degrade(falls_taken=10)
print(f"  After 10 falls — impact force: {degraded.spec.impact_force_kn:.2f} kN  "
      f"(was {spec.impact_force_kn} kN)")
warn = rope.retirement_warning(falls_taken=10)
print(f"  Retirement warning: {warn or 'none'}")

sub("4e. Standard compliance check")
violations = rope.validate_standard_compliance()
if violations:
    for v in violations:
        print(f"  ⚠ {v}")
else:
    print("  ✓ All EN 892 / UIAA 101 checks passed")

sub("4f. JSON round-trip")
json_str = rope.to_json()
rope2 = Rope.from_json(json_str)
print(f"  Serialised → deserialised: {rope2.spec.name!r} ✓")


# ═════════════════════════════════════════════════════════════════════════════
# 5.  FALL SIMULATION
# ═════════════════════════════════════════════════════════════════════════════
section("5. Fall simulation")

from ropesim.fall import FallConditions, Fall, BelayDevice

sub("5a. Basic fall — GriGri, 10 m rope out, 4 m above last bolt")
conditions = FallConditions(
    climber_mass_kg=80.0,
    fall_distance_m=8.0,     # 2 × 4 m above last bolt
    rope_out_m=10.0,
    belay_device=BelayDevice.GRIGRI,
    rope=spec,
)
result = Fall(conditions).simulate()
print(f"  Fall factor:       {result.fall_factor:.3f}")
print(f"  Peak force:        {result.peak_force_kn:.2f} kN  ({result.peak_force_lbf:.0f} lbf)")
print(f"  Peak deceleration: {result.peak_deceleration_g:.1f} g")
print(f"  Rope elongation:   {result.elongation_m:.3f} m")
print(f"  Rope survived:     {result.rope_survived}")
budget = result.energy_budget
print(f"  Energy — potential:{budget.potential_energy_j:.0f} J  "
      f"rope:{budget.rope_absorption_j:.0f} J  "
      f"belay:{budget.belay_device_j:.0f} J  "
      f"residual:{budget.residual_j:.0f} J")
if result.warnings:
    for w in result.warnings:
        print(f"  ⚠ {w}")

sub("5b. Wet rope, cold temperature, ATC")
cond2 = FallConditions(
    climber_mass_kg=80.0,
    fall_distance_m=8.0,
    rope_out_m=10.0,
    belay_device=BelayDevice.ATC,
    rope=spec,
    is_wet=True,
    temperature_celsius=-10.0,
)
result2 = Fall(cond2).simulate()
print(f"  Peak force (wet, -10 °C, ATC): {result2.peak_force_kn:.2f} kN")
print(f"  Warnings: {len(result2.warnings)}")
for w in result2.warnings:
    print(f"    • {w}")

sub("5c. Force-time curve (numpy)")
import numpy as np
curve = Fall(conditions).force_curve_numpy()
print(f"  Curve shape: {curve.shape}  (timesteps × 1)")
print(f"  Peak in curve: {curve.max():.3f} kN  at t={curve.argmax()} ms")

sub("5d. Belay device comparison")
devices = [BelayDevice.MUNTER, BelayDevice.ATC, BelayDevice.ATC_GUIDE,
           BelayDevice.GRIGRI, BelayDevice.GRIGRI_PLUS]
base = dict(climber_mass_kg=80.0, fall_distance_m=8.0, rope_out_m=10.0, rope=spec)
for dev in devices:
    r = Fall(FallConditions(**base, belay_device=dev)).simulate()
    print(f"  {dev.value:<14} → {r.peak_force_kn:.2f} kN")

sub("5e. Fall factor quick-check")
ff = Fall(conditions).fall_factor()
print(f"  Fall factor (standalone): {ff:.4f}")


# ═════════════════════════════════════════════════════════════════════════════
# 6.  ANCHOR SYSTEM
# ═════════════════════════════════════════════════════════════════════════════
section("6. Anchor system")

from ropesim.anchor import (
    AnchorSystem, AnchorType, Bolt, Cam, Nut, Sling,
    BoltType, RockType, CamPlacement, SlingMaterial,
)

sub("6a. Two-bolt sliding-X, load distribution vs angle")
bolt_a = Bolt(bolt_type=BoltType.GLUE_IN, rated_mbs_kn=25.0,
              age_years=2, rock_type=RockType.GRANITE)
bolt_b = Bolt(bolt_type=BoltType.GLUE_IN, rated_mbs_kn=25.0,
              age_years=2, rock_type=RockType.GRANITE)
anchor = AnchorSystem(AnchorType.SLIDING_X, [bolt_a, bolt_b])

for angle in [0, 30, 60, 90]:
    dist = anchor.load_distribution(load_kn=9.0, load_angle_deg=angle)
    parts = "  ".join(f"{k}: {v:.2f} kN" for k, v in dist.items())
    print(f"  {angle:3d}°  {parts}")

sub("6b. Safety margins")
margins = anchor.safety_margins(load_kn=9.0)
for comp, pct in margins.items():
    print(f"  {comp}: {pct:.1f} % of MBS remaining")

sub("6c. Weakest component")
weak = anchor.weakest_component()
print(f"  Weakest: {type(weak).__name__}  effective MBS = {weak.effective_mbs():.2f} kN")

sub("6d. Redundancy check")
print(f"  Is redundant: {anchor.is_redundant()}")

sub("6e. Cam placement quality")
cam = Cam(brand="Black Diamond", size="0.75", rated_mbs_kn=12.0,
          placement=CamPlacement.GOOD, rock_type=RockType.GRANITE, walking_risk=False)
print(f"  Cam effective MBS:       {cam.effective_mbs():.2f} kN")
print(f"  Cam placement score:     {cam.placement_quality_score():.2f}")

sub("6f. Nut")
nut = Nut(rated_mbs_kn=9.0, placement=CamPlacement.PERFECT, rock_type=RockType.LIMESTONE)
print(f"  Nut effective MBS: {nut.effective_mbs():.2f} kN")

sub("6g. Sling degradation")
sling = Sling(material=SlingMaterial.DYNEEMA, width_mm=6.0,
              rated_mbs_kn=22.0, length_m=0.6, uv_degradation=0.15)
print(f"  Sling rated MBS:    {sling.rated_mbs_kn} kN")
print(f"  Sling effective:    {sling.effective_mbs():.2f} kN  (after UV)")
print(f"  Sling elongation:   {sling.elongation_factor():.3f}")

sub("6h. Load sweep (angle range)")
sweep_arr = anchor.load_sweep(load_kn=9.0, angle_range=(-60, 60), steps=7)
print(f"  Sweep array shape: {sweep_arr.shape}  (angles × components)")
print(f"  Max load on any component: {sweep_arr.max():.2f} kN")

sub("6i. Progressive failure simulation")
failure = anchor.simulate_failure(load_kn=30.0)  # extreme load
print(f"  Failed components: {failure.failed_indices}")
print(f"  Cascade occurred:  {failure.cascade_occurred}")
print(f"  Redistributed forces: {[round(f, 2) for f in failure.redistributed_forces]}")


# ═════════════════════════════════════════════════════════════════════════════
# 7.  SCENARIO — multi-protection routes
# ═════════════════════════════════════════════════════════════════════════════
section("7. Scenario — full route simulation")

from ropesim.simulate import Scenario

sub("7a. Build a trad route: 4 pieces of gear")
rope_obj = Rope(db.get("Mammut Crag Classic 10.2"))
scenario = Scenario(
    rope=rope_obj,
    climber_mass_kg=75.0,
    belay_device=BelayDevice.ATC_GUIDE,
    temperature_c=15.0,
)

gear_heights = [3.0, 7.0, 12.0, 17.0]
for i, h in enumerate(gear_heights):
    if i < 2:
        piece = Cam(brand="Wild Country", size="2", rated_mbs_kn=12.0,
                    placement=CamPlacement.GOOD, rock_type=RockType.GRANITE, walking_risk=False)
        sys = AnchorSystem(AnchorType.SINGLE_POINT, [piece])
    else:
        piece = Bolt(bolt_type=BoltType.EXPANSION_WEDGE, rated_mbs_kn=20.0,
                     age_years=5, rock_type=RockType.LIMESTONE)
        sys = AnchorSystem(AnchorType.SLIDING_X, [piece, piece])
    scenario.add_protection(h, sys, label=f"P{i+1}")

print(f"  Protection points: {len(scenario.protection)}")
summary = scenario.summary()
print(f"  Scenario summary:  {summary}")

sub("7b. Simulate fall from 20 m")
fall_result = scenario.simulate_fall(climber_height_m=20.0)
print(f"  Peak force:   {fall_result.peak_force_kn:.2f} kN")
print(f"  Fall factor:  {fall_result.fall_factor:.3f}")
print(f"  Fall dist:    {fall_result.fall_distance_m:.1f} m")
print(f"  Rope out:     {fall_result.rope_out_m:.1f} m")

sub("7c. Sweep all positions (40 steps)")
sweep = scenario.sweep_fall_positions(height_range=(4.0, 22.0), steps=40)
arr = sweep.as_numpy()   # shape (N, 4): height, fall_dist, fall_factor, peak_kn
print(f"  Sweep shape:      {arr.shape}")
print(f"  Worst height:     {sweep.worst_height_m:.1f} m")
print(f"  Worst peak force: {sweep.worst_peak_kn:.2f} kN")
print(f"  Mean peak force:  {arr[:, 3].mean():.2f} kN")
print(f"  Min  peak force:  {arr[:, 3].min():.2f} kN")

sub("7d. Zipper analysis")
zipper = scenario.simulate_zipper(climber_height_m=20.0)
print(f"  Initial peak force:    {zipper.initial_fall_result.peak_force_kn:.2f} kN")
print(f"  Pieces failed:         {zipper.total_pieces_failed}")
print(f"  Failure sequence:      {zipper.failure_sequence}")
print(f"  Ground fall reached:   {zipper.ground_fall_reached}")


# ═════════════════════════════════════════════════════════════════════════════
# 8.  RUST CORE (direct, low-level)
# ═════════════════════════════════════════════════════════════════════════════
section("8. Rust core — direct low-level API")

try:
    from ropesim._rustcore import (
        compute_fall_factor,
        compute_impact_force_uiaa,
        compute_force_curve,
        compute_elongation,
        compute_energy_budget,
        compute_stiffness_from_spec,
        apply_wet_modifier,
        apply_temperature_modifier,
        batch_sweep_fall_factors,
    )

    ff = compute_fall_factor(8.0, 10.0)
    print(f"  Fall factor (8 m fall, 10 m out): {ff:.4f}")

    stiffness = compute_stiffness_from_spec(9.2, 32.0, 80.0)
    print(f"  Stiffness from spec (9.2 kN, 32%): {stiffness:.2f} kN")

    adj = apply_temperature_modifier(stiffness, -10.0)
    print(f"  Temperature-adjusted (-10 °C):      {adj:.2f} kN")

    peak = compute_impact_force_uiaa(80.0, ff, adj, 0.35)
    print(f"  Peak force (UIAA formula):          {peak:.3f} kN")

    wet_peak = apply_wet_modifier(peak, True)
    print(f"  Wet modifier applied:               {wet_peak:.3f} kN")

    curve = compute_force_curve(80.0, 8.0, 10.0, stiffness, 0.12, 1.0)
    print(f"  Force curve length:                 {len(curve)} timesteps")

    budget = compute_energy_budget(80.0, 8.0, peak, 0.3, 0.35)
    print(f"  Energy budget — potential: {budget.potential_energy_j:.0f} J  "
          f"rope: {budget.rope_absorption_j:.0f} J")

    sub("8a. Batch parallel sweep (Rayon)")
    ff_vals = list(np.linspace(0.1, 2.0, 200))
    peaks = batch_sweep_fall_factors(
        mass_kg=80.0,
        ff_values=ff_vals,
        stiffness_kn=stiffness,
        belay_friction=0.35,
    )
    max_kn = max(peaks)
    max_ff = ff_vals[peaks.index(max_kn)]
    print(f"  200-point sweep — max peak: {max_kn:.2f} kN at FF {max_ff:.2f}")

except ImportError:
    print("  (Rust extension not compiled — skipping low-level API demo)")


# ═════════════════════════════════════════════════════════════════════════════
# 9.  VISUALISATIONS  (saved to PNG, not shown interactively)
# ═════════════════════════════════════════════════════════════════════════════
section("9. Visualisations — matplotlib plots saved to disk")

import matplotlib
matplotlib.use("Agg")    # headless — remove this line if you want interactive windows
import matplotlib.pyplot as plt
from ropesim import viz

plots: list[tuple[str, object]] = []

sub("9a. Force-time curve")
fig, _ = viz.plot_force_curve(fall_result, dark=True)
plots.append(("demo_force_curve.png", fig))

sub("9b. Energy budget")
fig, _ = viz.plot_energy_budget(fall_result, dark=True)
plots.append(("demo_energy_budget.png", fig))

sub("9c. Rope elongation vs force")
fig, _ = viz.plot_rope_elongation(rope_obj, force_range=(0, 15), steps=200, dark=True)
plots.append(("demo_rope_elongation.png", fig))

sub("9d. Rope diameter under load")
fig, _ = viz.plot_diameter_under_load(rope_obj, force_range=(0, 12), steps=200, dark=True)
plots.append(("demo_diameter_under_load.png", fig))

sub("9e. Anchor load distribution")
fig, _ = viz.plot_anchor_distribution(anchor, load_kn=9.0, dark=True)
plots.append(("demo_anchor_distribution.png", fig))

sub("9f. Sweep — peak force vs climber height")
fig, _ = viz.plot_fall_scenario(
    protection_heights=gear_heights,
    climber_height_m=20.0,
    peak_forces=[
        scenario.simulate_fall(h).peak_force_kn
        for h in gear_heights
    ],
    dark=True,
)
plots.append(("demo_fall_scenario.png", fig))

sub("9g. Fall comparison (three ropes)")
rope_names = ["Beal Opera 8.5 Dry", "Mammut Crag Classic 10.2", "Sterling Evolution Velocity 9.8 Dry"]
compare_results = []
compare_labels = []
for name in rope_names:
    s = db.get(name)
    if s:
        c = FallConditions(climber_mass_kg=80.0, fall_distance_m=8.0,
                           rope_out_m=10.0, belay_device=BelayDevice.ATC, rope=s)
        compare_results.append(Fall(c).simulate())
        compare_labels.append(s.name.split()[1])  # short label

if len(compare_results) >= 2:
    fig, _ = viz.plot_comparison(compare_results, compare_labels, dark=True)
    plots.append(("demo_comparison.png", fig))

sub("9h. Fall history / rope aging")
falls_log = [
    {"falls": 0,  "impact_force_kn": spec.impact_force_kn},
    {"falls": 5,  "impact_force_kn": rope.degrade(5).spec.impact_force_kn},
    {"falls": 10, "impact_force_kn": rope.degrade(10).spec.impact_force_kn},
    {"falls": 15, "impact_force_kn": rope.degrade(15).spec.impact_force_kn},
]
fig, _ = viz.plot_fall_history(rope, falls_log, dark=True)
plots.append(("demo_fall_history.png", fig))

for fname, fig in plots:
    fig.savefig(fname, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {fname}")


# ═════════════════════════════════════════════════════════════════════════════
# 10. STANDARDS — validate a custom rope spec
# ═════════════════════════════════════════════════════════════════════════════
section("10. Standards — validate_rope()")

from ropesim.rope import RopeSpec
from ropesim import standards

# A deliberately bad spec
bad_spec = RopeSpec(
    name="BadRope Pro",
    manufacturer="Acme",
    rope_type=RopeType.SINGLE,
    diameter_mm=11.5,
    weight_gpm=78.0,
    impact_force_kn=14.0,    # ← too high (EN 892 max = 12 kN)
    number_of_falls=3,       # ← below minimum of 5
    static_elongation_pct=12.0,
    dynamic_elongation_pct=42.0,  # ← too high (max = 40%)
    sheath_percentage=35.0,
    dry_treated=False,
    length_m=60.0,
)
violations = standards.validate_rope(bad_spec)
print(f"  Violations found ({len(violations)}):")
for v in violations:
    print(f"    ⚠ {v}")

# A clean spec
good_spec = db.get("Mammut Crag Classic 10.2")
ok = standards.validate_rope(good_spec)
print(f"\n  Mammut Crag Classic 10.2 violations: {ok or ['none — compliant ✓']}")


# ═════════════════════════════════════════════════════════════════════════════
# 11. CLI USAGE EXAMPLES  (informational — prints the commands)
# ═════════════════════════════════════════════════════════════════════════════
section("11. CLI — example commands")

cli_examples = """
  # List all ropes in the database
  ropesim-cli list-ropes

  # Filter by type
  ropesim-cli list-ropes --type dry_single

  # Simulate a single fall (factor ~0.5)
  ropesim-cli simulate --mass 80 --fall-dist 8 --rope-out 20 --rope "Beal Opera 8.5 Dry" --device grigri

  # Simulate with a wet rope at -5 °C
  ropesim-cli simulate --mass 75 --fall-dist 6 --rope-out 15 --device atc --wet --temp -5

  # Machine-readable JSON output
  ropesim-cli simulate --mass 80 --fall-dist 8 --rope-out 20 --json

  # Anchor force distribution
  ropesim-cli anchor --type sliding_x --load 9.5 --angle 60

  # Sweep fall factors (0.1 → 1.8, 20 steps)
  ropesim-cli sweep --rope "Mammut Crag Classic 10.2" --mass 80 --steps 20

  # Validate a rope against EN 892
  ropesim-cli validate-rope --name "Mammut Crag Classic 10.2"
"""
print(textwrap.dedent(cli_examples))

# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 70)
print("  Demo complete. Check the demo_*.png files for the plots.")
print("═" * 70 + "\n")
