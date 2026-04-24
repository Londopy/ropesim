"""Gear editor dialogs: BoltEditorDialog, CamEditorDialog, NutEditorDialog."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from ropesim.anchor import (
    Bolt, BoltType, Cam, CamPlacement, Nut, RockType,
)
from ropesim.gui.style import DANGER, SUCCESS, WARNING


# ── shared MBS preview label ──────────────────────────────────────────────────

class _MbsPreview(QLabel):
    def update_mbs(self, mbs_kn: float) -> None:
        if mbs_kn >= 20.0:
            color = SUCCESS
        elif mbs_kn >= 10.0:
            color = WARNING
        else:
            color = DANGER
        self.setText(f"Rated MBS: {mbs_kn:.1f} kN")
        self.setStyleSheet(f"font-weight: bold; color: {color};")


# ── BoltEditorDialog ──────────────────────────────────────────────────────────

class BoltEditorDialog(QDialog):
    """Create or edit a Bolt anchor."""

    def __init__(self, bolt: Bolt | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Bolt Editor")
        self.setMinimumWidth(360)
        self._build_ui()
        if bolt is not None:
            self._load(bolt)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        grp = QGroupBox("Bolt Properties")
        form = QFormLayout(grp)

        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("e.g. B1")
        form.addRow("Label:", self._label_edit)

        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(0.0, 60.0)
        self._height_spin.setValue(2.0)
        self._height_spin.setSuffix(" m")
        self._height_spin.setSingleStep(0.5)
        form.addRow("Height:", self._height_spin)

        self._mbs_spin = QDoubleSpinBox()
        self._mbs_spin.setRange(1.0, 50.0)
        self._mbs_spin.setValue(25.0)
        self._mbs_spin.setSuffix(" kN")
        self._mbs_spin.setSingleStep(0.5)
        self._mbs_spin.valueChanged.connect(self._on_mbs_changed)
        form.addRow("Rated MBS:", self._mbs_spin)

        self._type_combo = QComboBox()
        for bt in BoltType:
            self._type_combo.addItem(bt.value, bt)
        form.addRow("Bolt type:", self._type_combo)

        self._rock_combo = QComboBox()
        for rt in RockType:
            self._rock_combo.addItem(rt.value, rt)
        form.addRow("Rock type:", self._rock_combo)

        self._age_spin = QDoubleSpinBox()
        self._age_spin.setRange(0.0, 50.0)
        self._age_spin.setValue(0.0)
        self._age_spin.setSuffix(" years")
        self._age_spin.setSingleStep(1.0)
        form.addRow("Age:", self._age_spin)

        self._mbs_preview = _MbsPreview()
        self._mbs_preview.update_mbs(self._mbs_spin.value())
        form.addRow("", self._mbs_preview)

        layout.addWidget(grp)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load(self, bolt: Bolt) -> None:
        self._mbs_spin.setValue(bolt.rated_mbs_kn)
        idx = self._type_combo.findData(bolt.bolt_type)
        if idx >= 0:
            self._type_combo.setCurrentIndex(idx)
        idx = self._rock_combo.findData(bolt.rock_type)
        if idx >= 0:
            self._rock_combo.setCurrentIndex(idx)
        self._age_spin.setValue(bolt.age_years)

    def _on_mbs_changed(self, val: float) -> None:
        self._mbs_preview.update_mbs(val)

    def build_bolt(self) -> Bolt:
        return Bolt(
            rated_mbs_kn=self._mbs_spin.value(),
            bolt_type=self._type_combo.currentData(),
            rock_type=self._rock_combo.currentData(),
            age_years=self._age_spin.value(),
        )

    def height_m(self) -> float:
        return self._height_spin.value()

    def label(self) -> str:
        return self._label_edit.text().strip()


# ── CamEditorDialog ───────────────────────────────────────────────────────────

class CamEditorDialog(QDialog):
    """Create or edit a Cam anchor."""

    def __init__(self, cam: Cam | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Cam Editor")
        self.setMinimumWidth(360)
        self._build_ui()
        if cam is not None:
            self._load(cam)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        grp = QGroupBox("Cam Properties")
        form = QFormLayout(grp)

        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("e.g. C1")
        form.addRow("Label:", self._label_edit)

        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(0.0, 60.0)
        self._height_spin.setValue(3.0)
        self._height_spin.setSuffix(" m")
        self._height_spin.setSingleStep(0.5)
        form.addRow("Height:", self._height_spin)

        self._mbs_spin = QDoubleSpinBox()
        self._mbs_spin.setRange(1.0, 50.0)
        self._mbs_spin.setValue(14.0)
        self._mbs_spin.setSuffix(" kN")
        self._mbs_spin.setSingleStep(0.5)
        self._mbs_spin.valueChanged.connect(self._on_mbs_changed)
        form.addRow("Rated MBS:", self._mbs_spin)

        self._brand_edit = QLineEdit()
        self._brand_edit.setPlaceholderText("e.g. Black Diamond")
        form.addRow("Brand:", self._brand_edit)

        self._size_edit = QLineEdit()
        self._size_edit.setPlaceholderText("e.g. #2")
        form.addRow("Size:", self._size_edit)

        self._placement_combo = QComboBox()
        for cp in CamPlacement:
            self._placement_combo.addItem(cp.value, cp)
        # Default to GOOD
        idx = self._placement_combo.findData(CamPlacement.GOOD)
        if idx >= 0:
            self._placement_combo.setCurrentIndex(idx)
        form.addRow("Placement:", self._placement_combo)

        self._rock_combo = QComboBox()
        for rt in RockType:
            self._rock_combo.addItem(rt.value, rt)
        form.addRow("Rock type:", self._rock_combo)

        self._walking_spin = QDoubleSpinBox()
        self._walking_spin.setRange(0.0, 1.0)
        self._walking_spin.setValue(0.0)
        self._walking_spin.setSingleStep(0.1)
        self._walking_spin.setDecimals(2)
        form.addRow("Walking risk (0–1):", self._walking_spin)

        self._mbs_preview = _MbsPreview()
        self._mbs_preview.update_mbs(self._mbs_spin.value())
        form.addRow("", self._mbs_preview)

        layout.addWidget(grp)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load(self, cam: Cam) -> None:
        self._mbs_spin.setValue(cam.rated_mbs_kn)
        self._brand_edit.setText(cam.brand)
        self._size_edit.setText(cam.size)
        idx = self._placement_combo.findData(cam.placement)
        if idx >= 0:
            self._placement_combo.setCurrentIndex(idx)
        idx = self._rock_combo.findData(cam.rock_type)
        if idx >= 0:
            self._rock_combo.setCurrentIndex(idx)
        self._walking_spin.setValue(cam.walking_risk)

    def _on_mbs_changed(self, val: float) -> None:
        self._mbs_preview.update_mbs(val)

    def build_cam(self) -> Cam:
        return Cam(
            rated_mbs_kn=self._mbs_spin.value(),
            brand=self._brand_edit.text().strip(),
            size=self._size_edit.text().strip(),
            placement=self._placement_combo.currentData(),
            rock_type=self._rock_combo.currentData(),
            walking_risk=self._walking_spin.value(),
        )

    def height_m(self) -> float:
        return self._height_spin.value()

    def label(self) -> str:
        return self._label_edit.text().strip()


# ── NutEditorDialog ───────────────────────────────────────────────────────────

class NutEditorDialog(QDialog):
    """Create or edit a Nut anchor."""

    def __init__(self, nut: Nut | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Nut Editor")
        self.setMinimumWidth(360)
        self._build_ui()
        if nut is not None:
            self._load(nut)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        grp = QGroupBox("Nut Properties")
        form = QFormLayout(grp)

        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("e.g. N1")
        form.addRow("Label:", self._label_edit)

        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(0.0, 60.0)
        self._height_spin.setValue(2.5)
        self._height_spin.setSuffix(" m")
        self._height_spin.setSingleStep(0.5)
        form.addRow("Height:", self._height_spin)

        self._mbs_spin = QDoubleSpinBox()
        self._mbs_spin.setRange(1.0, 30.0)
        self._mbs_spin.setValue(12.0)
        self._mbs_spin.setSuffix(" kN")
        self._mbs_spin.setSingleStep(0.5)
        self._mbs_spin.valueChanged.connect(self._on_mbs_changed)
        form.addRow("Rated MBS:", self._mbs_spin)

        self._placement_combo = QComboBox()
        for cp in CamPlacement:
            self._placement_combo.addItem(cp.value, cp)
        idx = self._placement_combo.findData(CamPlacement.GOOD)
        if idx >= 0:
            self._placement_combo.setCurrentIndex(idx)
        form.addRow("Placement:", self._placement_combo)

        self._rock_combo = QComboBox()
        for rt in RockType:
            self._rock_combo.addItem(rt.value, rt)
        form.addRow("Rock type:", self._rock_combo)

        self._mbs_preview = _MbsPreview()
        self._mbs_preview.update_mbs(self._mbs_spin.value())
        form.addRow("", self._mbs_preview)

        layout.addWidget(grp)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load(self, nut: Nut) -> None:
        self._mbs_spin.setValue(nut.rated_mbs_kn)
        idx = self._placement_combo.findData(nut.placement)
        if idx >= 0:
            self._placement_combo.setCurrentIndex(idx)
        idx = self._rock_combo.findData(nut.rock_type)
        if idx >= 0:
            self._rock_combo.setCurrentIndex(idx)

    def _on_mbs_changed(self, val: float) -> None:
        self._mbs_preview.update_mbs(val)

    def build_nut(self) -> Nut:
        return Nut(
            rated_mbs_kn=self._mbs_spin.value(),
            placement=self._placement_combo.currentData(),
            rock_type=self._rock_combo.currentData(),
        )

    def height_m(self) -> float:
        return self._height_spin.value()

    def label(self) -> str:
        return self._label_edit.text().strip()
