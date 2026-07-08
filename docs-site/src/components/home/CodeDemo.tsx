// Server component: tabbed live code demo, Shiki-highlighted.

import { codeToHtml } from 'shiki';
import Tabs from '@/components/docs/Tabs';

const LIBRARY = `from ropesim import Rope, Fall, FallConditions, BelayDevice

rope = Rope.from_db("Beal Joker 9.1 Dry")
fall = Fall(
    rope=rope,
    conditions=FallConditions(
        climber_mass_kg=80,
        fall_distance_m=4.0,
        rope_out_m=8.0,
        belay_device=BelayDevice.GRIGRI,
    ),
)

print(f"fall factor  {fall.fall_factor:.2f}")
print(f"peak force   {fall.peak_force:.2f} kN")

result = fall.simulate()             # full RK4 force-time curve
curve = fall.force_curve_numpy()     # → numpy array`;

const CLI = `$ ropesim-cli rope list --manufacturer Beal
$ ropesim-cli rope compare "Beal Opera 8.5 Dry" "Beal Joker 9.1 Dry"
$ ropesim-cli scenario run route.ropesim --height 16
$ ropesim-cli toprope --rope "Beal Joker 9.1 Dry" --mass 80 --slack 1.5
$ ropesim-cli haul --system 3:1 --load 95
$ ropesim-cli validate rope --name "Beal Opera 8.5 Dry"
$ ropesim-cli report route.ropesim -o report.pdf
$ ropesim tui        # full-screen terminal UI (v3)`;

const SCENARIO = `from ropesim import Rope, Scenario, AnchorSystem, Bolt, AnchorType
from ropesim import PhysicsMode

rope = Rope.from_db("Sterling Evolution Velocity 9.8")
anchor = AnchorSystem(AnchorType.SLIDING_X, [Bolt(), Bolt()])

scenario = Scenario(rope, climber_mass_kg=72)
scenario.add_protection(8.0, anchor, label="first bolt")
scenario.add_protection(14.0, anchor, label="second bolt")

result = scenario.simulate_fall(climber_height_m=16.0)
rapier = scenario.simulate_fall(16.0, mode=PhysicsMode.RAPIER_3D)
sweep = scenario.sweep_fall_positions()   # parallel, via Rayon
zipper = scenario.simulate_zipper(16.0)   # progressive failure`;

async function Block({ code, lang }: { code: string; lang: string }) {
  const html = await codeToHtml(code, { lang, theme: 'vitesse-dark' });
  return (
    <div
      className="overflow-hidden rounded-b-lg border border-t-0 border-line [&_pre]:!m-0 [&_pre]:!rounded-none [&_pre]:!border-0"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

export default function CodeDemo() {
  return (
    <section className="mx-auto max-w-4xl px-4 py-16">
      <h2 className="font-heading text-2xl text-bright">three ways in</h2>
      <p className="mt-2 text-sm text-muted">
        The same Rust core answers whether you call it from Python, the
        terminal, or the desktop app.
      </p>
      <Tabs labels={['Library', 'CLI', 'Scenario builder']}>
        <Block code={LIBRARY} lang="python" />
        <Block code={CLI} lang="bash" />
        <Block code={SCENARIO} lang="python" />
      </Tabs>
    </section>
  );
}
