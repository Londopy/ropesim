'use client';

// Pagefind search modal, opened with Cmd+K / Ctrl+K.
// The pagefind bundle only exists in the static export (`npm run build`);
// in `next dev` the dialog explains how to enable it.

import { useCallback, useEffect, useRef, useState } from 'react';

interface Result {
  url: string;
  title: string;
  excerpt: string;
}

declare global {
  interface Window {
    __pagefind?: {
      search: (q: string) => Promise<{
        results: {
          data: () => Promise<{
            url: string;
            meta: { title?: string };
            excerpt: string;
          }>;
        }[];
      }>;
    };
  }
}

export default function SearchDialog() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Result[]>([]);
  const [ready, setReady] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    if (!window.__pagefind) {
      // Load the pagefind bundle generated at build time.
      const base = document.querySelector('base')?.href ?? '/';
      import(/* webpackIgnore: true */ `${base}_pagefind/pagefind.js`)
        .then((pf) => {
          window.__pagefind = pf;
          setReady(true);
        })
        .catch(() => setReady(false));
    } else {
      setReady(true);
    }
  }, [open]);

  const runSearch = useCallback(async (q: string) => {
    setQuery(q);
    if (!q || !window.__pagefind) {
      setResults([]);
      return;
    }
    const res = await window.__pagefind.search(q);
    const data = await Promise.all(res.results.slice(0, 8).map((r) => r.data()));
    setResults(
      data.map((d) => ({
        url: d.url,
        title: d.meta.title ?? d.url,
        excerpt: d.excerpt,
      })),
    );
  }, []);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="hidden items-center gap-2 rounded border border-line bg-raised px-2.5 py-1 font-heading text-xs text-muted transition-colors hover:border-accent-dim sm:flex"
      >
        search <kbd className="rounded bg-surface px-1 text-[10px]">⌘K</kbd>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-start justify-center bg-black/60 pt-24"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-lg border border-line bg-surface shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => runSearch(e.target.value)}
              placeholder="search the docs…"
              className="w-full border-b border-line bg-transparent px-4 py-3 font-heading text-sm text-bright outline-none placeholder:text-muted"
            />
            <div className="max-h-80 overflow-y-auto p-2">
              {!ready && (
                <p className="p-3 text-sm text-muted">
                  Search index loads from the static build (`npm run build`).
                </p>
              )}
              {ready && query && results.length === 0 && (
                <p className="p-3 text-sm text-muted">no results</p>
              )}
              {results.map((r) => (
                <a
                  key={r.url}
                  href={r.url}
                  className="block rounded p-3 hover:bg-raised"
                  onClick={() => setOpen(false)}
                >
                  <p className="font-heading text-sm text-accent">{r.title}</p>
                  <p
                    className="text-xs text-muted [&_mark]:bg-accent-dim [&_mark]:text-bright"
                    dangerouslySetInnerHTML={{ __html: r.excerpt }}
                  />
                </a>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
