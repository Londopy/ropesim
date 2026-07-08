// Renders MDX source (next-mdx-remote RSC) with the custom component set.

import { MDXRemote } from 'next-mdx-remote/rsc';
import CodeBlock from '@/components/docs/CodeBlock';
import Callout from '@/components/docs/Callout';
import Tabs from '@/components/docs/Tabs';
import ParamTable from '@/components/docs/ParamTable';
import ApiMethod from '@/components/docs/ApiMethod';
import { slugify } from '@/lib/mdx';

function heading(depth: 2 | 3) {
  const Tag = `h${depth}` as const;
  return function Heading({ children }: { children?: React.ReactNode }) {
    const text = typeof children === 'string' ? children : String(children);
    const id = slugify(text);
    return (
      <Tag id={id} className="group scroll-mt-20">
        {children}
        <a
          href={`#${id}`}
          className="ml-2 !no-underline opacity-0 transition-opacity group-hover:opacity-100"
          aria-label="Anchor link"
        >
          #
        </a>
      </Tag>
    );
  };
}

// fenced ```lang blocks → Shiki
async function Pre(props: React.HTMLAttributes<HTMLPreElement>) {
  const child = props.children as
    | { props?: { className?: string; children?: string } }
    | undefined;
  const className = child?.props?.className ?? '';
  const lang = className.replace('language-', '') || 'text';
  const code = child?.props?.children ?? '';
  return <CodeBlock code={String(code)} lang={lang} />;
}

const components = {
  Callout,
  Tabs,
  ParamTable,
  ApiMethod,
  CodeBlock,
  pre: Pre,
  h2: heading(2),
  h3: heading(3),
};

export default function MDXContent({ source }: { source: string }) {
  return (
    <div className="prose-docs">
      <MDXRemote source={source} components={components} />
    </div>
  );
}
