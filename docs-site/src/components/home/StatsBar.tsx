const STATS = [
  { value: '25', label: 'ropes in database' },
  { value: '20+', label: 'CLI commands' },
  { value: '60 fps', label: 'OpenGL rope renderer' },
  { value: '4', label: 'frontends, one core' },
];

export default function StatsBar() {
  return (
    <section className="mx-auto max-w-7xl px-4 pb-4">
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4">
        {STATS.map((s) => (
          <div key={s.label} className="bg-surface px-4 py-5 text-center">
            <p className="font-heading text-2xl font-semibold text-accent">
              {s.value}
            </p>
            <p className="mt-1 font-heading text-[11px] uppercase tracking-widest text-muted">
              {s.label}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
