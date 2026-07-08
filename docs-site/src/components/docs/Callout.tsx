const styles = {
  info: {
    border: 'border-accent-dim',
    label: 'text-accent',
    icon: '▲',
    title: 'note',
  },
  warning: {
    border: 'border-warning',
    label: 'text-warning',
    icon: '◮',
    title: 'careful',
  },
  danger: {
    border: 'border-danger',
    label: 'text-danger',
    icon: '⚠',
    title: 'danger',
  },
} as const;

export default function Callout({
  type = 'info',
  title,
  children,
}: {
  type?: keyof typeof styles;
  title?: string;
  children: React.ReactNode;
}) {
  const s = styles[type];
  return (
    <div className={`my-5 rounded-r-lg border-l-2 ${s.border} bg-raised px-4 py-3`}>
      <p className={`mb-1 font-heading text-xs uppercase tracking-widest ${s.label}`}>
        {s.icon} {title ?? s.title}
      </p>
      <div className="text-sm leading-relaxed [&>p]:m-0">{children}</div>
    </div>
  );
}
