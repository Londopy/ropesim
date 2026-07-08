'use client';

// Full-viewport hero. GSAP timeline: title types in, subtitle fades up,
// tag pills slide in, CTAs appear, install command last. A slow morphing
// rope curve breathes in the background.

import { useEffect, useRef } from 'react';
import Link from 'next/link';
import gsap from 'gsap';
import CopyButton from '@/components/shared/CopyButton';

const TAGS = ['Python', 'Rust', 'C++ / Qt6', 'UIAA 101', 'EN 892'];

export default function Hero() {
  const root = useRef<HTMLDivElement>(null);
  const rope = useRef<SVGPathElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: 'power2.out' } });
      tl.from('.hero-char', { opacity: 0, y: 14, stagger: 0.06, duration: 0.3 })
        .from('.hero-sub', { opacity: 0, y: 12, duration: 0.5 }, '-=0.1')
        .from('.hero-tag', { opacity: 0, x: -14, stagger: 0.07, duration: 0.3 })
        .from('.hero-cta', { opacity: 0, y: 10, stagger: 0.1, duration: 0.4 })
        .from('.hero-install', { opacity: 0, duration: 0.6 });

      // Slow rope morph — 14 s breathing loop.
      if (rope.current) {
        gsap.to(rope.current, {
          attr: {
            d: 'M -40 620 C 260 640, 190 210, 480 190 S 690 560, 1010 540',
          },
          duration: 14,
          repeat: -1,
          yoyo: true,
          ease: 'sine.inOut',
        });
      }
    }, root);
    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={root}
      className="relative flex min-h-[calc(100vh-3.5rem)] items-center overflow-hidden"
    >
      {/* animated rope curve */}
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full opacity-25"
        viewBox="0 0 960 720"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden
      >
        <path
          ref={rope}
          d="M -40 560 C 220 580, 230 170, 500 150 S 720 600, 1010 580"
          fill="none"
          stroke="var(--accent)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray="1 7"
        />
      </svg>

      <div className="mx-auto w-full max-w-7xl px-4">
        <h1 className="font-heading text-6xl font-bold tracking-tight text-bright sm:text-8xl">
          {'ropesim'.split('').map((c, i) => (
            <span key={i} className="hero-char inline-block">
              {c}
            </span>
          ))}
          <span className="hero-char inline-block animate-pulse text-accent">
            _
          </span>
        </h1>

        <p className="hero-sub mt-4 max-w-xl text-lg text-muted">
          Climbing rope physics engine. UIAA 101 / EN 892 fall model in Rust —
          consumed from Python, the terminal, or a native 3D desktop app.
        </p>

        <div className="mt-6 flex flex-wrap gap-2">
          {TAGS.map((t) => (
            <span
              key={t}
              className="hero-tag rounded-full border border-line bg-raised px-3 py-1 font-heading text-xs text-body"
            >
              {t}
            </span>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-4">
          <Link
            href="/quickstart/"
            className="hero-cta rounded bg-accent px-5 py-2.5 font-heading text-sm font-semibold text-black transition-transform hover:-translate-y-0.5"
          >
            Get started →
          </Link>
          <a
            href="https://github.com/Londopy/ropesim"
            className="hero-cta rounded border border-line px-5 py-2.5 font-heading text-sm text-body transition-colors hover:border-accent-dim hover:text-accent"
          >
            View on GitHub
          </a>
        </div>

        <div className="hero-install mt-10 inline-flex items-center gap-3 rounded-lg border border-line bg-codebg px-4 py-2.5">
          <code className="font-code text-sm">
            <span className="text-muted">$</span>{' '}
            <span className="text-bright">pip install ropesim</span>
          </code>
          <CopyButton text="pip install ropesim" />
        </div>
      </div>
    </section>
  );
}
