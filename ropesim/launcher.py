"""ropesim.launcher -- the `ropesim` console command (v3).

The v2 PySide6 GUI is replaced by the native C++ application, so the bare
``ropesim`` command now routes to the interfaces that live in this package:

    ropesim tui     full-screen terminal UI
    ropesim cli …   alias for ropesim-cli
    ropesim gui     where to get the native desktop app
"""

from __future__ import annotations

import sys

USAGE = """\
ropesim 3.x — climbing rope physics engine

usage:
  ropesim tui          launch the terminal UI
  ropesim cli [...]    run the CLI (same as `ropesim-cli`)
  ropesim gui          how to get the native desktop application

python API:            import ropesim
documentation:         https://londopy.github.io/ropesim/
"""

GUI_NOTE = """\
The v3 desktop app is a native application (no Python needed).

Download for Windows / macOS / Linux:
  https://github.com/Londopy/ropesim/releases

Build from source (Qt 6.6+, CMake 3.25+, Rust):
  see CONTRIBUTING.md → "C++ GUI"
"""


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0

    cmd, rest = args[0], args[1:]
    if cmd == "tui":
        from ropesim.tui import main as tui_main

        return tui_main()
    if cmd == "cli":
        from ropesim.cli_v2 import main as cli_main

        sys.argv = ["ropesim-cli", *rest]
        return cli_main()
    if cmd == "gui":
        print(GUI_NOTE)
        return 0

    print(f"unknown command: {cmd!r}\n\n{USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
