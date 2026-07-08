export interface ParamRow {
  name: string;
  type: string;
  description: string;
  default?: string;
}

export default function ParamTable({ params }: { params: ParamRow[] }) {
  return (
    <div className="my-5 overflow-x-auto rounded-lg border border-line">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-raised font-heading text-xs text-muted">
            <th className="px-3 py-2 text-left font-medium">parameter</th>
            <th className="px-3 py-2 text-left font-medium">type</th>
            <th className="px-3 py-2 text-left font-medium">default</th>
            <th className="px-3 py-2 text-left font-medium">description</th>
          </tr>
        </thead>
        <tbody>
          {params.map((p) => (
            <tr key={p.name} className="border-t border-line/50">
              <td className="px-3 py-2 font-code text-accent">{p.name}</td>
              <td className="px-3 py-2 font-code text-xs text-muted">{p.type}</td>
              <td className="px-3 py-2 font-code text-xs text-muted">
                {p.default ?? '—'}
              </td>
              <td className="px-3 py-2 text-body">{p.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
