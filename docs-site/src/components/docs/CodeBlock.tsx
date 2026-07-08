// Server component: Shiki-highlighted code block with copy button.

import { codeToHtml } from 'shiki';
import CopyButton from '@/components/shared/CopyButton';

export default async function CodeBlock({
  code,
  lang = 'python',
  title,
}: {
  code: string;
  lang?: string;
  title?: string;
}) {
  const html = await codeToHtml(code.trim(), {
    lang,
    theme: 'vitesse-dark',
  });

  return (
    <div className="group relative my-5 overflow-hidden rounded-lg border border-line">
      {title && (
        <div className="flex items-center justify-between border-b border-line bg-raised px-4 py-1.5 font-heading text-xs text-muted">
          {title}
          <CopyButton text={code.trim()} />
        </div>
      )}
      {!title && (
        <div className="absolute right-2 top-2 opacity-0 transition-opacity group-hover:opacity-100">
          <CopyButton text={code.trim()} />
        </div>
      )}
      <div
        className="[&_pre]:!m-0 [&_pre]:!rounded-none [&_pre]:!border-0"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
