#!/usr/bin/env python3
"""Extract docstrings and signatures from the ropesim package into
data/api-data.json, consumed by src/components/docs/ApiReference.tsx.

Run with ropesim importable (pip install -e . or maturin develop):

    python docs-site/scripts/generate-api-docs.py

Update a docstring in Python -> re-run this script -> commit api-data.json
-> the site rebuilds with updated docs. No manual HTML editing.
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

PUBLIC_MODULES = [
    "ropesim.rope",
    "ropesim.fall",
    "ropesim.anchor",
    "ropesim.simulate",
    "ropesim.physics_v3",
    "ropesim.replay",
    "ropesim.units",
    "ropesim.standards",
    "ropesim.viz",
]

PARAM_RE = re.compile(r"^\s*(\w+)\s*(?:\(([^)]*)\)|--|:)?\s*[-—:]*\s*(.*)$")


def parse_docstring(doc: str | None) -> tuple[str, list[dict], str]:
    """Split a docstring into (summary, params, example)."""
    if not doc:
        return "", [], ""
    doc = inspect.cleandoc(doc)

    example = ""
    if ">>>" in doc:
        idx = doc.index(">>>")
        example = doc[idx:].strip()
        doc = doc[:idx]

    params: list[dict] = []
    lines = doc.split("\n")
    body: list[str] = []
    in_params = False
    for line in lines:
        lower = line.strip().lower()
        if lower.startswith(("args:", "arguments:", "parameters", "params:")):
            in_params = True
            continue
        if in_params:
            if lower.startswith(("returns", "raises", "yields", "example", "note")):
                in_params = False
                body.append(line)
                continue
            m = re.match(r"^\s+(\*{0,2}\w+)\s*(?:\(([^)]*)\))?\s*[:—-]\s*(.*)$", line)
            if m:
                params.append(
                    {
                        "name": m.group(1),
                        "type": m.group(2) or "",
                        "description": m.group(3).strip(),
                    }
                )
                continue
            if line.strip() and params:
                params[-1]["description"] += " " + line.strip()
                continue
        body.append(line)

    # `param -- description` (Sphinx-lite style used in ropesim docstrings)
    for line in lines:
        m = re.match(r"^\s*\*?\s*``?(\w+)``?\s+--\s+(.*)$", line)
        if m and not any(p["name"] == m.group(1) for p in params):
            params.append(
                {"name": m.group(1), "type": "", "description": m.group(2).strip()}
            )

    return "\n".join(body).strip(), params, example


def describe_function(name: str, obj) -> dict | None:
    try:
        sig = str(inspect.signature(obj))
    except (ValueError, TypeError):
        sig = "(…)"
    doc, params, example = parse_docstring(inspect.getdoc(obj))
    returns = ""
    m = re.search(r"->\s*(.+)$", sig)
    if m:
        returns = m.group(1).strip()
        sig = sig[: m.start()].strip()
    # Signature params not documented in the docstring still get a row.
    try:
        for pname, p in inspect.signature(obj).parameters.items():
            if pname in ("self", "cls"):
                continue
            if not any(x["name"].lstrip("*") == pname for x in params):
                ptype = (
                    "" if p.annotation is inspect.Parameter.empty
                    else str(p.annotation).replace("typing.", "")
                )
                default = (
                    None if p.default is inspect.Parameter.empty else repr(p.default)
                )
                params.append(
                    {
                        "name": pname,
                        "type": ptype,
                        "description": f"default {default}" if default else "",
                    }
                )
    except (ValueError, TypeError):
        pass
    return {
        "name": name,
        "signature": f"{name}{sig}",
        "params": params,
        "returns": returns,
        "docstring": doc,
        "example": example,
    }


def describe_module(modname: str) -> dict | None:
    try:
        mod = importlib.import_module(modname)
    except Exception as exc:  # noqa: BLE001 — record and continue
        print(f"  ! skipping {modname}: {exc}")
        return None

    classes, functions = [], []
    for name, obj in sorted(vars(mod).items()):
        if name.startswith("_") or getattr(obj, "__module__", None) != modname:
            continue
        if inspect.isclass(obj):
            methods = []
            for mname, meth in sorted(vars(obj).items()):
                if mname.startswith("_"):
                    continue
                target = None
                if inspect.isfunction(meth):
                    target = meth
                elif isinstance(meth, (classmethod, staticmethod)):
                    target = meth.__func__
                elif isinstance(meth, property) and meth.fget:
                    target = meth.fget
                if target is None:
                    continue
                d = describe_function(mname, target)
                if d:
                    methods.append(d)
            classes.append(
                {
                    "name": name,
                    "docstring": (inspect.getdoc(obj) or "").strip(),
                    "methods": methods,
                }
            )
        elif inspect.isfunction(obj):
            d = describe_function(name, obj)
            if d:
                functions.append(d)

    return {
        "name": modname,
        "docstring": (inspect.getdoc(mod) or "").split("\n\n")[0].strip(),
        "classes": classes,
        "functions": functions,
    }


def main() -> int:
    modules = [m for m in (describe_module(n) for n in PUBLIC_MODULES) if m]
    try:
        version = importlib.import_module("ropesim").__version__
    except Exception:  # noqa: BLE001
        version = "dev"

    out = {
        "generated": date.today().isoformat(),
        "version": version,
        "modules": modules,
    }
    out_path = Path(__file__).resolve().parents[1] / "data" / "api-data.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    n_items = sum(len(m["classes"]) + len(m["functions"]) for m in modules)
    print(f"wrote {out_path} — {len(modules)} modules, {n_items} documented items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
