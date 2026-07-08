'use client';

import { useEffect, useState } from 'react';

interface Heading {
  depth: number;
  text: string;
  id: string;
}

export default function TableOfContents({ headings }: { headings: Heading[] }) {
  const [active, setActive] = useState<string>('');

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) setActive(e.target.id);
        }
      },
      { rootMargin: '-80px 0px -70% 0px' },
    );
    for (const h of headings) {
      const el = document.getElementById(h.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [headings]);

  if (headings.length === 0) return null;

  return (
    <nav className="sticky top-20 hidden w-52 shrink-0 self-start xl:block">
      <p className="mb-2 font-heading text-[11px] uppercase tracking-widest text-muted">
        On this page
      </p>
      {headings.map((h) => (
        <a
          key={h.id}
          href={`#${h.id}`}
          className={`block py-1 text-[13px] leading-snug transition-colors ${
            h.depth === 3 ? 'pl-4' : ''
          } ${active === h.id ? 'text-accent' : 'text-muted hover:text-body'}`}
        >
          {h.text}
        </a>
      ))}
    </nav>
  );
}
