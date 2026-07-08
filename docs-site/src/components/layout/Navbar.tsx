'use client';

import Link from 'next/link';
import SearchDialog from '@/components/shared/SearchDialog';
import ThemeToggle from '@/components/shared/ThemeToggle';

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-bg/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
        <Link href="/" className="group flex items-baseline gap-2">
          {/* rope-curve mark */}
          <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden>
            <path
              d="M4 20 C 8 20, 6 4, 12 4 S 16 20, 20 20"
              fill="none"
              stroke="var(--accent)"
              strokeWidth="2.4"
              strokeLinecap="round"
            />
          </svg>
          <span className="font-heading text-lg font-semibold text-bright group-hover:text-accent">
            ropesim
          </span>
          <span className="font-heading text-[10px] text-muted">v3</span>
        </Link>

        <nav className="hidden gap-5 font-heading text-sm text-muted sm:flex">
          <Link href="/quickstart/" className="hover:text-accent">docs</Link>
          <Link href="/api/reference/" className="hover:text-accent">api</Link>
          <Link href="/gui/overview/" className="hover:text-accent">gui</Link>
          <Link href="/changelog/" className="hover:text-accent">changelog</Link>
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <SearchDialog />
          <ThemeToggle />
          <a
            href="https://github.com/Londopy/ropesim"
            className="font-heading text-sm text-muted hover:text-accent"
            target="_blank"
            rel="noreferrer"
          >
            github ↗
          </a>
        </div>
      </div>
    </header>
  );
}
