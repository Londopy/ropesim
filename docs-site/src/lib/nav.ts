// Sidebar navigation structure — single source of truth for doc ordering.

export interface NavItem {
  title: string;
  slug: string; // path under /, e.g. "quickstart" or "concepts/fall-physics"
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const nav: NavSection[] = [
  {
    title: 'Getting started',
    items: [
      { title: 'Installation', slug: 'installation' },
      { title: 'Quickstart', slug: 'quickstart' },
    ],
  },
  {
    title: 'Concepts',
    items: [
      { title: 'Fall physics', slug: 'concepts/fall-physics' },
      { title: 'Anchor systems', slug: 'concepts/anchor-systems' },
      { title: 'Rope specs', slug: 'concepts/rope-specs' },
      { title: 'Standards', slug: 'concepts/standards' },
    ],
  },
  {
    title: 'API reference',
    items: [
      { title: 'Rope', slug: 'api/rope' },
      { title: 'Fall', slug: 'api/fall' },
      { title: 'Anchor', slug: 'api/anchor' },
      { title: 'Scenario', slug: 'api/simulate' },
      { title: 'v3 physics', slug: 'api/physics-v3' },
      { title: 'Visualisation', slug: 'api/viz' },
      { title: 'CLI', slug: 'api/cli' },
      { title: 'Generated reference', slug: 'api/reference' },
    ],
  },
  {
    title: 'Desktop GUI',
    items: [
      { title: 'Overview', slug: 'gui/overview' },
      { title: 'Route canvas', slug: 'gui/canvas' },
      { title: 'Running simulations', slug: 'gui/simulation' },
      { title: 'Rope database', slug: 'gui/rope-database' },
    ],
  },
  {
    title: 'More',
    items: [
      { title: 'Notebooks', slug: 'notebooks' },
      { title: 'TUI', slug: 'tui' },
      { title: 'Changelog', slug: 'changelog' },
      { title: 'Contributing', slug: 'contributing' },
    ],
  },
];

export const allSlugs = nav.flatMap((s) => s.items.map((i) => i.slug));
