export default function ApiMethod({
  name,
  sig,
  returns,
  children,
}: {
  name: string;
  sig: string;
  returns?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="my-5 rounded-lg border border-line bg-surface p-4">
      <p className="font-code text-sm">
        <span className="text-accent">{name}</span>
        <span className="text-muted">{sig}</span>
        {returns && (
          <>
            <span className="text-muted"> → </span>
            <span className="text-bright">{returns}</span>
          </>
        )}
      </p>
      {children && (
        <div className="mt-2 text-sm text-body [&>p]:my-1">{children}</div>
      )}
    </div>
  );
}
