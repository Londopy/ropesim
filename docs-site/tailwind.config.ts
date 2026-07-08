import type { Config } from 'tailwindcss';

// Topographic & materials theme — tokens live as CSS variables in
// globals.css so a light theme is a single swap.
const config: Config = {
  content: ['./src/**/*.{ts,tsx}', './content/**/*.mdx'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        raised: 'var(--surface-raised)',
        line: 'var(--border)',
        accent: 'var(--accent)',
        'accent-dim': 'var(--accent-dim)',
        body: 'var(--text-primary)',
        muted: 'var(--text-secondary)',
        bright: 'var(--text-bright)',
        warning: 'var(--warning)',
        danger: 'var(--danger)',
        codebg: 'var(--code-bg)',
      },
      fontFamily: {
        heading: ['var(--font-plex-mono)', 'monospace'],
        body: ['var(--font-dm-sans)', 'sans-serif'],
        code: ['var(--font-jetbrains)', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
