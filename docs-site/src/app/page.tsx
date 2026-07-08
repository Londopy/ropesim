import Hero from '@/components/home/Hero';
import StatsBar from '@/components/home/StatsBar';
import FeatureGrid from '@/components/home/FeatureGrid';
import CodeDemo from '@/components/home/CodeDemo';
import InstallBanner from '@/components/home/InstallBanner';
import Link from 'next/link';

const COLUMNS = [
  {
    title: 'Library',
    body: 'import and compute in Python — falls, anchors, sweeps, numpy out.',
    href: '/quickstart/',
    label: 'quickstart →',
  },
  {
    title: 'GUI',
    body: 'native desktop app: drag-and-drop routes, 3D playback, force plots.',
    href: '/gui/overview/',
    label: 'gui guide →',
  },
  {
    title: 'CLI + TUI',
    body: 'full terminal workflow, from one-liners to a full-screen dashboard.',
    href: '/api/cli/',
    label: 'cli reference →',
  },
];

export default function Home() {
  return (
    <>
      <Hero />
      <StatsBar />
      <section className="mx-auto grid max-w-7xl gap-4 px-4 py-14 md:grid-cols-3">
        {COLUMNS.map((c) => (
          <div
            key={c.title}
            className="rounded-lg border border-line bg-surface p-6"
          >
            <h3 className="font-heading text-lg text-bright">{c.title}</h3>
            <p className="mt-2 text-sm text-muted">{c.body}</p>
            <Link
              href={c.href}
              className="mt-4 inline-block font-heading text-sm text-accent hover:underline"
            >
              {c.label}
            </Link>
          </div>
        ))}
      </section>
      <FeatureGrid />
      <CodeDemo />
      <InstallBanner />
    </>
  );
}
