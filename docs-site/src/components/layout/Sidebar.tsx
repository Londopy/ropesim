'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { nav } from '@/lib/nav';
import { useState } from 'react';

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  return (
    <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-60 shrink-0 overflow-y-auto border-r border-line py-6 pr-4 lg:block">
      {nav.map((section) => {
        const isCollapsed = collapsed[section.title];
        return (
          <div key={section.title} className="mb-5">
            <button
              onClick={() =>
                setCollapsed((c) => ({ ...c, [section.title]: !isCollapsed }))
              }
              className="mb-1.5 flex w-full items-center justify-between font-heading text-[11px] uppercase tracking-widest text-muted hover:text-accent"
            >
              {section.title}
              <span>{isCollapsed ? '+' : '−'}</span>
            </button>
            {!isCollapsed &&
              section.items.map((item) => {
                const href = `/${item.slug}/`;
                const active = pathname === href || pathname === `/${item.slug}`;
                return (
                  <Link
                    key={item.slug}
                    href={href}
                    className={`block border-l py-1 pl-3 text-sm transition-colors ${
                      active
                        ? 'border-accent font-medium text-accent'
                        : 'border-line text-body hover:border-accent-dim hover:text-bright'
                    }`}
                  >
                    {item.title}
                  </Link>
                );
              })}
          </div>
        );
      })}
    </aside>
  );
}
