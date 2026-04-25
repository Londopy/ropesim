"""
ropesim.cli_v2
==============
v2 CLI subcommands added to the ropesim CLI without touching existing commands.

New commands:
  rope        -- list / show / compare / add / import / retire ropes
  scenario    -- build / run / zipper / sweep scenario files
  validate    -- rope / scenario / system compliance checks
  report      -- generate PDF technical report
  toprope     -- top-rope catch simulation
  rappel      -- rappel anchor load calculation
  haul        -- mechanical advantage haul system
  interactive -- Python REPL with ropesim pre-loaded

All commands support --format text (default) | json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional


W = 58  # table width

def _hr(ch='='):   return ch * W
def _row(k, v):    return f"  {k:<26}: {v}"
def _hdr(title):   return f"\n{_hr()}\n  {title}\n{_hr('-')}"


# ── rope subcommand group ─────────────────────────────────────────────────────

def cmd_rope(args: argparse.Namespace) -> int:
    sub = getattr(args, 'rope_sub', None)
    dispatch = {
        'list':   _rope_list,
        'show':   _rope_show,
        'compare': _rope_compare,
        'add':    _rope_add,
        'import': _rope_import,
        'retire': _rope_retire,
    }
    handler = dispatch.get(sub)
    if handler is None:
        print("Usage: ropesim rope {list|show|compare|add|import|retire} ...")
        return 1
    return handler(args)


def _rope_list(args: argparse.Namespace) -> int:
    from ropesim.rope import RopeDatabase, RopeType

    db   = RopeDatabase()
    specs = db.search(rope_type=(RopeType(args.type.lower()) if args.type else None))

    if args.dry:
        specs = [s for s in specs if s.dry_treated]
    if args.manufacturer:
        specs = [s for s in specs
                 if args.manufacturer.lower() in getattr(s, 'manufacturer', '').lower()]
    if args.max_diameter:
        specs = [s for s in specs if s.diameter_mm <= args.max_diameter]
    if args.min_falls:
        specs = [s for s in specs if s.number_of_falls >= args.min_falls]

    sort_key = {
        'diameter':     lambda s: s.diameter_mm,
        'falls':        lambda s: -s.number_of_falls,
        'impact_force': lambda s: s.impact_force_kn,
        'weight':       lambda s: s.weight_gpm,
    }.get(args.sort, lambda s: s.name)
    specs.sort(key=sort_key)

    if args.format == 'json':
        print(json.dumps([s.model_dump() for s in specs], indent=2, default=str))
        return 0

    print(_hdr(f"ROPE DATABASE ({len(specs)} results)"))
    print(f"  {'Name':<35} {'Type':<8} {'Dia':>5} {'kN':>6} {'Elong':>6} {'Falls':>6} {'Dry':>4}")
    print(_hr('-'))
    for s in specs:
        dry = 'Y' if s.dry_treated else 'N'
        print(f"  {s.name:<35} {s.rope_type.value:<8} {s.diameter_mm:>4.1f}mm "
              f"{s.impact_force_kn:>5.1f}kN {s.dynamic_elongation_pct:>5.1f}% "
              f"{s.number_of_falls:>5}  {dry:>4}")
    print(_hr() + "\n")
    return 0


def _rope_show(args: argparse.Namespace) -> int:
    from ropesim import Rope, standards

    name = getattr(args, 'rope_name', None) or getattr(args, 'name', None)
    if not name:
        print("Error: rope name required", file=sys.stderr)
        return 1
    try:
        rope = Rope.from_db(name)
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    s = rope.spec
    violations = rope.validate_standard_compliance()
    status = 'COMPLIANT' if not violations else f'{len(violations)} VIOLATION(S)'

    if args.format == 'json':
        print(json.dumps({'spec': s.model_dump(), 'violations': violations},
                         indent=2, default=str))
        return 0

    print(_hdr(f"ROPE SPEC — {s.name}"))
    for k, v in [
        ('Type',               s.rope_type.value),
        ('Diameter',           f'{s.diameter_mm} mm'),
        ('Weight',             f'{s.weight_gpm:.0f} g/m'),
        ('Impact force',       f'{s.impact_force_kn:.2f} kN'),
        ('Static elongation',  f'{s.static_elongation_pct:.1f} %'),
        ('Dynamic elongation', f'{s.dynamic_elongation_pct:.1f} %'),
        ('UIAA falls',         str(s.number_of_falls)),
        ('Dry treated',        'Yes' if s.dry_treated else 'No'),
        ('EN 892 status',      status),
    ]:
        print(_row(k, v))

    if violations:
        print(_hr('-'))
        for v in violations:
            print(f"  ! {v}")
    print(_hr() + "\n")
    return 0 if not violations else 1


def _rope_compare(args: argparse.Namespace) -> int:
    from ropesim import Rope

    names = args.names
    if len(names) < 2:
        print("Error: provide at least two rope names to compare", file=sys.stderr)
        return 1

    ropes = []
    for n in names:
        try:
            ropes.append(Rope.from_db(n))
        except KeyError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    if args.format == 'json':
        print(json.dumps([r.spec.model_dump() for r in ropes], indent=2, default=str))
        return 0

    fields = [
        ('Type',          lambda s: s.rope_type.value),
        ('Diameter (mm)', lambda s: f'{s.diameter_mm:.1f}'),
        ('Weight (g/m)',  lambda s: f'{s.weight_gpm:.0f}'),
        ('Impact (kN)',   lambda s: f'{s.impact_force_kn:.2f}'),
        ('Static elong.', lambda s: f'{s.static_elongation_pct:.1f}%'),
        ('Dyn. elong.',   lambda s: f'{s.dynamic_elongation_pct:.1f}%'),
        ('UIAA falls',    lambda s: str(s.number_of_falls)),
        ('Dry',           lambda s: 'Yes' if s.dry_treated else 'No'),
    ]

    # Header row
    col_w = max(len(r.spec.name) for r in ropes) + 2
    print(f"\n  {'Field':<22}", end='')
    for r in ropes:
        print(f"  {r.spec.name[:col_w]:<{col_w}}", end='')
    print(f"\n  {_hr('-')}")

    for label, fn in fields:
        values = [fn(r.spec) for r in ropes]
        # Highlight best/worst for numeric fields
        print(f"  {label:<22}", end='')
        for v in values:
            print(f"  {v:<{col_w}}", end='')
        print()

    print()
    return 0


def _rope_add(args: argparse.Namespace) -> int:
    """Interactive: walk through RopeSpec fields and save to local ropes.json."""
    from ropesim.rope import RopeSpec, RopeType
    import pathlib

    print("\n  ADD ROPE — interactive mode")
    print("  Press Enter to accept default values.\n")

    def ask(prompt, default=None, cast=str):
        if default is not None:
            val = input(f"  {prompt} [{default}]: ").strip()
            return cast(val) if val else cast(default)
        else:
            while True:
                val = input(f"  {prompt}: ").strip()
                if val:
                    return cast(val)
                print("  (required)")

    name               = ask("Rope name")
    manufacturer       = ask("Manufacturer", "Unknown")
    rope_type_str      = ask("Type [single/half/twin]", "single")
    diameter_mm        = ask("Diameter (mm)", "9.5", float)
    weight_gpm         = ask("Weight (g/m)", "60", float)
    impact_force_kn    = ask("Impact force (kN)", "9.0", float)
    number_of_falls    = ask("UIAA falls", "7", int)
    static_elong       = ask("Static elongation %", "8.0", float)
    dynamic_elong      = ask("Dynamic elongation %", "34.0", float)
    dry_treated        = ask("Dry treated? [y/n]", "n").lower().startswith('y')

    try:
        rt = RopeType(rope_type_str.lower())
    except ValueError:
        rt = RopeType.SINGLE

    spec = RopeSpec(
        name=name, manufacturer=manufacturer,
        rope_type=rt, diameter_mm=diameter_mm,
        weight_gpm=weight_gpm,
        impact_force_kn=impact_force_kn,
        number_of_falls=number_of_falls,
        static_elongation_pct=static_elong,
        dynamic_elongation_pct=dynamic_elong,
        dry_treated=dry_treated,
        sheath_percentage=38.0,
    )

    # Validate
    from ropesim.rope import Rope
    rope = Rope(spec)
    violations = rope.validate_standard_compliance()
    if violations:
        print("\n  Violations found:")
        for v in violations:
            print(f"    ! {v}")
        if input("\n  Save anyway? [y/N]: ").strip().lower() != 'y':
            print("  Aborted.")
            return 1

    # Save to local ropes.json
    local_path = pathlib.Path.home() / '.ropesim' / 'ropes.json'
    local_path.parent.mkdir(exist_ok=True)
    data = {}
    if local_path.exists():
        with open(local_path) as f:
            data = json.load(f)
    data[name] = spec.model_dump(mode='json')
    with open(local_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\n  Saved to {local_path}\n")
    return 0


def _rope_import(args: argparse.Namespace) -> int:
    """Import rope spec from a JSON file."""
    from ropesim.rope import RopeSpec
    import pathlib

    if not os.path.exists(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1

    with open(args.file) as f:
        data = json.load(f)

    if isinstance(data, list):
        specs_data = data
    else:
        specs_data = [data]

    local_path = pathlib.Path.home() / '.ropesim' / 'ropes.json'
    local_path.parent.mkdir(exist_ok=True)
    existing = {}
    if local_path.exists():
        with open(local_path) as f:
            existing = json.load(f)

    imported = 0
    for sd in specs_data:
        try:
            spec = RopeSpec(**sd)
            existing[spec.name] = spec.model_dump(mode='json')
            print(f"  Imported: {spec.name}")
            imported += 1
        except Exception as e:
            print(f"  Skip: {e}", file=sys.stderr)

    with open(local_path, 'w') as f:
        json.dump(existing, f, indent=2, default=str)
    print(f"\n  {imported} rope(s) imported to {local_path}\n")
    return 0


def _rope_retire(args: argparse.Namespace) -> int:
    from ropesim import Rope

    name = getattr(args, 'rope_name', None) or getattr(args, 'name', None)
    try:
        rope = Rope.from_db(name)
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    rating = rope.spec.number_of_falls
    falls  = args.falls_taken
    # Each hard lead fall ≈ 0.8–1.2 UIAA equiv
    consumed = falls * 0.9
    remaining = max(rating - consumed, 0)
    pct = 100 * remaining / rating

    if pct < 10:
        status, advice = 'RETIRE NOW', 'Retire this rope immediately.'
    elif pct < 25:
        status, advice = 'NEAR END',   'Inspect carefully; consider retiring.'
    elif pct < 50:
        status, advice = 'CHECK',      'Inspect for sheath damage and stiffness.'
    else:
        status, advice = 'OK',         'Rope in good standing.'

    print(_hdr(f"RETIREMENT STATUS — {rope.spec.name}"))
    print(_row('UIAA fall rating',    f'{rating} falls'))
    print(_row('Falls taken',         f'{falls}'))
    print(_row('Estimated remaining', f'{remaining:.1f} falls ({pct:.0f}%)'))
    print(_row('Status',              f'{status}'))
    print(_hr('-'))
    print(f"  {advice}")
    print(_hr() + "\n")
    return 0 if pct >= 25 else 1


# ── scenario subcommand group ─────────────────────────────────────────────────

_SCENARIO_SCHEMA = {
    'rope':            'Beal Opera 8.5 Dry',
    'climber_mass_kg': 80.0,
    'belay_device':    'atc',
    'belay_height_m':  0.0,
    'is_wet':          False,
    'temperature_c':   20.0,
    'protection':      [],
}


def _load_scenario_file(path: str):
    """Load a .ropesim scenario file and return a Scenario object."""
    from ropesim import Rope, Scenario, AnchorSystem, AnchorType, Bolt, BoltType, RockType
    from ropesim.fall import BelayDevice

    with open(path) as f:
        data = json.load(f)

    rope     = Rope.from_db(data['rope'])
    device   = BelayDevice(data.get('belay_device', 'atc'))
    scenario = Scenario(
        rope            = rope,
        climber_mass_kg = data.get('climber_mass_kg', 80.0),
        belay_device    = device,
        belay_height_m  = data.get('belay_height_m', 0.0),
        is_wet          = data.get('is_wet', False),
        temperature_c   = data.get('temperature_c', 20.0),
    )

    for pro in data.get('protection', []):
        bolt = Bolt(
            position  = [0.0, 0.0],
            mbs_kn    = pro.get('mbs_kn', 25.0),
            bolt_type = BoltType.GLUE_IN,
            rock_type = RockType.GRANITE,
        )
        anchor = AnchorSystem(components=[bolt], anchor_type=AnchorType.SINGLE_POINT)
        scenario.add_protection(pro['height_m'], anchor, label=pro.get('label', ''))

    return scenario, data


def cmd_scenario(args: argparse.Namespace) -> int:
    sub = getattr(args, 'scenario_sub', None)
    dispatch = {
        'build':  _scenario_build,
        'run':    _scenario_run,
        'zipper': _scenario_zipper,
        'sweep':  _scenario_sweep,
    }
    handler = dispatch.get(sub)
    if handler is None:
        print("Usage: ropesim scenario {build|run|zipper|sweep} ...")
        return 1
    return handler(args)


def _scenario_build(args: argparse.Namespace) -> int:
    """Interactive scenario builder."""
    print("\n  SCENARIO BUILDER — interactive mode\n")

    def ask(prompt, default=None, cast=str):
        if default is not None:
            val = input(f"  {prompt} [{default}]: ").strip()
            return cast(val) if val else cast(default)
        while True:
            val = input(f"  {prompt}: ").strip()
            if val:
                return cast(val)
            print("  (required)")

    rope_name  = ask("Rope name (from database)", "Beal Opera 8.5 Dry")
    mass       = ask("Climber mass (kg)", "80.0", float)
    device     = ask("Belay device", "atc")
    belay_h    = ask("Belay height (m)", "0.0", float)
    wet        = ask("Wet conditions? [y/n]", "n").lower().startswith('y')
    temp       = ask("Temperature (C)", "20.0", float)

    protection = []
    print("\n  Add protection points (empty height to stop):")
    while True:
        h_str = input("  Height (m) [done]: ").strip()
        if not h_str:
            break
        h_m   = float(h_str)
        mbs   = float(input(f"    MBS kN [25.0]: ").strip() or "25.0")
        label = input(f"    Label: ").strip() or f"piece at {h_m}m"
        protection.append({'height_m': h_m, 'mbs_kn': mbs, 'label': label})

    out_path = ask("Save to file", "scenario.ropesim")
    data = {
        'rope': rope_name, 'climber_mass_kg': mass, 'belay_device': device,
        'belay_height_m': belay_h, 'is_wet': wet, 'temperature_c': temp,
        'protection': protection,
    }
    with open(out_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n  Scenario saved to {out_path}\n")
    return 0


def _scenario_run(args: argparse.Namespace) -> int:
    scenario, data = _load_scenario_file(args.file)
    heights = [p['height_m'] for p in data.get('protection', [])]
    if not heights:
        print("Error: scenario has no protection points", file=sys.stderr)
        return 1

    climber_h = getattr(args, 'height', None) or (max(heights) + 2.0)
    result = scenario.simulate_fall(climber_h)

    if args.format == 'json':
        print(result.model_dump_json(indent=2))
        return 0

    print(_hdr(f"SCENARIO RUN — {args.file}"))
    print(_row('Climber height',  f'{climber_h:.1f} m'))
    print(_row('Fall factor',     f'{result.fall_factor:.3f}'))
    print(_row('Peak force',      f'{result.peak_force_kn:.2f} kN'))
    print(_row('Deceleration',    f'{result.peak_deceleration_g:.1f} g'))
    print(_row('Elongation',      f'{result.elongation_m:.3f} m'))
    if result.warnings:
        print(_hr('-'))
        for w in result.warnings:
            print(f"  ! {w}")
    print(_hr() + "\n")
    return 0


def _scenario_zipper(args: argparse.Namespace) -> int:
    scenario, data = _load_scenario_file(args.file)
    heights = [p['height_m'] for p in data.get('protection', [])]
    if not heights:
        print("Error: scenario has no protection points", file=sys.stderr)
        return 1

    climber_h = getattr(args, 'height', None) or (max(heights) + 2.0)
    result = scenario.simulate_zipper(climber_h)

    if args.format == 'json':
        out = {'total_failed': result.total_pieces_failed,
               'ground_fall': result.ground_fall_reached,
               'sequence': result.failure_sequence}
        print(json.dumps(out, indent=2))
        return 0

    print(_hdr(f"ZIPPER SIMULATION — {args.file}"))
    print(_row('Climber height',  f'{climber_h:.1f} m'))
    print(_row('Pieces failed',   str(result.total_pieces_failed)))
    print(_row('Ground fall',     'YES' if result.ground_fall_reached else 'No'))
    if result.failure_sequence:
        print(_hr('-'))
        pros = data.get('protection', [])
        for i, idx in enumerate(result.failure_sequence):
            if idx < len(pros):
                p = pros[idx]
                print(f"  Step {i+1}: {p.get('label','?')} at {p['height_m']}m failed")
    print(_hr() + "\n")
    return 0 if not result.ground_fall_reached else 1


def _scenario_sweep(args: argparse.Namespace) -> int:
    scenario, _ = _load_scenario_file(args.file)
    h_from = args.h_from
    h_to   = args.h_to
    steps  = args.steps

    sweep = scenario.sweep_fall_positions(height_range=(h_from, h_to), steps=steps)

    if args.format == 'json':
        out = [{'height_m': h, 'fall_factor': ff, 'peak_kn': pk}
               for h, ff, pk in zip(sweep.climber_heights_m,
                                     sweep.fall_factors,
                                     sweep.peak_forces_kn)]
        print(json.dumps(out, indent=2))
        return 0

    print(_hdr(f"SCENARIO SWEEP — {args.file}"))
    print(f"  {'Height (m)':>10}  {'Fall factor':>12}  {'Peak kN':>9}  Risk")
    print(_hr('-'))
    for h, ff, kn in zip(sweep.climber_heights_m,
                          sweep.fall_factors,
                          sweep.peak_forces_kn):
        risk = 'HIGH  ' if kn > 10.0 else ('MED   ' if kn > 7.0 else 'LOW   ')
        mark = ' <-- worst' if abs(h - sweep.worst_height_m) < 0.2 else ''
        print(f"  {h:>10.1f}  {ff:>12.3f}  {kn:>9.2f}  {risk}{mark}")
    print(_hr('-'))
    print(f"  Worst: {sweep.worst_height_m:.1f}m -> {sweep.worst_peak_kn:.2f} kN")
    print(_hr() + "\n")
    return 0


# ── validate subcommand group ─────────────────────────────────────────────────

def cmd_validate(args: argparse.Namespace) -> int:
    sub = getattr(args, 'validate_sub', None)
    dispatch = {
        'rope':     _validate_rope,
        'scenario': _validate_scenario,
        'system':   _validate_system,
    }
    handler = dispatch.get(sub)
    if handler is None:
        print("Usage: ropesim validate {rope|scenario|system} ...")
        return 1
    return handler(args)


def _validate_rope(args: argparse.Namespace) -> int:
    from ropesim.rope import Rope

    # Load from spec file or database name
    if hasattr(args, 'spec') and args.spec:
        with open(args.spec) as f:
            data = json.load(f)
        from ropesim.rope import RopeSpec
        spec = RopeSpec(**data)
        rope = Rope(spec)
    else:
        name = getattr(args, 'name', None)
        if not name:
            print("Error: --name or --spec required", file=sys.stderr)
            return 1
        rope = Rope.from_db(name)

    violations = rope.validate_standard_compliance()
    compliant = len(violations) == 0

    if getattr(args, 'format', 'text') == 'json':
        import json as _json
        print(_json.dumps({
            'rope': rope.spec.name,
            'compliant': compliant,
            'violations': violations,
        }, indent=2))
        return 0 if compliant else 1

    print(_hdr(f"ROPE VALIDATION — {rope.spec.name}"))
    if compliant:
        print("  PASS: No EN 892 / UIAA 101 violations.\n")
        return 0
    for v in violations:
        print(f"  FAIL: {v}")
    print(_hr() + "\n")
    return 1


def _validate_scenario(args: argparse.Namespace) -> int:
    from ropesim import standards

    scenario, data = _load_scenario_file(args.file)
    rope_name = data.get('rope', '')
    violations = []

    from ropesim import Rope
    try:
        rope = Rope.from_db(rope_name)
        v = rope.validate_standard_compliance()
        violations.extend([f"Rope: {x}" for x in v])
    except Exception as e:
        violations.append(f"Rope error: {e}")

    # Check each protection point
    for pro in data.get('protection', []):
        mbs = pro.get('mbs_kn', 0)
        if mbs < 5.0:
            violations.append(f"Protection '{pro.get('label','')}': MBS {mbs}kN below 5kN minimum")

    print(_hdr(f"SCENARIO VALIDATION — {args.file}"))
    if not violations:
        print("  PASS: All components compliant.\n")
        return 0
    for v in violations:
        print(f"  FAIL: {v}")
    print(_hr() + "\n")
    return 1


def _validate_system(args: argparse.Namespace) -> int:
    from ropesim import Rope, AnchorSystem, AnchorType, Bolt, BoltType, RockType, standards

    violations = []

    if args.rope:
        try:
            rope = Rope.from_db(args.rope)
            v = rope.validate_standard_compliance()
            violations.extend([f"Rope: {x}" for x in v])
        except KeyError as e:
            violations.append(f"Rope not found: {e}")

    # Check anchor load vs bolt MBS
    load = args.load
    bolt_mbs = args.bolt_mbs
    if load > bolt_mbs * 0.9:
        violations.append(
            f"Load {load:.1f}kN exceeds 90% of bolt MBS {bolt_mbs:.1f}kN")

    print(_hdr("SYSTEM VALIDATION"))
    print(_row('Rope',      args.rope or '—'))
    print(_row('Anchor',    args.anchor or '—'))
    print(_row('Bolt MBS',  f'{bolt_mbs:.1f} kN'))
    print(_row('Load',      f'{load:.1f} kN'))
    print(_hr('-'))
    if not violations:
        print("  PASS: System compliant.\n")
        return 0
    for v in violations:
        print(f"  FAIL: {v}")
    print(_hr() + "\n")
    return 1


# ── report ────────────────────────────────────────────────────────────────────

def cmd_report(args: argparse.Namespace) -> int:
    """Generate a PDF technical report for a scenario."""
    scenario, data = _load_scenario_file(args.scenario)
    heights = [p['height_m'] for p in data.get('protection', [])]
    if not heights:
        print("Error: scenario has no protection points", file=sys.stderr)
        return 1

    sweep = scenario.sweep_fall_positions(
        height_range=(min(heights) - 1.0, max(heights) + 3.0),
        steps=40,
    )

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        import numpy as np

        out_path = args.output or 'report.pdf'
        with PdfPages(out_path) as pdf:
            # Page 1: Title / summary
            fig, ax = plt.subplots(figsize=(8.5, 11))
            ax.axis('off')
            summary = [
                'ROPESIM TECHNICAL REPORT',
                '',
                f"Scenario: {args.scenario}",
                f"Rope:     {data.get('rope','')}",
                f"Climber:  {data.get('climber_mass_kg',80)} kg",
                f"Device:   {data.get('belay_device','')}",
                f"Wet:      {'Yes' if data.get('is_wet') else 'No'}",
                f"Temp:     {data.get('temperature_c',20)} C",
                '',
                'PROTECTION:',
            ]
            for p in data.get('protection', []):
                summary.append(f"  {p.get('label','piece')}: {p['height_m']}m, MBS={p.get('mbs_kn',25)}kN")
            summary += [
                '',
                f"Worst-case height: {sweep.worst_height_m:.1f} m",
                f"Worst-case peak:   {sweep.worst_peak_kn:.2f} kN",
            ]
            ax.text(0.1, 0.9, '\n'.join(summary), transform=ax.transAxes,
                    fontsize=11, verticalalignment='top', fontfamily='monospace')
            pdf.savefig(fig)
            plt.close(fig)

            if args.include_plots:
                # Page 2: Force sweep
                fig2, ax2 = plt.subplots(figsize=(10, 6))
                colors = ['#27ae60' if f <= 7 else '#f39c12' if f <= 10 else '#e74c3c'
                          for f in sweep.peak_forces_kn]
                ax2.bar(sweep.climber_heights_m, sweep.peak_forces_kn,
                        width=0.3, color=colors, alpha=0.85)
                ax2.axhline(9.0, color='red', linestyle='--', linewidth=0.8,
                            label='EN 892 limit')
                for h in heights:
                    ax2.axvline(h, color='blue', linestyle=':', alpha=0.5)
                ax2.set_xlabel('Climber height (m)')
                ax2.set_ylabel('Peak force (kN)')
                ax2.set_title('Peak anchor force vs climber height')
                ax2.legend()
                pdf.savefig(fig2)
                plt.close(fig2)

                # Page 3: Fall factor
                fig3, ax3 = plt.subplots(figsize=(10, 5))
                ax3.plot(sweep.climber_heights_m, sweep.fall_factors, 'o-',
                         color='#8e44ad', linewidth=1.8, markersize=4)
                ax3.set_xlabel('Climber height (m)')
                ax3.set_ylabel('Fall factor')
                ax3.set_title('Fall factor vs climber height')
                pdf.savefig(fig3)
                plt.close(fig3)

        print(f"  Report written to: {out_path}\n")
        return 0

    except ImportError:
        print("Error: matplotlib required for PDF reports (pip install matplotlib)",
              file=sys.stderr)
        return 1


# ── toprope ──��────────────────────────────────────────────────────────────────

def cmd_toprope(args: argparse.Namespace) -> int:
    from ropesim import Rope
    from ropesim._rustcore import (
        compute_top_rope_impact,
        compute_stiffness_from_spec,
        apply_temperature_modifier,
    )
    from ropesim.fall import BELAY_FRICTION_COEFFICIENTS, BelayDevice

    try:
        rope = Rope.from_db(args.rope)
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    spec = rope.spec
    base_k  = compute_stiffness_from_spec(spec.impact_force_kn,
                                           spec.dynamic_elongation_pct, 80.0)
    adj_k   = apply_temperature_modifier(base_k, getattr(args, 'temp', 20.0))

    try:
        device = BelayDevice(args.device.lower())
    except ValueError:
        device = BelayDevice.ATC
    friction = BELAY_FRICTION_COEFFICIENTS.get(device, 0.35)

    rope_length = getattr(args, 'rope_length', 30.0)
    peak_kn = compute_top_rope_impact(adj_k, args.mass, args.slack,
                                       rope_length, friction)

    if args.format == 'json':
        print(json.dumps({'slack_m': args.slack, 'peak_force_kn': round(peak_kn, 3),
                          'device': device.value}))
        return 0

    print(_hdr("TOP-ROPE SIMULATION"))
    print(_row('Rope',           spec.name))
    print(_row('Climber mass',   f'{args.mass:.0f} kg'))
    print(_row('Slack',          f'{args.slack:.2f} m'))
    print(_row('Device',         device.value))
    print(_row('Rope length',    f'{rope_length:.0f} m'))
    print(_hr('-'))
    fall_dist = 2 * args.slack
    ff = fall_dist / max(rope_length, 0.1)
    print(_row('Fall distance',  f'{fall_dist:.2f} m'))
    print(_row('Fall factor',    f'{ff:.4f}'))
    print(_row('Peak force',     f'{peak_kn:.3f} kN'))
    advice = ('Low force catch.' if peak_kn < 3.0 else
              'Moderate force — check slack.' if peak_kn < 6.0 else
              'High force — reduce slack.')
    print(_hr('-'))
    print(f"  {advice}")
    print(_hr() + "\n")

    if getattr(args, 'plot', False):
        _toprope_plot(args.mass, adj_k, friction, rope_length)

    return 0


def _toprope_plot(mass, stiffness_kn, friction, rope_length):
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        from ropesim._rustcore import compute_top_rope_impact

        slacks = np.linspace(0.05, 3.0, 60)
        forces = [compute_top_rope_impact(stiffness_kn, mass, s, rope_length, friction)
                  for s in slacks]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(slacks, forces, color='#2270c4', linewidth=2)
        ax.fill_between(slacks, forces, alpha=0.15, color='#2270c4')
        ax.axhline(3.0, color='green', linestyle='--', linewidth=0.8, label='3 kN')
        ax.set_xlabel('Slack in system (m)')
        ax.set_ylabel('Peak force (kN)')
        ax.set_title('Top-rope catch force vs system slack')
        ax.legend()
        plt.tight_layout()
        plt.show()
    except ImportError:
        print("(pip install matplotlib for plots)")


# ── rappel ────────────────────────────────────────────────────────────────────

def cmd_rappel(args: argparse.Namespace) -> int:
    from ropesim._rustcore import compute_rappel_load

    load_normal = compute_rappel_load(args.mass, args.device_friction,
                                       args.speed, False)
    load_stop   = compute_rappel_load(args.mass, args.device_friction,
                                       args.speed, True)

    if args.format == 'json':
        print(json.dumps({'normal_load_kn': round(load_normal, 3),
                          'sudden_stop_kn': round(load_stop, 3),
                          'anchor_mbs_kn':  args.anchor_mbs}))
        return 0

    margin_n = (args.anchor_mbs / load_normal - 1) * 100
    margin_s = (args.anchor_mbs / load_stop  - 1) * 100

    print(_hdr("RAPPEL ANALYSIS"))
    print(_row('Climber mass',     f'{args.mass:.0f} kg'))
    print(_row('Rappel speed',     f'{args.speed:.1f} m/s'))
    print(_row('Device friction',  f'{args.device_friction:.2f}'))
    print(_row('Anchor MBS',       f'{args.anchor_mbs:.0f} kN'))
    print(_hr('-'))
    print(_row('Normal load',      f'{load_normal:.3f} kN  ({margin_n:.0f}% margin)'))
    print(_row('Sudden-stop load', f'{load_stop:.3f} kN  ({margin_s:.0f}% margin)'))
    print(_hr('-'))
    if margin_s < 20:
        print("  WARNING: Sudden-stop load within 20% of anchor MBS.")
    else:
        print("  Anchor within safe limits for both scenarios.")
    print(_hr() + "\n")
    return 0


# ── haul ──────────────────────────────────────────────────────────────────────

def cmd_haul(args: argparse.Namespace) -> int:
    from ropesim._rustcore import compute_haul_system_force, HaulSystem

    system_map = {
        '3:1': HaulSystem.ThreeToOne,
        '5:1': HaulSystem.FiveToOne,
        '6:1': HaulSystem.SixToOne,
        '9:1': HaulSystem.Piggyback,
        'piggyback': HaulSystem.Piggyback,
    }
    hs = system_map.get(str(args.system).lower())
    if hs is None:
        print(f"Error: unknown system '{args.system}'. Valid: 3:1, 5:1, 6:1, 9:1/piggyback",
              file=sys.stderr)
        return 1

    result = compute_haul_system_force(args.load, hs, args.friction)
    anchor_kn = result.anchor_load_n / 1000.0
    hauler_kn = result.hauler_effort_n / 1000.0
    margin    = (args.anchor_mbs / anchor_kn - 1) * 100 if args.anchor_mbs > 0 else None

    if args.format == 'json':
        print(json.dumps({
            'theoretical_ma': result.theoretical_ma,
            'actual_ma':      round(result.actual_ma, 3),
            'hauler_effort_kn': round(hauler_kn, 3),
            'anchor_load_kn': round(anchor_kn, 3),
        }))
        return 0

    print(_hdr(f"HAUL SYSTEM — {args.system}"))
    print(_row('Load',              f'{args.load:.0f} kg'))
    print(_row('Friction loss',     f'{args.friction:.0%} per redirect'))
    print(_row('Theoretical MA',    f'{result.theoretical_ma:.0f}:1'))
    print(_row('Actual MA',         f'{result.actual_ma:.2f}:1'))
    print(_hr('-'))
    print(_row('Hauler effort',     f'{hauler_kn:.3f} kN  ({result.hauler_effort_n:.0f} N)'))
    print(_row('Anchor load',       f'{anchor_kn:.3f} kN'))
    if margin is not None:
        print(_row('Anchor margin', f'{margin:.0f}%'))
        if margin < 100:
            print(_hr('-'))
            print(f"  WARNING: Haul load uses >{100-margin:.0f}% of anchor MBS!")
    print(_hr() + "\n")
    return 0


# ── interactive REPL ──────────────────────────────────────────────────────────

def cmd_interactive(args: argparse.Namespace) -> int:
    import code as _code
    import readline  # noqa: F401 -- enables history/completion

    banner = """
  ropesim interactive REPL
  ========================
  Pre-loaded: Rope, Fall, FallConditions, AnchorSystem, Scenario,
              BelayDevice, PhysicsMode, HaulSystem, SimulationReplay
  Type 'help(Rope)' for docs, 'exit()' or Ctrl-D to quit.
