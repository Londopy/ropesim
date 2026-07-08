// Renders the auto-generated api-data.json (docstrings extracted from the
// installed ropesim package by scripts/generate-api-docs.py).

import { loadApiData, type ApiFunction } from '@/lib/api-docs';
import CodeBlock from '@/components/docs/CodeBlock';

function FunctionBlock({ fn, prefix }: { fn: ApiFunction; prefix?: string }) {
  return (
    <div className="my-4 rounded-lg border border-line bg-surface p-4">
      <p className="font-code text-sm">
        {prefix && <span className="text-muted">{prefix}.</span>}
        <span className="text-accent">{fn.name}</span>
        <span className="text-muted">{fn.signature.replace(fn.name, '')}</span>
      </p>
      {fn.docstring && (
        <p className="mt-2 whitespace-pre-line text-sm text-body">
          {fn.docstring}
        </p>
      )}
      {fn.params.length > 0 && (
        <table className="mt-3 w-full text-xs">
          <tbody>
            {fn.params.map((p) => (
              <tr key={p.name} className="border-t border-line/40">
                <td className="py-1 pr-3 font-code text-accent">{p.name}</td>
                <td className="py-1 pr-3 font-code text-muted">{p.type}</td>
                <td className="py-1 text-body">{p.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {fn.example && <CodeBlock code={fn.example} lang="python" />}
    </div>
  );
}

export default function ApiReference() {
  const data = loadApiData();

  if (data.modules.length === 0) {
    return (
      <div className="rounded-lg border border-warning/40 bg-raised p-4 text-sm">
        <p className="font-heading text-warning">api-data.json not generated</p>
        <p className="mt-1 text-muted">
          Run <code>python scripts/generate-api-docs.py</code> with ropesim
          installed, then rebuild the site.
        </p>
      </div>
    );
  }

  return (
    <div>
      <p className="font-heading text-xs text-muted">
        generated {data.generated} · ropesim {data.version}
      </p>
      {data.modules.map((mod) => (
        <section key={mod.name} className="mt-8">
          <h2 id={mod.name.replace(/\./g, '-')} className="scroll-mt-20">
            {mod.name}
          </h2>
          {mod.docstring && (
            <p className="text-sm text-muted">{mod.docstring}</p>
          )}
          {mod.classes.map((cls) => (
            <div key={cls.name} className="mt-6">
              <h3
                id={`${mod.name}-${cls.name}`.replace(/\./g, '-')}
                className="font-code scroll-mt-20"
              >
                class {cls.name}
              </h3>
              {cls.docstring && (
                <p className="whitespace-pre-line text-sm text-body">
                  {cls.docstring}
                </p>
              )}
              {cls.methods.map((m) => (
                <FunctionBlock key={m.name} fn={m} prefix={cls.name} />
              ))}
            </div>
          ))}
          {mod.functions.map((fn) => (
            <FunctionBlock key={fn.name} fn={fn} />
          ))}
        </section>
      ))}
    </div>
  );
}
