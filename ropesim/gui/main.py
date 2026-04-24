"""QApplication entry point for the RopeSim GUI."""
from __future__ import annotations

import sys


def main() -> None:
    """Launch the RopeSim GUI application."""
    # Must import QApplication before anything else touches Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    # Enable High-DPI scaling (Qt6 does this automatically, but be explicit)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("RopeSim")
    app.setOrganizationName("ropesim")

    from ropesim.gui.main_window import MainWindow
    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
