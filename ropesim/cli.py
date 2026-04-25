"""
ropesim.cli
===========
Command-line interface for ropesim.

Commands
--------
  simulate      Simulate a single fall (mass, fall-dist, rope-out, rope name)
  anchor        Compute anchor load distribution
  list-ropes    List all ropes in the database
  validate-rope Check a rope against EN 892 / UIAA 101
  sweep         Sweep fall factors and print peak forces

Entry point: ``ropesim-cli``  (defined in pyproject.toml)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print_result_table(result) -> None:
    """Pretty-print a FallResult."""
    print(f"\n{'═'*54}")
    print(f"  FALL SIMULATION RESULT")
    print(f"{'─'*54}")
    print(f"  Fall factor          : {result.fall_factor:.3f}")
    print(f"  Peak force           : {result.peak_force_kn:.2f} kN  ({result.peak_force_lbf:.0f} lbf)")
    print(f"  Peak deceleration    : {result.peak_deceleration_g:.2f} g")
    print(f"  Rope elongation      : {result.elongation_m:.2f} m")
    print(f"  Rope survived        : {'Yes' if result.rope_survived else 'No'}")
    eb = result.energy_budget
    print(f"{'─'*54}")
    print(f"  Energy budget:")
    print(f"    Potential energy   : {eb.potential_energy_j:.0f} J")
    print(f"    Rope absorption    : {eb.rope_absorption_j:.0f} J")
    print(f"    Belay device       : {eb.belay_device_j:.0f} J")
    print(f"    Residual           : {eb.residual_j:.0f} J")
    if result.warnings:
        print(f"{'─'*54}")
        print(f"  Warnings:")
        for w in result.warnings:
            print(f"    ! {w}")
    print(f"{'═'*54}\n")


# ── Command: simulate ─────────────────────────────────────────────────────────

def cmd_simulate(args: argparse.Namespace) -> int:
    from ropesim.rope import Rope, RopeSpec, RopeType
    from ropesim.fall import Fall, FallConditions, BelayDevice

    # Load rope
    if args.rope:
        try:
            rope = Rope.from_db(args.rope)
        except KeyError as e:
            print(f"Error: {e}", file=sys.stderr)
            print("Use 'ropesim-cli list-ropes' to see available ropes.", file=sys.stderr)
            return 1
        spec = rope.spec
    else:
        # Build a generic single rope from CLI params
        spec = RopeSpec(
            name                  = "CLI rope",
            rope_type             = RopeType.SINGLE,
            diameter_mm           = float(args.diameter or 9.5),
            weight_gpm            = 60.0,
            sheath_percentage     = 40.0,
            impact_force_kn       = float(args.impact_force or 9.2),
            number_of_falls       = 7,
            static_elongation_pct = 8.0,
            dynamic_elongation_pct= 34.0,
        )

    device_map = {
        "atc": "atc", "grigri": "grigri", "grigri_plus": "grigri_plus",
        "tube": "tube", "reverso": "reverso", "munter": "munter",
        "atc_guide": "atc_guide",
    }
    device_str = device_map.get(args.device.lower(), "atc")
    device = BelayDevice(device_str)

    conditions = FallConditions(
        climber_mass_kg     = args.mass,
        fall_distance_m     = args.fall_dist,
        rope_out_m          = args.rope_out,
        belay_device        = device,
        rope                = spec,
        is_wet              = args.wet,
        temperature_celsius = args.temp,
        damping_ratio       = args.damping,
    )

    result = Fall(conditions).simulate()

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"\n  Rope   : {spec.name}")
        print(f"  Device : {device.value}")
        _print_result_table(result)

    return 0


# ── Command: anchor ───────────────────────────────────────────────────────────

def cmd_anchor(args: argparse.Namespace) -> int:
    from ropesim.anchor import AnchorSystem, AnchorType, Bolt

    anchor_type_map = {
        "sliding_x": AnchorType.SLIDING_X,
        "quad":       AnchorType.QUAD,
        "cordelette": AnchorType.CORDELETTE,
        "direct":     AnchorType.DIRECT_2BOLT,
    }
    atype = anchor_type_map.get(args.type.lower(), AnchorType.SLIDING_X)

    # Build N identical bolts
    n = args.bolts
    spacing = 0.3  # default bolt spacing in metres
    bolts = [
        Bolt(rated_mbs_kn=args.bolt_mbs, position=(i * spacing, 0.0))
        for i in range(n)
    ]

    system = AnchorSystem(atype, bolts)
    dist   = system.load_distribution(args.load, args.angle)
    margins = system.safety_margins(args.load)
    failure = system.simulate_failure(args.load, args.angle)

    print(f"\n{'═'*54}")
    print(f"  ANCHOR ANALYSIS — {atype.value.upper()}")
    print(f"{'─'*54}")
    print(f"  Applied load : {args.load:.1f} kN  @ {args.angle:.0f}°")
    print(f"  Bolt MBS     : {args.bolt_mbs:.1f} kN each")
    print(f"{'─'*54}")
    print(f"  Per-bolt forces:")
    for i, (key, force) in enumerate(dist.items()):
        margin = margins.get(key, 0.0)
        status = "OK" if margin > 0 else "OVERLOADED"
        print(f"    Bolt {i+1}: {force:.2f} kN  ({margin:.1f}% margin)  [{status}]")
    if failure.failed_indices:
        print(f"{'─'*54}")
        print(f"  ⚠  FAILURE: bolts {[i+1 for i in failure.failed_indices]} failed")
        if failure.cascade_occurred:
            print(f"  ⚠  CASCADE occurred!")
    else:
        print(f"{'─'*54}")
        print(f"  All components within rated MBS.")
    print(f"{'═'*54}\n")

    return 0


# ── Command: list-ropes ───────────────────────────────────────────────────────

def cmd_list_ropes(args: argparse.Namespace) -> int:
    from ropesim.rope import RopeDatabase, RopeType

    db = RopeDatabase()
    rope_type = None
    if args.type:
        try:
            rope_type = RopeType(args.type.lower())
        except ValueError:
            print(f"Unknown rope type '{args.type}'. Valid: single, half, twin, dry_single, dry_half, dry_twin", file=sys.stderr)
            return 1

    specs = db.search(rope_type=rope_type)

    if args.dry:
        specs = [s for s in specs if s.dry_treated]

    if not specs:
        print("No ropes found matching criteria.")
        return 0

    if args.json:
        print(json.dumps([s.model_dump() for s in specs], indent=2))
        return 0

    # Table header
    print(f"\n{'═'*80}")
    print(f"  {'Name':<35} {'Type':<12} {'Dia':>5} {'IF':>6} {'Falls':>6} {'Dry':>4}")
    print(f"{'─'*80}")
    for s in specs:
        dry = "Yes" if s.dry_treated else "No"
        print(
            f"  {s.name:<35} {s.rope_type.value:<12} "
            f"{s.diameter_mm:>4.1f}mm {s.impact_force_kn:>5.1f}kN "
            f"{s.number_of_falls:>5}  {dry:>4}"
        )
    print(f"{'─'*80}")
    print(f"  {len(specs)} rope(s) found.\n")
    return 0


# ── Command: validate-rope ────────────────────────────────────────────────────

def cmd_validate_rope(args: argparse.Namespace) -> int:
    from ropesim.rope import Rope

    try:
        rope = Rope.from_db(args.name)
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    violations = rope.validate_standard_compliance()

    if args.json:
        print(json.dumps({"rope": args.name, "violations": violations}))
        return 0 if not violations else 1

    print(f"\n  Rope: {rope.spec.name}")
    print(f"  Type: {rope.spec.rope_type.value}  |  "
          f"Diameter: {rope.spec.diameter_mm}mm  |  "
          f"Impact force: {rope.spec.impact_force_kn}kN  |  "
          f"Falls: {rope.spec.number_of_falls}")

    if not violations:
        print("  Result: COMPLIANT — no EN 892 / UIAA 101 violations.\n")
        return 0
    else:
        print(f"  Result: {len(violations)} VIOLATION(S):")
        for v in violations:
            print(f"    ! {v}")
        print()
        return 1


# ── Command: sweep ────────────────────────────────────────────────────────────

def cmd_sweep(args: argparse.Namespace) -> int:
    from ropesim.rope import Rope, RopeSpec, RopeType
    from ropesim._rustcore import (
        batch_sweep_fall_factors,
        compute_stiffness_from_spec,
        apply_temperature_modifier,
    )
    from ropesim.fall import BELAY_FRICTION_COEFFICIENTS, BelayDevice

    if args.rope:
        try:
            rope = Rope.from_db(args.rope)
        except KeyError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        spec = rope.spec
    else:
        spec = RopeSpec(
            name                  = "CLI rope",
            rope_type             = RopeType.SINGLE,
            diameter_mm           = 9.5,
            weight_gpm            = 60.0,
            sheath_percentage     = 40.0,
            impact_force_kn       = float(args.impact_force or 9.2),
            number_of_falls       = 7,
            static_elongation_pct = 8.0,
            dynamic_elongation_pct= 34.0,
        )

    device = BelayDevice(args.device.lower() if args.device else "atc")
    base_k = compute_stiffness_from_spec(spec.impact_force_kn, spec.dynamic_elongation_pct, 80.0)
    adj_k  = apply_temperature_modifier(base_k, args.temp)
    friction = BELAY_FRICTION_COEFFICIENTS.get(device, 0.35)

    import numpy as np
    ff_values = np.linspace(args.ff_start, args.ff_end, args.steps).tolist()
    peak_forces = batch_sweep_fall_factors(args.mass, ff_values, adj_k, friction)

    if args.json:
        out = [{"fall_factor": ff, "peak_force_kn": pf}
               for ff, pf in zip(ff_values, peak_forces)]
        print(json.dumps(out, indent=2))
        return 0

    print(f"\n  SWEEP — {spec.name}  |  mass={args.mass}kg  |  device={device.value}")
    print(f"  {'Fall factor':>12}  {'Peak force':>12}")
    print(f"  {'─'*12}  {'─'*12}")
    for ff, pf in zip(ff_values, peak_forces):
        flag = "  ←  MAX" if pf == max(peak_forces) else ""
        print(f"  {ff:>12.3f}  {pf:>10.2f} kN{flag}")
    print()
    return 0


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ropesim-cli",
        description="ropesim — Climbing rope physics CLI",
    )
    parser.add_argument("--version", action="version", version="ropesim 0.1.0")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # ── simulate ──
    p_sim = sub.add_parser("simulate", help="Simulate a single fall")
    p_sim.add_argument("--mass",         type=float, default=80.0,  metavar="KG",   help="Climber mass in kg (default: 80)")
    p_sim.add_argument("--fall-dist",    type=float, required=True, metavar="M",    help="Fall distance in metres")
    p_sim.add_argument("--rope-out",     type=float, required=True, metavar="M",    help="Rope paid out in metres")
    p_sim.add_argument("--rope",         type=str,   default=None,  metavar="NAME", help="Rope name from database")
    p_sim.add_argument("--device",       type=str,   default="atc", metavar="DEV",  help="Belay device [atc|grigri|grigri_plus|tube|reverso|munter] (default: atc)")
    p_sim.add_argument("--wet",          action="store_true",                       help="Wet rope condition")
    p_sim.add_argument("--temp",         type=float, default=20.0,  metavar="C",    help="Temperature in °C (default: 20)")
    p_sim.add_argument("--damping",      type=float, default=0.12,  metavar="Z",    help="Damping ratio 0–1 (default: 0.12)")
    p_sim.add_argument("--diameter",     type=float, default=None,  metavar="MM",   help="Rope diameter mm (if not using --rope)")
    p_sim.add_argument("--impact-force", type=float, default=None,  metavar="KN",   help="Rope impact force kN (if not using --rope)")
    p_sim.add_argument("--json",         action="store_true",                       help="Output JSON")

    # ── anchor ──
    p_anc = sub.add_parser("anchor", help="Analyse anchor load distribution")
    p_anc.add_argument("--type",     type=str,   default="sliding_x", metavar="TYPE", help="Anchor type [sliding_x|quad|cordelette|direct] (default: sliding_x)")
    p_anc.add_argument("--bolts",    type=int,   default=2,            metavar="N",    help="Number of bolts (default: 2)")
    p_anc.add_argument("--bolt-mbs", type=float, default=25.0,         metavar="KN",   help="Bolt MBS in kN (default: 25.0)")
    p_anc.add_argument("--load",     type=float, required=True,        metavar="KN",   help="Applied load in kN")
    p_anc.add_argument("--angle",    type=float, default=0.0,          metavar="DEG",  help="Load angle in degrees (default: 0)")

    # ── list-ropes ──
    p_lr = sub.add_parser("list-ropes", help="List ropes in the database")
    p_lr.add_argument("--type", type=str, default=None, metavar="TYPE", help="Filter by type [single|half|twin|dry_single|dry_half|dry_twin]")
    p_lr.add_argument("--dry",  action="store_true",                   help="Show only dry-treated ropes")
    p_lr.add_argument("--json", action="store_true",                   help="Output JSON")

    # ── validate-rope ──
    p_vr = sub.add_parser("validate-rope", help="Check rope against EN 892 / UIAA 101")
    p_vr.add_argument("--name", type=str, required=True, metavar="NAME", help="Rope name from database")
    p_vr.add_argument("--json", action="store_true",                     help="Output JSON")

    # ── sweep ──
    p_sw = sub.add_parser("sweep", help="Sweep fall factors and print peak forces")
    p_sw.add_argument("--rope",         type=str,   default=None,  metavar="NAME", help="Rope name from database")
    p_sw.add_argument("--mass",         type=float, default=80.0,  metavar="KG",   help="Climber mass in kg (default: 80)")
    p_sw.add_argument("--device",       type=str,   default="atc", metavar="DEV",  help="Belay device (default: atc)")
    p_sw.add_argument("--ff-start",     type=float, default=0.1,   metavar="FF",   help="Start fall factor (default: 0.1)")
    p_sw.add_argument("--ff-end",       type=float, default=1.8,   metavar="FF",   help="End fall factor (default: 1.8)")
    p_sw.add_argument("--steps",        type=int,   default=10,    metavar="N",    help="Number of steps (default: 10)")
    p_sw.add_argument("--temp",         type=float, default=20.0,  metavar="C",    help="Temperature in °C (default: 20)")
    p_sw.add_argument("--impact-force", type=float, default=None,  metavar="KN",   help="Rope impact force kN (if not using --rope)")
    p_sw.add_argument("--json",         action="store_true",                       help="Output JSON")

    # ── v2 commands ──
    from ropesim.cli_v2 import register_v2_commands
    register_v2_commands(sub)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    from ropesim.cli_v2 import v2_dispatch
    dispatch = {
        "simulate":     cmd_simulate,
        "anchor":       cmd_anchor,
        "list-ropes":   cmd_list_ropes,
        "validate-rope": cmd_validate_rope,
        "sweep":        cmd_sweep,
        **v2_dispatch(),
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