"""
    try:
        from ropesim import (
            Rope, Fall, FallConditions, AnchorSystem, Scenario,
            BelayDevice, PhysicsMode, HaulSystem, SimulationReplay,
            Bolt, BoltType, Cam, CamPlacement, Nut, Sling,
            AnchorType, RockType, SlingMaterial,
        )
        from ropesim._rustcore import (
            compute_top_rope_impact, compute_rappel_load,
            compute_haul_system_force,
        )
        _locals = {k: v for k, v in locals().items() if not k.startswith('_')}
    except ImportError as e:
        print(f"Import error: {e}", file=sys.stderr)
        _locals = {}

    _code.interact(banner=banner, local=_locals)
    return 0


# ── Parser registration ───────────────────────────────────────────────────────

def register_v2_commands(sub: argparse._SubParsersAction) -> None:
    """Register all v2 subcommands on an existing argparse subparser group."""

    FMT = dict(metavar='FMT', default='text',
               help='Output format: text (default) | json')

    # ── rope ──
    p_rope = sub.add_parser('rope', help='Rope database management')
    rope_sub = p_rope.add_subparsers(dest='rope_sub')

    p_rl = rope_sub.add_parser('list', help='List/filter ropes')
    p_rl.add_argument('--type',           default=None)
    p_rl.add_argument('--dry',            action='store_true')
    p_rl.add_argument('--max-diameter',   type=float, default=None, metavar='MM')
    p_rl.add_argument('--min-falls',      type=int,   default=None, metavar='N')
    p_rl.add_argument('--manufacturer',   default=None)
    p_rl.add_argument('--sort',           default='name',
                      choices=['diameter','falls','impact_force','weight','name'])
    p_rl.add_argument('--format',         **FMT)

    p_rs = rope_sub.add_parser('show', help='Show full rope spec')
    p_rs.add_argument('rope_name')
    p_rs.add_argument('--format', **FMT)

    p_rc = rope_sub.add_parser('compare', help='Compare ropes side by side')
    p_rc.add_argument('names', nargs='+')
    p_rc.add_argument('--format', **FMT)

    rope_sub.add_parser('add',    help='Interactively add a rope to local database')
    p_ri = rope_sub.add_parser('import', help='Import rope spec from JSON file')
    p_ri.add_argument('--file', required=True)

    p_rr = rope_sub.add_parser('retire', help='Check retirement status')
    p_rr.add_argument('rope_name')
    p_rr.add_argument('--falls-taken', type=int, required=True, metavar='N')
    p_rr.add_argument('--format', **FMT)

    # ── scenario ──
    p_scen = sub.add_parser('scenario', help='Scenario file management')
    scen_sub = p_scen.add_subparsers(dest='scenario_sub')

    scen_sub.add_parser('build', help='Interactively build a scenario file')

    p_sr = scen_sub.add_parser('run', help='Run a scenario file')
    p_sr.add_argument('--file', required=True)
    p_sr.add_argument('--height', type=float, default=None, metavar='M')
    p_sr.add_argument('--format', **FMT)

    p_sz = scen_sub.add_parser('zipper', help='Zipper failure simulation')
    p_sz.add_argument('--file', required=True)
    p_sz.add_argument('--height', type=float, default=None, metavar='M')
    p_sz.add_argument('--format', **FMT)

    p_ss = scen_sub.add_parser('sweep', help='Sweep climber heights')
    p_ss.add_argument('--file',   required=True)
    p_ss.add_argument('--from',   dest='h_from', type=float, default=2.0)
    p_ss.add_argument('--to',     dest='h_to',   type=float, default=30.0)
    p_ss.add_argument('--steps',  type=int, default=20)
    p_ss.add_argument('--format', **FMT)

    # ── validate (v2) ──
    p_val = sub.add_parser('validate', help='Compliance checks (v2)')
    val_sub = p_val.add_subparsers(dest='validate_sub')

    p_vr2 = val_sub.add_parser('rope',     help='Validate a rope spec')
    p_vr2.add_argument('--name', default=None)
    p_vr2.add_argument('--spec', default=None, metavar='FILE')
    p_vr2.add_argument('--format', **FMT)

    p_vs = val_sub.add_parser('scenario', help='Validate a scenario file')
    p_vs.add_argument('--file', required=True)
    p_vs.add_argument('--format', **FMT)

    p_vsys = val_sub.add_parser('system', help='Quick system check')
    p_vsys.add_argument('--rope',      default=None)
    p_vsys.add_argument('--anchor',    default=None)
    p_vsys.add_argument('--bolt-mbs',  type=float, default=25.0, dest='bolt_mbs')
    p_vsys.add_argument('--load',      type=float, required=True)
    p_vsys.add_argument('--format', **FMT)

    # ── report ──
    p_rep = sub.add_parser('report', help='Generate PDF technical report')
    p_rep.add_argument('--scenario',       required=True, metavar='FILE')
    p_rep.add_argument('--output',         default='report.pdf', metavar='FILE')
    p_rep.add_argument('--include-plots',  action='store_true', dest='include_plots')

    # ── toprope ──
    p_tr = sub.add_parser('toprope', help='Top-rope catch simulation')
    p_tr.add_argument('--rope',         required=True)
    p_tr.add_argument('--mass',         type=float, default=80.0)
    p_tr.add_argument('--slack',        type=float, required=True, metavar='M')
    p_tr.add_argument('--device',       default='atc')
    p_tr.add_argument('--rope-length',  type=float, default=30.0, dest='rope_length')
    p_tr.add_argument('--temp',         type=float, default=20.0)
    p_tr.add_argument('--plot',         action='store_true')
    p_tr.add_argument('--format', **FMT)

    # ── rappel ──
    p_rap = sub.add_parser('rappel', help='Rappel anchor load calculation')
    p_rap.add_argument('--mass',             type=float, required=True, metavar='KG')
    p_rap.add_argument('--device-friction',  type=float, default=0.4, dest='device_friction')
    p_rap.add_argument('--speed',            type=float, default=0.8, metavar='MPS')
    p_rap.add_argument('--anchor-mbs',       type=float, default=25.0, dest='anchor_mbs')
    p_rap.add_argument('--format', **FMT)

    # ── haul ──
    p_haul = sub.add_parser('haul', help='Mechanical advantage haul system')
    p_haul.add_argument('--system',     required=True,
                        choices=['3:1','5:1','6:1','9:1','piggyback'])
    p_haul.add_argument('--load',       type=float, required=True, metavar='KG')
    p_haul.add_argument('--friction',   type=float, default=0.12)
    p_haul.add_argument('--anchor-mbs', type=float, default=25.0, dest='anchor_mbs')
    p_haul.add_argument('--format', **FMT)

    # ── interactive ──
    sub.add_parser('interactive', help='Python REPL with ropesim pre-loaded')


def v2_dispatch() -> dict:
    """Return the dispatch dict for all v2 commands."""
    return {
        'rope':        cmd_rope,
        'scenario':    cmd_scenario,
        'validate':    cmd_validate,
        'report':      cmd_report,
        'toprope':     cmd_toprope,
        'rappel':      cmd_rappel,
        'haul':        cmd_haul,
        'interactive': cmd_interactive,
    }
