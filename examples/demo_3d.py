#!/usr/bin/env python3
"""
ropesim 3-D demo — a complete Rapier rigid-body fall, plotted in 3-D.

Run it and it does *everything* for you:

  * loads a rope from the built-in database,
  * builds a full climbing scenario (vertical rock face + bolt protection),
  * spins up the Rapier 3-D world and steps the physics,
  * finds the peak-force frame,
  * and plots the lot: the rope in 3-D at the moment of peak load, the
    climber's fall trajectory through space, and the anchor force-time curve.

Usage
-----
    python examples/demo_3d.py                 # save PNG to examples/output/
    python examples/demo_3d.py --show          # also pop up the figure
    python examples/demo_3d.py --rope "Mammut Infinity 9.5 Dry"

Needs the compiled Rust core with the Rapier world (built into the released
wheels; ``maturin develop`` locally). If it isn't present the script explains
what to do instead of crashing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np

from ropesim import (
    AnchorSystem,
    AnchorType,
    BelayDevice,
    Bolt,
    RockFaceGeometry,
    Rope,
    Scenario,
    SimulationReplay,
)

# ── Settings for the example scenario ────────────────────────────────────────
DEFAULT_ROPE = "Beal Opera 8.5 Dry"
CLIMBER_MASS_KG = 78.0
BELAY_DEVICE = BelayDevice.GRIGRI
WALL_WIDTH_M = 8.0
WALL_HEIGHT_M = 24.0
WALL_FRICTION = 0.5
PROTECTION_HEIGHTS_M = [4.0, 8.0, 12.0, 16.0]
SIM_SECONDS = 3.0
DT_SECONDS = 1.0 / 240.0


def build_scenario(rope: Rope) -> Scenario:
    """Assemble a fully-specified Rapier-ready scenario."""
    face = RockFaceGeometry.vertical_slab(
        width_m=WALL_WIDTH_M, height_m=WALL_HEIGHT_M, friction=WALL_FRICTION
    )
    scenario = Scenario(
        rope,
        climber_mass_kg=CLIMBER_MASS_KG,
        belay_device=BELAY_DEVICE,
        rock_face=face,
    )
    for i, h in enumerate(PROTECTION_HEIGHTS_M):
        anchor = AnchorSystem(
            anchor_type=AnchorType.SINGLE_POINT,
            components=[Bolt(rated_mbs_kn=25.0, position=(0.0, h))],
        )
        scenario.add_protection(h, anchor, label=f"bolt {i + 1}")
    return scenario


def run_rapier(scenario: Scenario) -> SimulationReplay:
    """Build the Rapier world, step it, and wrap the frames in a replay."""
    world = scenario.build_rapier_world()
    n_steps = int(SIM_SECONDS / DT_SECONDS)
    frame_data = world.step_n(n_steps, DT_SECONDS)
    return SimulationReplay(frame_data)


def print_summary(rope: Rope, replay: SimulationReplay) -> int:
    print("═" * 60)
    print(f"  ropesim 3-D demo (Rapier) — {rope.spec.name}")
    print("═" * 60)
    print(f"  climber mass      {CLIMBER_MASS_KG:.0f} kg")
    print(f"  belay device      {BELAY_DEVICE.value}")
    print(f"  wall              {WALL_WIDTH_M:.0f} × {WALL_HEIGHT_M:.0f} m "
          f"(friction {WALL_FRICTION})")
    print(f"  protection        {PROTECTION_HEIGHTS_M} m")
    print("─" * 60)
    print(f"  frames simulated  {replay.total_frames()}")
    print(f"  timestep          {DT_SECONDS * 1000:.2f} ms")
    print(f"  peak anchor force {replay.peak_anchor_force_kn():.2f} kN")
    peak_idx = replay.peak_force_frame()
    print(f"  peak at frame     {peak_idx} "
          f"(t = {replay.frame(peak_idx).timestamp_ms:.0f} ms)")
    print("═" * 60)
    return peak_idx


def save(fig, out_dir: Path, name: str) -> Path:
    path = out_dir / name
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"  wrote {path}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rope", default=DEFAULT_ROPE, help="rope name from the database")
    ap.add_argument("--show", action="store_true", help="display the figure interactively")
    ap.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "output",
        help="directory to write the PNG into",
    )
    args = ap.parse_args()

    if not args.show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers 3d projection)

    rope = Rope.from_db(args.rope)
    scenario = build_scenario(rope)

    try:
        replay = run_rapier(scenario)
    except ImportError:
        print(
            "The Rapier 3-D world isn't available in this build of the Rust "
            "core.\n"
            "Install the released wheel (`pip install ropesim`) or rebuild "
            "locally with `maturin develop --release`, then re-run."
        )
        return 1

    peak_idx = print_summary(rope, replay)

    # ── Gather geometry ─────────────────────────────────────────────────────
    frames = replay._frames
    peak_frame = replay.frame(peak_idx)

    # Rope shape at peak load (list of [x, y, z]); y is the vertical axis.
    rope_xyz = np.array(peak_frame.rope_positions, dtype=float)
    # Climber trajectory across the whole fall.
    climber_xyz = np.array([f.climber_position for f in frames], dtype=float)

    # matplotlib's z-axis is "up", so map physics-y (height) -> plot-z.
    def to_plot(a: np.ndarray) -> tuple:
        a = np.atleast_2d(a)
        return a[:, 0], a[:, 2], a[:, 1]  # x, depth, height

    out_dir = args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(13, 6), facecolor="#1a1a2e")

    # ── Left: 3-D scene ─────────────────────────────────────────────────────
    ax = fig.add_subplot(1, 2, 1, projection="3d")
    ax.set_facecolor("#16213e")

    rx, rd, rh = to_plot(rope_xyz)
    ax.plot(rx, rd, rh, color="#4fc3f7", lw=2.5, label="rope @ peak load")

    cx, cd, ch = to_plot(climber_xyz)
    ax.plot(cx, cd, ch, color="#e94560", lw=1.6, alpha=0.9, label="climber fall path")
    ax.scatter(cx[0], cd[0], ch[0], color="#ffb300", s=40, label="start")
    ax.scatter(cx[-1], cd[-1], ch[-1], color="#e94560", s=50, label="caught")

    # Anchor (top of the rope) + protection markers on the wall (x=0).
    ax.scatter(rx[0], rd[0], rh[0], color="#4caf50", s=80, marker="s", label="anchor")
    for h in PROTECTION_HEIGHTS_M:
        ax.scatter(0, 0, h, color="#aed581", s=45, marker="^")

    # Draw the rock face as a translucent plane.
    xx, zz = np.meshgrid(
        np.linspace(-WALL_WIDTH_M / 2, WALL_WIDTH_M / 2, 2),
        np.linspace(0, WALL_HEIGHT_M, 2),
    )
    yy = np.zeros_like(xx)
    ax.plot_surface(xx, yy, zz, color="#2a2a4a", alpha=0.25, shade=False)

    ax.set_xlabel("x (m)", color="#e0e0e0")
    ax.set_ylabel("depth (m)", color="#e0e0e0")
    ax.set_zlabel("height (m)", color="#e0e0e0")
    ax.set_title("3-D fall — Rapier rigid-body world",
                 color="#e0e0e0", fontsize=11)
    ax.tick_params(colors="#e0e0e0", labelsize=8)
    ax.legend(fontsize=8, facecolor="#0f3460", labelcolor="#e0e0e0", loc="upper left")

    # ── Right: anchor force-time curve ──────────────────────────────────────
    ax2 = fig.add_subplot(1, 2, 2)
    ax2.set_facecolor("#16213e")
    t_ms = np.array([f.timestamp_ms for f in frames])
    force = np.array(replay.force_curve())
    ax2.plot(t_ms, force, color="#e94560", lw=1.8)
    ax2.axvline(peak_frame.timestamp_ms, color="#ffb300", ls="--", lw=1,
                label=f"peak {replay.peak_anchor_force_kn():.1f} kN")
    ax2.set_xlabel("time (ms)", color="#e0e0e0")
    ax2.set_ylabel("anchor force (kN)", color="#e0e0e0")
    ax2.set_title("Anchor force over time", color="#e0e0e0", fontsize=11)
    ax2.grid(True, color="#2a2a4a", ls="--", alpha=0.6)
    ax2.tick_params(colors="#e0e0e0", labelsize=8)
    for spine in ax2.spines.values():
        spine.set_color("#2a2a4a")
    ax2.legend(fontsize=8, facecolor="#0f3460", labelcolor="#e0e0e0")

    fig.tight_layout()
    save(fig, out_dir, "3d_rapier_fall.png")

    print(f"\n  done — figure in {out_dir}")
    if args.show:
        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
