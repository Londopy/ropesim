// MDX loading + frontmatter parsing for the content/ directory.

import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';

const CONTENT_DIR = path.join(process.cwd(), 'content');

export interface DocPage {
  slug: string;
  title: string;
  description: string;
  source: string; // raw MDX body
  headings: { depth: number; text: string; id: string }[];
}

export function slugToFile(slug: string): string | null {
  const candidates = [
    path.join(CONTENT_DIR, `${slug}.mdx`),
    path.join(CONTENT_DIR, slug, 'index.mdx'),
  ];
  for (const c of candidates) if (fs.existsSync(c)) return c;
  return null;
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-');
}

export function loadDoc(slug: string): DocPage | null {
  const file = slugToFile(slug);
  if (!file) return null;
  const raw = fs.readFileSync(file, 'utf8');
  const { data, content } = matter(raw);

  // Extract H2/H3 headings for the table of contents.
  const headings: DocPage['headings'] = [];
  for (const line of content.split('\n')) {
    const m = /^(#{2,3})\s+(.*)/.exec(line);
    if (m) {
      headings.push({
        depth: m[1].length,
        text: m[2].trim(),
        id: slugify(m[2]),
      });
    }
  }

  return {
    slug,
    title: (data.title as string) ?? slug,
    description: (data.description as string) ?? '',
    source: content,
    headings,
  };
}
