#!/usr/bin/env python3
"""
ropesim 2-D demo — a complete, self-contained fall analysis.

Run it and it does *everything* for you:

  * loads a rope from the built-in database,
  * spells out every fall setting (mass, fall/rope-out, belay device, wetness,
    temperature, edge, timestep, damping),
  * runs the analytical UIAA / RK4 simulation,
  * compares three belay devices on the same fall,
  * sweeps a whole route to find the worst climber position,
  * and plots the lot with ``ropesim.viz`` — force curve, energy budget,
    rope elongation, and a route schematic.

Usage
-----
    python examples/demo_2d.py                 # save PNGs to examples/output/
    python examples/demo_2d.py --show          # also pop up the figures
    python examples/demo_2d.py --rope "Mammut Infinity 9.5 Dry"

Nothing here needs the C++ GUI — just the pip-installed library
(``pip install ropesim``) with matplotlib.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

from ropesim import (
    AnchorSystem,
    AnchorType,
    BelayDevice,
    Bolt,
    Fall,
    FallConditions,
    Rope,
    Scenario,
    viz,
)

# ── Settings for the example fall ────────────────────────────────────────────
DEFAULT_ROPE = "Beal Opera 8.5 Dry"
CLIMBER_MASS_KG = 80.0
FALL_DISTANCE_M = 6.0
ROPE_OUT_M = 12.0
BELAY_DEVICE = BelayDevice.ATC
IS_WET = False
TEMPERATURE_C = 15.0
ROPE_OVER_EDGE = False
TIMESTEP_MS = 1.0
DAMPING_RATIO = 0.12

# Route used for the position sweep (protection heights above the belay).
ROUTE_PROTECTION_HEIGHTS_M = [3.0, 6.0, 9.0, 12.0, 15.0]
CLIMBER_HEIGHT_M = 17.0


def build_conditions(rope: Rope, device: BelayDevice) -> FallConditions:
    """Assemble a fully-specified FallConditions from the module settings."""
    return FallConditions(
        climber_mass_kg=CLIMBER_MASS_KG,
        fall_distance_m=FALL_DISTANCE_M,
        rope_out_m=ROPE_OUT_M,
        belay_device=device,
        rope=rope.spec,
        is_wet=IS_WET,
        temperature_celsius=TEMPERATURE_C,
        rope_over_edge=ROPE_OVER_EDGE,
        timestep_ms=TIMESTEP_MS,
        damping_ratio=DAMPING_RATIO,
    )


def print_summary(rope: Rope, result) -> None:
    """Human-readable rundown of the primary fall."""
    eb = result.energy_budget
    print("═" * 60)
    print(f"  ropesim 2-D demo — {rope.spec.name}")
    print("═" * 60)
    print(f"  climber mass      {CLIMBER_MASS_KG:.0f} kg")
    print(f"  fall / rope out   {FALL_DISTANCE_M:.1f} m / {ROPE_OUT_M:.1f} m")
    print(f"  belay device      {BELAY_DEVICE.value}")
    print(f"  temperature       {TEMPERATURE_C:.0f} °C   wet={IS_WET}")
    print("─" * 60)
    print(f"  fall factor       {result.fall_factor:.2f}")
    print(f"  peak force        {result.peak_force_kn:.2f} kN "
          f"({result.peak_force_lbf:.0f} lbf)")
    print(f"  peak deceleration {result.peak_deceleration_g:.1f} g")
    print(f"  rope elongation   {result.elongation_m:.2f} m")
    print(f"  rope survived     {result.rope_survived}")
    print(f"  energy: PE={eb.potential_energy_j:.0f} J  "
          f"rope={eb.rope_absorption_j:.0f} J  "
          f"belay={eb.belay_device_j:.0f} J  "
          f"residual={eb.residual_j:.0f} J")
    if result.warnings:
        print("  warnings:")
        for w in result.warnings:
            print(f"    • {w}")
    print("═" * 60)


def save(fig, out_dir: Path, name: str) -> Path:
    """Save a figure preserving its (dark) background."""
    path = out_dir / name
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"  wrote {path}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rope", default=DEFAULT_ROPE, help="rope name from the database")
    ap.add_argument("--show", action="store_true", help="display figures interactively")
    ap.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "output",
        help="directory to write PNGs into",
    )
    args = ap.parse_args()

    if not args.show:
        matplotlib.use("Agg")  # headless: only save files
    import matplotlib.pyplot as plt

    out_dir = args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load the rope and run the primary fall ------------------------------
    rope = Rope.from_db(args.rope)
    primary = Fall(build_conditions(rope, BELAY_DEVICE)).simulate()
    print_summary(rope, primary)

    # 2. Compare three belay devices on the identical fall -------------------
    compare_devices = [BelayDevice.ATC, BelayDevice.GRIGRI, BelayDevice.MUNTER]
    device_results = [
        Fall(build_conditions(rope, d)).simulate() for d in compare_devices
    ]
    print("\n  belay-device comparison (same fall):")
    for d, r in zip(compare_devices, device_results):
        print(f"    {d.value:<8} peak {r.peak_force_kn:5.2f} kN")

    # 3. Sweep the whole route for the worst climber position ----------------
    scenario = Scenario(
        rope,
        climber_mass_kg=CLIMBER_MASS_KG,
        belay_device=BELAY_DEVICE,
        temperature_c=TEMPERATURE_C,
    )
    for i, h in enumerate(ROUTE_PROTECTION_HEIGHTS_M):
        anchor = AnchorSystem(
            anchor_type=AnchorType.SINGLE_POINT,
            components=[Bolt(rated_mbs_kn=25.0, position=(0.0, h))],
        )
        scenario.add_protection(h, anchor, label=f"bolt {i + 1}")
    sweep = scenario.sweep_fall_positions(
        height_range=(ROUTE_PROTECTION_HEIGHTS_M[0], CLIMBER_HEIGHT_M),
        steps=40,
    )
    print(f"\n  worst position: {sweep.worst_height_m:.1f} m "
          f"→ {sweep.worst_peak_kn:.2f} kN\n")

    # 4. Plot everything -----------------------------------------------------
    print("  plots:")

    fig1, _ = viz.plot_force_curve(primary, label=f"{BELAY_DEVICE.value} (primary)")
    save(fig1, out_dir, "2d_force_curve.png")

    # Belay devices differ in *peak* force, not curve shape — show a bar chart.
    fig_dev, axd = plt.subplots(figsize=(7, 4))
    peaks = [r.peak_force_kn for r in device_results]
    bars = axd.bar([d.value for d in compare_devices], peaks,
                   color=["#e94560", "#4caf50", "#ffb300"])
    for rect, p in zip(bars, peaks):
        axd.text(rect.get_x() + rect.get_width() / 2, p, f"{p:.2f} kN",
                 ha="center", va="bottom", fontsize=9)
    axd.set_ylabel("Peak impact force (kN)")
    axd.set_title("Belay-device comparison (same fall)")
    axd.grid(True, axis="y", ls="--", alpha=0.4)
    fig_dev.tight_layout()
    save(fig_dev, out_dir, "2d_device_comparison.png")

    fig2, _ = viz.plot_energy_budget(primary)
    save(fig2, out_dir, "2d_energy_budget.png")

    fig3, _ = viz.plot_rope_elongation(rope)
    save(fig3, out_dir, "2d_rope_elongation.png")

    fig4, ax4 = plt.subplots(figsize=(9, 4))
    ax4.plot(sweep.climber_heights_m, sweep.peak_forces_kn, color="#e94560", lw=2)
    ax4.scatter([sweep.worst_height_m], [sweep.worst_peak_kn],
                color="#ffb300", zorder=5, s=60,
                label=f"worst {sweep.worst_peak_kn:.1f} kN @ {sweep.worst_height_m:.1f} m")
    ax4.set_xlabel("Climber height above belay (m)")
    ax4.set_ylabel("Peak impact force (kN)")
    ax4.set_title("Peak force vs. climber position (route sweep)")
    ax4.grid(True, ls="--", alpha=0.4)
    ax4.legend()
    fig4.tight_layout()
    save(fig4, out_dir, "2d_position_sweep.png")

    fig5, _ = viz.plot_fall_scenario(
        ROUTE_PROTECTION_HEIGHTS_M,
        CLIMBER_HEIGHT_M,
        peak_forces=[sweep.worst_peak_kn] * len(ROUTE_PROTECTION_HEIGHTS_M),
    )
    save(fig5, out_dir, "2d_route_schematic.png")

    print(f"\n  done — {6} figures in {out_dir}")
    if args.show:
        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
