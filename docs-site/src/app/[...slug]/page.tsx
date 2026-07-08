// Dynamic route for every doc page: three-column layout
// (sidebar | MDX content | table of contents).

import { notFound } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import TableOfContents from '@/components/layout/TableOfContents';
import Breadcrumb from '@/components/docs/Breadcrumb';
import MDXContent from '@/components/docs/MDXContent';
import ApiReference from '@/components/docs/ApiReference';
import { allSlugs } from '@/lib/nav';
import { loadDoc } from '@/lib/mdx';

export function generateStaticParams() {
  return allSlugs.map((slug) => ({ slug: slug.split('/') }));
}

export const dynamicParams = false;

export function generateMetadata({ params }: { params: { slug: string[] } }) {
  const doc = loadDoc(params.slug.join('/'));
  return { title: doc?.title ?? 'docs', description: doc?.description };
}

export default function DocPage({ params }: { params: { slug: string[] } }) {
  const slug = params.slug.join('/');
  const doc = loadDoc(slug);
  if (!doc) notFound();

  const isGeneratedReference = slug === 'api/reference';

  return (
    <div className="mx-auto flex max-w-7xl gap-10 px-4">
      <Sidebar />
      <article className="min-w-0 flex-1 py-10" data-pagefind-body>
        <Breadcrumb slug={slug} />
        <h1 className="mb-1 text-3xl">{doc.title}</h1>
        {doc.description && (
          <p className="mb-8 text-muted">{doc.description}</p>
        )}
        <MDXContent source={doc.source} />
        {isGeneratedReference && <ApiReference />}
      </article>
      <TableOfContents headings={doc.headings} />
    </div>
  );
}
