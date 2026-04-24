"""RopeEditorDialog — create or edit a RopeSpec and persist it to ropes.json."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QGroupBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QSpinBox, QVBoxLayout, QWidget,
)

from ropesim.rope import RopeDatabase, RopeSpec, RopeType, RopeStandard

_DEFAULT_DB = Path(__file__).resolve().parent.parent.parent.parent / "ropes.json"


class RopeEditorDialog(QDialog):
    """Full form for editing or creating a RopeSpec."""

    def __init__(
        self,
        rope_name: str | None = None,
        db_path: Path | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._db_path = db_path or _DEFAULT_DB
        self._original_name = rope_name
        self.setWindowTitle(
            "New Rope" if rope_name is None else f"Edit Rope — {rope_name}"
        )
        self.setMinimumWidth(440)
        self._build_ui()
        if rope_name is not None:
            self._load_rope(rope_name)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Identity ──────────────────────────────────────────────────────────
        id_grp = QGroupBox("Identity")
        id_form = QFormLayout(id_grp)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Mammut Infinity 9.5")
        id_form.addRow("Name *:", self._name_edit)

        self._mfr_edit = QLineEdit()
        id_form.addRow("Manufacturer:", self._mfr_edit)

        self._type_combo = QComboBox()
        for rt in RopeType:
            self._type_combo.addItem(rt.value, rt)
        id_form.addRow("Type:", self._type_combo)

        self._std_combo = QComboBox()
        for rs in RopeStandard:
            self._std_combo.addItem(rs.value, rs)
        id_form.addRow("Standard:", self._std_combo)

        self._diameter_spin = QDoubleSpinBox()
        self._diameter_spin.setRange(6.0, 12.0)
        self._diameter_spin.setValue(9.5)
        self._diameter_spin.setSuffix(" mm")
        self._diameter_spin.setSingleStep(0.1)
        self._diameter_spin.setDecimals(1)
        id_form.addRow("Diameter:", self._diameter_spin)

        self._weight_spin = QDoubleSpinBox()
        self._weight_spin.setRange(30.0, 130.0)
        self._weight_spin.setValue(62.0)
        self._weight_spin.setSuffix(" g/m")
        self._weight_spin.setSingleStep(0.5)
        self._weight_spin.setDecimals(1)
        id_form.addRow("Weight:", self._weight_spin)

        self._sheath_spin = QDoubleSpinBox()
        self._sheath_spin.setRange(0.0, 60.0)
        self._sheath_spin.setValue(40.0)
        self._sheath_spin.setSuffix(" %")
        self._sheath_spin.setSingleStep(1.0)
        id_form.addRow("Sheath %:", self._sheath_spin)

        self._length_spin = QDoubleSpinBox()
        self._length_spin.setRange(30.0, 100.0)
        self._length_spin.setValue(60.0)
        self._length_spin.setSuffix(" m")
        self._length_spin.setSingleStep(5.0)
        id_form.addRow("Length:", self._length_spin)

        self._dry_check = QCheckBox("Dry treated")
        id_form.addRow("", self._dry_check)

        layout.addWidget(id_grp)

        # ── EN 892 Performance ────────────────────────────────────────────────
        en_grp = QGroupBox("EN 892 / UIAA Performance")
        en_form = QFormLayout(en_grp)

        self._impact_spin = QDoubleSpinBox()
        self._impact_spin.setRange(1.0, 15.0)
        self._impact_spin.setValue(9.0)
        self._impact_spin.setSuffix(" kN")
        self._impact_spin.setSingleStep(0.1)
        self._impact_spin.setDecimals(2)
        en_form.addRow("Impact force:", self._impact_spin)

        self._falls_spin = QSpinBox()
        self._falls_spin.setRange(1, 50)
        self._falls_spin.setValue(7)
        en_form.addRow("Number of falls:", self._falls_spin)

        self._static_elong_spin = QDoubleSpinBox()
        self._static_elong_spin.setRange(0.0, 30.0)
        self._static_elong_spin.setValue(8.5)
        self._static_elong_spin.setSuffix(" %")
        self._static_elong_spin.setSingleStep(0.5)
        en_form.addRow("Static elongation:", self._static_elong_spin)

        self._dynamic_elong_spin = QDoubleSpinBox()
        self._dynamic_elong_spin.setRange(0.0, 60.0)
        self._dynamic_elong_spin.setValue(34.0)
        self._dynamic_elong_spin.setSuffix(" %")
        self._dynamic_elong_spin.setSingleStep(0.5)
        en_form.addRow("Dynamic elongation:", self._dynamic_elong_spin)

        layout.addWidget(en_grp)

        # ── Buttons ───────────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── load / save ──────────────────────────────────────────────────────────

    def _load_rope(self, name: str) -> None:
        try:
            spec = RopeDatabase(self._db_path).get(name)
        except Exception:  # noqa: BLE001
            return
        if spec is None:
            return
        self._name_edit.setText(spec.name)
        self._mfr_edit.setText(spec.manufacturer or "")
        idx = self._type_combo.findData(spec.rope_type)
        if idx >= 0:
            self._type_combo.setCurrentIndex(idx)
        idx = self._std_combo.findData(spec.standard)
        if idx >= 0:
            self._std_combo.setCurrentIndex(idx)
        self._diameter_spin.setValue(spec.diameter_mm)
        self._weight_spin.setValue(spec.weight_gpm)
        self._sheath_spin.setValue(spec.sheath_percentage)
        self._length_spin.setValue(spec.length_m)
        self._dry_check.setChecked(spec.dry_treated)
        self._impact_spin.setValue(spec.impact_force_kn)
        self._falls_spin.setValue(spec.number_of_falls)
        self._static_elong_spin.setValue(spec.static_elongation_pct)
        self._dynamic_elong_spin.setValue(spec.dynamic_elongation_pct)

    def _on_save(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        static_e = self._static_elong_spin.value()
        dynamic_e = self._dynamic_elong_spin.value()
        if dynamic_e < static_e:
            QMessageBox.warning(
                self, "Validation",
                "Dynamic elongation must be ≥ static elongation."
            )
            return
        try:
            spec = RopeSpec(
                name=name,
                manufacturer=self._mfr_edit.text().strip(),
                rope_type=self._type_combo.currentData(),
                standard=self._std_combo.currentData(),
                diameter_mm=self._diameter_spin.value(),
                weight_gpm=self._weight_spin.value(),
                sheath_percentage=self._sheath_spin.value(),
                length_m=self._length_spin.value(),
                dry_treated=self._dry_check.isChecked(),
                impact_force_kn=self._impact_spin.value(),
                number_of_falls=self._falls_spin.value(),
                static_elongation_pct=static_e,
                dynamic_elongation_pct=dynamic_e,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Validation Error", str(exc))
            return
        try:
            self._save_to_db(spec)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save Error", str(exc))
            return
        self.accept()

    def _save_to_db(self, spec: RopeSpec) -> None:
        db_path = self._db_path
        if db_path.exists():
            raw = json.loads(db_path.read_text(encoding="utf-8"))
        else:
            raw = {"ropes": []}
        ropes: list[dict] = raw.get("ropes", [])
        ropes = [
            r for r in ropes
            if r.get("name") != spec.name and r.get("name") != self._original_name
        ]
        ropes.append(spec.model_dump())
        raw["ropes"] = ropes
        db_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    # ── public ────────────────────────────────────────────────────────────────

    def saved_name(self) -> str:
        return self._name_edit.text().strip()
