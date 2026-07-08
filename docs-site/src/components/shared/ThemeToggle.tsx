'use client';

import { useEffect, useState } from 'react';

export default function ThemeToggle() {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');

  useEffect(() => {
    const saved = window.localStorage.getItem('ropesim-theme');
    if (saved === 'light' || saved === 'dark') {
      setTheme(saved);
      document.documentElement.dataset.theme = saved;
    }
  }, []);

  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.dataset.theme = next;
    window.localStorage.setItem('ropesim-theme', next);
  };

  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="font-heading text-sm text-muted hover:text-accent"
    >
      {theme === 'dark' ? '◐' : '◑'}
    </button>
  );
}
