import Link from 'next/link';

export default function Breadcrumb({ slug }: { slug: string }) {
  const parts = slug.split('/');
  return (
    <p className="mb-4 font-heading text-xs text-muted">
      <Link href="/" className="hover:text-accent">
        ropesim
      </Link>
      {parts.map((part, i) => (
        <span key={i}>
          {' / '}
          {i === parts.length - 1 ? (
            <span className="text-accent">{part}</span>
          ) : (
            part
          )}
        </span>
      ))}
    </p>
  );
}
