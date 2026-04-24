"""
ropesim.gui.style
=================
Global dark theme stylesheet and colour palette.
"""
from __future__ import annotations

# ── Palette ────────────────────────────────────────────────────────────────────
DARK_BG        = "#1e1e2e"   # main background
PANEL_BG       = "#252535"   # side panel background
SURFACE        = "#2a2a3e"   # card / widget surface
BORDER         = "#3a3a5a"   # borders / separators
TEXT_PRIMARY   = "#cdd6f4"   # primary text
TEXT_SECONDARY = "#9399b2"   # secondary / hint text
ACCENT         = "#89b4fa"   # interactive accent (blue)
ACCENT_HOVER   = "#b4d0fc"
SUCCESS        = "#a6e3a1"   # green — safe / passing
WARNING        = "#f9e2af"   # yellow — caution
DANGER         = "#f38ba8"   # red — failure / over limit

# Route canvas
CANVAS_BG      = "#13131f"
ROCK_WALL_TOP  = "#2a2030"
ROCK_WALL_BOT  = "#1a1025"
ROPE_COLOR     = "#fab387"   # orange rope
ROPE_WIDTH     = 3
BOLT_COLOR     = "#89dceb"   # cyan
CAM_COLOR      = "#a6e3a1"   # green
NUT_COLOR      = "#f9e2af"   # yellow
CLIMBER_COLOR  = "#cba6f7"   # purple
FORCE_COLOR    = "#f38ba8"   # red force arrows
ANCHOR_COLOR   = "#89b4fa"   # blue belay anchor
WALL_COLOR     = "#2a2030"   # alias for canvas rock face

STYLESHEET = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "SF Pro Display", "Inter", sans-serif;
    font-size: 13px;
}}

QSplitter::handle {{
    background-color: {BORDER};
    width: 2px;
    height: 2px;
}}

QMenuBar {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    padding: 2px;
}}
QMenuBar::item:selected {{
    background-color: {SURFACE};
}}
QMenu {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
}}
QMenu::item:selected {{
    background-color: {ACCENT};
    color: {DARK_BG};
}}

QToolBar {{
    background-color: {PANEL_BG};
    border-bottom: 1px solid {BORDER};
    spacing: 4px;
    padding: 4px;
}}
QToolButton {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
}}
QToolButton:hover {{
    background-color: {SURFACE};
    border-color: {BORDER};
}}
QToolButton:pressed {{
    background-color: {ACCENT};
    color: {DARK_BG};
}}

QStatusBar {{
    background-color: {PANEL_BG};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
}}

QScrollArea, QScrollBar {{
    background-color: {DARK_BG};
}}
QScrollBar:vertical {{
    width: 8px;
    background: {DARK_BG};
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 8px;
    color: {TEXT_SECONDARY};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}

QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}
QLabel[secondary="true"] {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
}}

QComboBox {{
    background-color: {SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 24px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
    selection-color: {DARK_BG};
    border: 1px solid {BORDER};
}}

QDoubleSpinBox, QSpinBox {{
    background-color: {SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 24px;
}}
QDoubleSpinBox:hover, QSpinBox:hover {{ border-color: {ACCENT}; }}
QDoubleSpinBox::up-button, QSpinBox::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    background: {BORDER};
    border: none;
    width: 18px;
}}

QLineEdit {{
    background-color: {SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 24px;
}}
QLineEdit:hover {{ border-color: {ACCENT}; }}
QLineEdit:focus {{ border-color: {ACCENT}; }}

QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background: {SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QPushButton {{
    background-color: {SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: {ACCENT};
    color: {DARK_BG};
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: {ACCENT_HOVER};
    color: {DARK_BG};
}}
QPushButton#runButton {{
    background-color: {ACCENT};
    color: {DARK_BG};
    font-weight: bold;
    font-size: 14px;
}}
QPushButton#runButton:hover {{
    background-color: {ACCENT_HOVER};
}}

QFrame#separator {{
    background-color: {BORDER};
    max-height: 1px;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-top: none;
}}
QTabBar::tab {{
    background: {SURFACE};
    color: {TEXT_SECONDARY};
    padding: 6px 16px;
    border: 1px solid {BORDER};
    border-bottom: none;
}}
QTabBar::tab:selected {{
    background: {PANEL_BG};
    color: {TEXT_PRIMARY};
}}

QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {SURFACE};
    text-align: center;
    color: {TEXT_PRIMARY};
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}
"""


def severity_color(value: float, safe_threshold: float, warn_threshold: float) -> str:
    """Return a hex color based on how close `value` is to the threshold."""
    if value <= safe_threshold:
        return SUCCESS
    if value <= warn_threshold:
        return WARNING
    return DANGER


def force_color(peak_kn: float, limit_kn: float = 12.0) -> str:
    ratio = peak_kn / limit_kn
    if ratio < 0.60:
        return SUCCESS
    if ratio < 0.85:
        return WARNING
    return DANGER
