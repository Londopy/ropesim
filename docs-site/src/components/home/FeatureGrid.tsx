'use client';

import { motion } from 'framer-motion';

const FEATURES = [
  {
    icon: '⛰',
    title: 'Rust core physics',
    body: 'RK4 damped-spring integration and Rapier3D rigid-body rope simulation, exposed through PyO3 and a plain C FFI.',
  },
  {
    icon: '◉',
    title: 'UIAA 101 / EN 892',
    body: 'The standards-based impact force model, with wet-rope, temperature, and rope-degradation modifiers.',
  },
  {
    icon: '⚯',
    title: 'v3 physics',
    body: 'Twin/half rope interaction, knot strength reduction, sheath abrasion accumulation, and fall probability modelling.',
  },
  {
    icon: '⚓',
    title: 'Anchor models',
    body: 'Sliding-X, quad, and cordelette equalisation with progressive component failure and load-angle sweeps.',
  },
  {
    icon: '▤',
    title: '25-rope database',
    body: 'Real EN 892 spec sheets from Beal, Mammut, Sterling, Petzl, Edelrid, Black Diamond, and more.',
  },
  {
    icon: '❯_',
    title: 'Four frontends',
    body: 'Python library, 20+ command CLI, terminal UI, and a native Qt6 desktop app with a 60 fps OpenGL viewport.',
  },
];

export default function FeatureGrid() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-20">
      <h2 className="font-heading text-2xl text-bright">
        what&apos;s in the box
      </h2>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f, i) => (
          <motion.div
            key={f.title}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: i * 0.08, duration: 0.45, ease: 'easeOut' }}
            className="group rounded-lg border border-line bg-surface p-5 transition-colors hover:border-accent-dim"
          >
            <span className="font-heading text-xl text-accent">{f.icon}</span>
            <h3 className="mt-3 font-heading text-base text-bright group-hover:text-accent">
              {f.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-muted">{f.body}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
