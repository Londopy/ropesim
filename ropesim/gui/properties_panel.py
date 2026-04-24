"""PropertiesPanel — left panel: rope/climber settings and simulation controls."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QProgressBar, QPushButton, QSizePolicy, QSpinBox,
    QVBoxLayout, QWidget,
)

from ropesim.gui.style import ACCENT, DANGER, SUCCESS, WARNING


class PropertiesPanel(QWidget):
    """Left panel with rope selector, climber settings, and Run button."""

    # Emitted by user actions
    rope_changed        = Signal(str)          # rope name
    climber_changed     = Signal(float, float) # mass_kg, height_m
    run_requested       = Signal()
    sweep_requested     = Signal()
    zipper_requested    = Signal()
    add_bolt_requested  = Signal()
    add_cam_requested   = Signal()
    add_nut_requested   = Signal()
    edit_rope_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumWidth(220)
        self.setMaximumWidth(300)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        root.addWidget(self._rope_group())
        root.addWidget(self._climber_group())
        root.addWidget(self._gear_group())
        root.addWidget(self._sim_group())
        root.addStretch()

    def _rope_group(self) -> QGroupBox:
        grp = QGroupBox("Rope")
        layout = QVBoxLayout(grp)
        layout.setSpacing(6)

        self._rope_combo = QComboBox()
        self._rope_combo.setPlaceholderText("Select rope…")
        self._rope_combo.currentTextChanged.connect(self.rope_changed)
        layout.addWidget(self._rope_combo)

        edit_btn = QPushButton("Edit / Add Rope…")
        edit_btn.clicked.connect(self.edit_rope_requested)
        layout.addWidget(edit_btn)

        return grp

    def _climber_group(self) -> QGroupBox:
        grp = QGroupBox("Climber")
        form = QFormLayout(grp)
        form.setSpacing(6)

        self._mass_spin = QDoubleSpinBox()
        self._mass_spin.setRange(40.0, 200.0)
        self._mass_spin.setValue(80.0)
        self._mass_spin.setSuffix(" kg")
        self._mass_spin.setSingleStep(1.0)
        self._mass_spin.valueChanged.connect(self._emit_climber)
        form.addRow("Mass:", self._mass_spin)

        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(0.0, 60.0)
        self._height_spin.setValue(5.0)
        self._height_spin.setSuffix(" m")
        self._height_spin.setSingleStep(0.5)
        self._height_spin.valueChanged.connect(self._emit_climber)
        form.addRow("Height:", self._height_spin)

        return grp

    def _gear_group(self) -> QGroupBox:
        grp = QGroupBox("Add Protection")
        layout = QVBoxLayout(grp)
        layout.setSpacing(6)

        bolt_btn = QPushButton("+ Bolt")
        cam_btn  = QPushButton("+ Cam")
        nut_btn  = QPushButton("+ Nut")
        bolt_btn.clicked.connect(self.add_bolt_requested)
        cam_btn.clicked.connect(self.add_cam_requested)
        nut_btn.clicked.connect(self.add_nut_requested)

        layout.addWidget(bolt_btn)
        layout.addWidget(cam_btn)
        layout.addWidget(nut_btn)

        return grp

    def _sim_group(self) -> QGroupBox:
        grp = QGroupBox("Simulation")
        layout = QVBoxLayout(grp)
        layout.setSpacing(6)

        self._sweep_steps_spin = QSpinBox()
        self._sweep_steps_spin.setRange(5, 200)
        self._sweep_steps_spin.setValue(40)
        self._sweep_steps_spin.setPrefix("steps: ")
        layout.addWidget(self._sweep_steps_spin)

        run_btn = QPushButton("▶  Run Fall Simulation")
        run_btn.setStyleSheet(f"background-color: {ACCENT}; font-weight: bold;")
        run_btn.clicked.connect(self.run_requested)
        layout.addWidget(run_btn)

        sweep_btn = QPushButton("⟳  Sweep All Positions")
        sweep_btn.clicked.connect(self.sweep_requested)
        layout.addWidget(sweep_btn)

        zipper_btn = QPushButton("↓  Zipper Analysis")
        zipper_btn.clicked.connect(self.zipper_requested)
        layout.addWidget(zipper_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("Ready")
        self._status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_label)

        return grp

    # ── public API ───────────────────────────────────────────────────────────

    def set_rope_names(self, names: list[str]) -> None:
        self._rope_combo.blockSignals(True)
        current = self._rope_combo.currentText()
        self._rope_combo.clear()
        self._rope_combo.addItems(names)
        idx = self._rope_combo.findText(current)
        self._rope_combo.setCurrentIndex(max(0, idx))
        self._rope_combo.blockSignals(False)

    def current_rope_name(self) -> str:
        return self._rope_combo.currentText()

    def climber_mass_kg(self) -> float:
        return self._mass_spin.value()

    def climber_height_m(self) -> float:
        return self._height_spin.value()

    def sweep_steps(self) -> int:
        return self._sweep_steps_spin.value()

    def set_progress(self, value: int) -> None:
        self._progress.setVisible(value > 0)
        self._progress.setValue(value)

    def set_status(self, msg: str, level: str = "info") -> None:
        """level: 'info' | 'success' | 'warning' | 'danger'"""
        color_map = {
            "info":    "",
            "success": SUCCESS,
            "warning": WARNING,
            "danger":  DANGER,
        }
        color = color_map.get(level, "")
        if color:
            self._status_label.setStyleSheet(f"color: {color};")
        else:
            self._status_label.setStyleSheet("")
        self._status_label.setText(msg)

    def set_busy(self, busy: bool) -> None:
        self._progress.setVisible(busy)
        if busy:
            self._progress.setRange(0, 0)  # indeterminate
        else:
            self._progress.setRange(0, 100)
            self._progress.setValue(0)

    # ── private ──────────────────────────────────────────────────────────────

    def _emit_climber(self) -> None:
        self.climber_changed.emit(self._mass_spin.value(), self._height_spin.value())
