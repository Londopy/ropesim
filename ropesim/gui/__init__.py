"""ropesim.gui — PySide6 graphical interface for the RopeSim physics engine."""
from __future__ import annotations


def main() -> None:
    """Entry point registered in pyproject.toml as the ``ropesim`` command."""
    from ropesim.gui.main import main as _main
    _main()


__all__ = ["main"]
