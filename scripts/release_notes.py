#!/usr/bin/env python3
"""Generate a GitHub Release body for a given version.

Reads the project CHANGELOG.md with the `patchnotes` library
(https://pypi.org/project/patchnotes/) — the same Keep a Changelog parser the
project standardises on — pulls out the requested version's section, and wraps
it with a project blurb, install instructions, and (optionally) a checksum
table read from a SHA256SUMS.txt file.

Usage:
    python scripts/release_notes.py 3.0.0 \
        [--changelog CHANGELOG.md] \
        [--sha256 SHA256SUMS.txt] \
        [--output NOTES.md]

Requires:  pip install patchnotes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import patchnotes
except ImportError:
    sys.exit("release_notes.py needs the 'patchnotes' package:  pip install patchnotes")

REPO = "Londopy/ropesim"

BLURB = """\
**Climbing rope physics engine — Python library, CLI, TUI, and a native 3D desktop app.**

ropesim models lead-fall dynamics with a UIAA 101 / EN 892 impact-force model and
RK4 damped-spring integration in a Rust core (optional Rapier3D full-physics mode).
One engine, four frontends: a pip-installable Python library, a 20+ command CLI, a
Textual terminal UI, and a native C++ / Qt6 desktop application with a 60 fps OpenGL
rope renderer."""

INSTALL = f"""\
### Install

**Python library / CLI / TUI** (all platforms, Python 3.10–3.12):
```bash
pip install ropesim          # library + CLI
pip install "ropesim[tui]"   # + terminal UI
```

**Desktop app** (no Python required) — download an asset below and run:
- **Windows** — unzip `ropesim-gui-windows-x64.zip`, run `ropesim-gui.exe`
- **macOS** — open `ropesim-gui-macos.dmg` (unsigned: right-click → Open the first time)
- **Linux** — `chmod +x ropesim-gui-linux-x86_64.AppImage && ./ropesim-gui-linux-x86_64.AppImage`"""

SAFETY = (
    "⚠️ *ropesim informs judgement — it is for education and planning, never a "
    "substitute for testing, redundancy, and experience at the crag.*"
)


def changelog_section(changelog_path: Path, version: str) -> str:
    """Return the requested version's changes, grouped by type, as markdown."""
    cl = patchnotes.parse_file(str(changelog_path))
    release = cl.get_version(version)
    if release is None:
        available = ", ".join(r.version for r in cl.releases)
        sys.exit(f"version {version!r} not found in {changelog_path} (have: {available})")

    lines: list[str] = []
    date = f" — {release.release_date}" if release.release_date else ""
    lines.append(f"## ropesim {release.version}{date}\n")
    lines.append(BLURB + "\n")

    # `by_type` groups entries under Added / Changed / Fixed / Removed / etc.
    for change_type, entries in release.by_type.items():
        if not entries:
            continue
        lines.append(f"### {change_type}")
        for entry in entries:
            lines.append(f"- {entry.text}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def checksum_table(sha_path: Path) -> str:
    """Render a SHA256SUMS.txt as a verify section, GUI binaries first."""
    rows = []
    for line in sha_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, name = line.partition(" ")
        rows.append((name.strip(), digest))

    def is_gui(name: str) -> bool:
        return name.endswith((".zip", ".dmg", ".AppImage"))

    gui = [r for r in rows if is_gui(r[0])]
    wheels = sorted((r for r in rows if r[0].endswith(".whl")), key=lambda r: r[0])

    out = [
        "### Verify your download (SHA-256)",
        "",
        "```bash",
        "sha256sum -c SHA256SUMS.txt        # Linux",
        "shasum -a 256 -c SHA256SUMS.txt    # macOS",
        "```",
        "",
    ]
    if gui:
        out.append("**Desktop apps**")
        for name, digest in gui:
            out.append(f"- `{name}`\n  `{digest}`")
        out.append("")
    if wheels:
        out.append("**Python wheels**")
        for name, digest in wheels:
            out.append(f"- `{name}`\n  `{digest}`")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def build(version: str, changelog: Path, sha256: Path | None) -> str:
    parts = [changelog_section(changelog, version), "---\n", INSTALL, "\n---\n"]
    if sha256 and sha256.exists():
        parts.append(checksum_table(sha256))
        parts.append("---\n")
    parts.append(SAFETY + "\n")
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("version", help="version to render, e.g. 3.0.0")
    ap.add_argument("--changelog", default="CHANGELOG.md", type=Path)
    ap.add_argument("--sha256", type=Path, help="optional SHA256SUMS.txt to embed")
    ap.add_argument("--output", type=Path, help="write here instead of stdout")
    args = ap.parse_args()

    body = build(args.version, args.changelog, args.sha256)
    if args.output:
        args.output.write_text(body)
        print(f"wrote {args.output} ({len(body.splitlines())} lines)", file=sys.stderr)
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
