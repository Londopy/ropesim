'use client';

import { useState } from 'react';

export default function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1600);
      }}
      className="rounded border border-line bg-raised px-2 py-1 font-heading text-[11px] text-muted transition-colors hover:border-accent-dim hover:text-accent"
      aria-label="Copy to clipboard"
    >
      {copied ? '✓ copied' : 'copy'}
    </button>
  );
}
