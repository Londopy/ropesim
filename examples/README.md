# ropesim examples

Two self-contained demos. Each one sets up every parameter, runs a real
simulation, and plots the results — nothing to configure, just run it.

## Requirements

```bash
pip install ropesim          # library + compiled physics core
pip install matplotlib       # plotting (pulled in by the demos)
```

The 3-D demo additionally needs the Rapier world, which ships in the released
wheels. If you're on a local source checkout, build the core first with
`maturin develop --release`.

## `demo_2d.py` — analytical fall analysis

Loads a rope, specifies a full fall (mass, fall distance, rope out, belay
device, temperature, edge, timestep, damping), runs the UIAA / RK4 model, then
produces six figures:

- force–time curve
- belay-device comparison (ATC vs GriGri vs Munter, peak force)
- fall energy budget
- rope elongation curve with EN reference lines
- peak force vs. climber position (whole-route sweep)
- route schematic with protection placement

```bash
python examples/demo_2d.py                 # save PNGs to examples/output/
python examples/demo_2d.py --show          # also display the figures
python examples/demo_2d.py --rope "Mammut Infinity 9.5 Dry"
```

## `demo_3d.py` — Rapier 3-D fall

Builds a full scenario (vertical rock face + bolt protection), spins up the
Rapier rigid-body world, steps the physics, and plots the rope in 3-D at the
moment of peak load, the climber's fall path through space, and the anchor
force–time curve.

```bash
python examples/demo_3d.py                 # save PNG to examples/output/
python examples/demo_3d.py --show          # also display the figure
python examples/demo_3d.py --rope "Beal Joker 9.1 Dry"
```

Both scripts write their PNGs to `examples/output/` by default; pass
`--output DIR` to change that.
