# -*- coding: utf-8 -*-
"""MainWindow — three-panel QSplitter with menu/toolbar and live simulation."""
from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QMainWindow, QMessageBox,
    QSplitter, QStackedWidget, QStatusBar, QToolBar, QToolButton,
)

from ropesim.anchor import Bolt, Cam, Nut
from ropesim.gui.canvas import RouteCanvas
from ropesim.gui.models import GearItem, RouteModel
from ropesim.gui.properties_panel import PropertiesPanel
from ropesim.gui.results_panel import ResultsPanel
from ropesim.gui.style import STYLESHEET
from ropesim.gui.viewport3d import Viewport3D
from ropesim.gui.workers import SimulationWorker, SweepWorker, ZipperWorker


class MainWindow(QMainWindow):
    """Top-level window: left properties panel | centre canvas | right results."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RopeSim — Climbing Rope Physics Simulator")
        self.setMinimumSize(1200, 760)
        self.setStyleSheet(STYLESHEET)

        self._model   = RouteModel(self)
        self._worker: SimulationWorker | SweepWorker | ZipperWorker | None = None

        self._build_panels()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._connect_all()

        # Populate rope list after event loop starts (model may need DB)
        QTimer.singleShot(0, self._refresh_rope_list)

    # ── panel layout ─────────────────────────────────────────────────────────

    def _build_panels(self) -> None:
        self._props      = PropertiesPanel(self)
        self._canvas     = RouteCanvas(self)
        self._viewport3d = Viewport3D(self)
        self._results    = ResultsPanel(self)

        # Centre panel: QStackedWidget lets us flip between 2D canvas and 3D viewport
        self._centre_stack = QStackedWidget(self)
        self._centre_stack.addWidget(self._canvas)      # index 0 — 2D
        self._centre_stack.addWidget(self._viewport3d)  # index 1 — 3D
        self._centre_stack.setCurrentIndex(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._props)
        splitter.addWidget(self._centre_stack)
        splitter.addWidget(self._results)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([240, 700, 320])

        self.setCentralWidget(splitter)

    # ── menu bar ─────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # File
        file_m = mb.addMenu("&File")
        self._act_new        = QAction("&New Route",      self, shortcut=QKeySequence.New)
        self._act_export_pdf = QAction("Export &PDF…",    self)
        self._act_export_csv = QAction("Export &CSV…",    self)
        self._act_quit       = QAction("&Quit",           self, shortcut=QKeySequence.Quit)

        file_m.addAction(self._act_new)
        file_m.addSeparator()
        file_m.addAction(self._act_export_pdf)
        file_m.addAction(self._act_export_csv)
        file_m.addSeparator()
        file_m.addAction(self._act_quit)

        self._act_quit.triggered.connect(self.close)
        self._act_new.triggered.connect(self._on_new_route)
        self._act_export_pdf.triggered.connect(self._export_pdf)
        self._act_export_csv.triggered.connect(self._export_csv)

        # Route
        route_m = mb.addMenu("&Route")
        self._act_add_bolt = QAction("Add &Bolt…", self, shortcut="B")
        self._act_add_cam  = QAction("Add &Cam…",  self, shortcut="C")
        self._act_add_nut  = QAction("Add &Nut…",  self, shortcut="N")
        self._act_clear    = QAction("&Clear All Gear", self)

        route_m.addAction(self._act_add_bolt)
        route_m.addAction(self._act_add_cam)
        route_m.addAction(self._act_add_nut)
        route_m.addSeparator()
        route_m.addAction(self._act_clear)

        self._act_add_bolt.triggered.connect(self._add_bolt)
        self._act_add_cam.triggered.connect(self._add_cam)
        self._act_add_nut.triggered.connect(self._add_nut)
        self._act_clear.triggered.connect(self._clear_gear)

        # Simulation
        sim_m = mb.addMenu("&Simulation")
        self._act_run    = QAction("&Run Fall",    self, shortcut="F5")
        self._act_sweep  = QAction("Run &Sweep",   self, shortcut="F6")
        self._act_zipper = QAction("Run &Zipper",  self, shortcut="F7")
        self._act_stop   = QAction("&Stop",        self, shortcut="Escape")
        self._act_stop.setEnabled(False)

        sim_m.addAction(self._act_run)
        sim_m.addAction(self._act_sweep)
        sim_m.addAction(self._act_zipper)
        sim_m.addSeparator()
        sim_m.addAction(self._act_stop)

        self._act_run.triggered.connect(self._run_fall)
        self._act_sweep.triggered.connect(self._run_sweep)
        self._act_zipper.triggered.connect(self._run_zipper)
        self._act_stop.triggered.connect(self._stop_worker)

        # Rope
        rope_m = mb.addMenu("R&ope")
        self._act_edit_rope = QAction("&Edit / Add Rope…", self)
        rope_m.addAction(self._act_edit_rope)
        self._act_edit_rope.triggered.connect(self._edit_rope)

        # Help
        help_m = mb.addMenu("&Help")
        self._act_demo  = QAction("★ &Demo Route", self, shortcut="F8")
        self._act_about = QAction("&About", self)
        help_m.addAction(self._act_demo)
        help_m.addSeparator()
        help_m.addAction(self._act_about)
        self._act_demo.triggered.connect(self._run_demo)
        self._act_about.triggered.connect(self._show_about)

    # ── toolbar ──────────────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addAction(self._act_run)
        tb.addAction(self._act_sweep)
        tb.addAction(self._act_stop)
        tb.addSeparator()
        tb.addAction(self._act_add_bolt)
        tb.addAction(self._act_add_cam)
        tb.addAction(self._act_add_nut)
        tb.addSeparator()
        tb.addAction(self._act_clear)
        tb.addSeparator()

        # ── 2D / 3D view toggle ──
        self._btn_2d = QToolButton()
        self._btn_2d.setText("2D")
        self._btn_2d.setCheckable(True)
        self._btn_2d.setChecked(True)
        self._btn_2d.setToolTip("Switch to 2D route canvas")

        self._btn_3d = QToolButton()
        self._btn_3d.setText("3D")
        self._btn_3d.setCheckable(True)
        self._btn_3d.setChecked(False)
        self._btn_3d.setToolTip("Switch to 3D Vispy viewport")

        self._view_group = QButtonGroup(self)
        self._view_group.setExclusive(True)
        self._view_group.addButton(self._btn_2d, 0)
        self._view_group.addButton(self._btn_3d, 1)
        self._view_group.idToggled.connect(self._on_view_toggle)

        tb.addWidget(self._btn_2d)
        tb.addWidget(self._btn_3d)
        tb.addSeparator()

        # ── Analytical / Rapier physics mode toggle ──
        self._btn_analytical = QToolButton()
        self._btn_analytical.setText("Analytical")
        self._btn_analytical.setCheckable(True)
        self._btn_analytical.setChecked(True)
        self._btn_analytical.setToolTip("Fast analytical solver (UIAA model)")

        self._btn_rapier = QToolButton()
        self._btn_rapier.setText("Rapier 3D")
        self._btn_rapier.setCheckable(True)
        self._btn_rapier.setChecked(False)
        self._btn_rapier.setToolTip("Full 3D Rapier physics (slower; requires long rope = more links)")

        self._physics_group = QButtonGroup(self)
        self._physics_group.setExclusive(True)
        self._physics_group.addButton(self._btn_analytical, 0)
        self._physics_group.addButton(self._btn_rapier, 1)
        self._physics_group.idToggled.connect(self._on_physics_mode_toggle)

        tb.addWidget(self._btn_analytical)
        tb.addWidget(self._btn_rapier)

    # ── view / physics mode toggles ───────────────────────────────────────────

    def _on_view_toggle(self, btn_id: int, checked: bool) -> None:
        """Switch centre panel between 2D canvas (0) and 3D viewport (1)."""
        if not checked:
            return
        self._centre_stack.setCurrentIndex(btn_id)
        if btn_id == 1:
            # Mirror last result into 3D viewport if one exists
            result = getattr(self._model, "last_result", None)
            if result is not None:
                gear_items = list(self._model.gear_items)
                rope_out_m = self._props.rope_out_m() if hasattr(self._props, "rope_out_m") else 20.0
                self._viewport3d.load_result(result, gear_items, rope_out_m)
            self._sb.showMessage("3D viewport — orbit: left-drag  pan: middle-drag  zoom: scroll  reset: R")
        else:
            self._sb.showMessage("2D canvas — double-click to place gear")

    def _on_physics_mode_toggle(self, btn_id: int, checked: bool) -> None:
        """Toggle physics mode: 0=Analytical, 1=Rapier 3D."""
        if not checked:
            return
        mode = "analytical" if btn_id == 0 else "rapier_3d"
        self._viewport3d.set_physics_mode(mode)
        if btn_id == 1:
            # Estimate link count and warn if very long route
            rope_out_m = self._props.rope_out_m() if hasattr(self._props, "rope_out_m") else 20.0
            n_links = int(rope_out_m / 0.08)
            if n_links > 800:
                QMessageBox.information(
                    self, "Rapier 3D — Performance Note",
                    f"Your route uses ~{n_links} rope links.\n"
                    "For ropes over 64 m consider a coarser link spacing (0.10–0.15 m)\n"
                    "to keep simulation interactive.",
                )
        self._sb.showMessage(
            f"Physics mode: {'Analytical (fast)' if btn_id == 0 else 'Rapier 3D (full physics)'}"
        )

    # ── status bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        self._sb = QStatusBar(self)
        self.setStatusBar(self._sb)
        self._sb.showMessage("Ready — double-click canvas to place gear")

    # ── signal wiring ─────────────────────────────────────────────────────────

    def _connect_all(self) -> None:
        # Properties panel → model
        self._props.rope_changed.connect(self._on_rope_changed)
        self._props.climber_changed.connect(self._on_climber_changed)
        self._props.run_requested.connect(self._run_fall)
        self._props.sweep_requested.connect(self._run_sweep)
        self._props.zipper_requested.connect(self._run_zipper)
        self._props.add_bolt_requested.connect(self._add_bolt)
        self._props.add_cam_requested.connect(self._add_cam)
        self._props.add_nut_requested.connect(self._add_nut)
        self._props.edit_rope_requested.connect(self._edit_rope)
        self._props.demo_requested.connect(self._run_demo)

        # Canvas → model
        self._canvas.gear_moved.connect(self._on_gear_moved)
        self._canvas.add_requested.connect(self._on_canvas_add_requested)

        # Model → canvas / results
        self._model.gear_changed.connect(self._sync_canvas_gear)
        self._model.rope_changed.connect(self._refresh_rope_list)
        self._model.result_ready.connect(self._on_result_ready)
        self._model.sweep_ready.connect(self._on_sweep_ready)
        self._model.simulation_error.connect(self._on_sim_error)

    # ── rope management ───────────────────────────────────────────────────────

    def _refresh_rope_list(self) -> None:
        names = self._model.all_rope_names()
        self._props.set_rope_names(names)

    def _on_rope_changed(self, name: str) -> None:
        if name:
            self._model.set_rope_by_name(name)

    def _edit_rope(self) -> None:
        from ropesim.gui.dialogs.rope_editor import RopeEditorDialog
        dlg = RopeEditorDialog(parent=self)
        if dlg.exec():
            self._refresh_rope_list()
            saved = dlg.saved_name()
            self._model.set_rope_by_name(saved)
            self._sb.showMessage(f"Rope '{saved}' saved.")

    # ── climber ───────────────────────────────────────────────────────────────

    def _on_climber_changed(self, mass_kg: float, height_m: float) -> None:
        self._model.set_climber_mass(mass_kg)
        self._model.set_climber_height(height_m)
        self._canvas.set_climber_height(height_m)

    # ── gear placement ────────────────────────────────────────────────────────

    def _add_bolt(self) -> None:
        from ropesim.gui.dialogs.gear_editor import BoltEditorDialog
        dlg = BoltEditorDialog(parent=self)
        if dlg.exec():
            bolt = dlg.build_bolt()
            item = GearItem(
                kind="bolt",
                height_m=dlg.height_m(),
                x_offset=0.0,
                label=dlg.label(),
                bolt=bolt,
            )
            self._model.add_gear(item)

    def _add_cam(self) -> None:
        from ropesim.gui.dialogs.gear_editor import CamEditorDialog
        dlg = CamEditorDialog(parent=self)
        if dlg.exec():
            cam = dlg.build_cam()
            item = GearItem(
                kind="cam",
                height_m=dlg.height_m(),
                x_offset=0.3,
                label=dlg.label(),
                cam=cam,
            )
            self._model.add_gear(item)

    def _add_nut(self) -> None:
        from ropesim.gui.dialogs.gear_editor import NutEditorDialog
        dlg = NutEditorDialog(parent=self)
        if dlg.exec():
            nut = dlg.build_nut()
            item = GearItem(
                kind="nut",
                height_m=dlg.height_m(),
                x_offset=-0.3,
                label=dlg.label(),
                nut=nut,
            )
            self._model.add_gear(item)

    def _clear_gear(self) -> None:
        reply = QMessageBox.question(
            self, "Clear Gear",
            "Remove all protection from the route?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._model.clear_gear()
            self._results.clear()

    def _on_canvas_add_requested(self, height_m: float, x_offset_m: float) -> None:
        """Double-click on canvas → add bolt at that position."""
        from ropesim.gui.dialogs.gear_editor import BoltEditorDialog
        dlg = BoltEditorDialog(parent=self)
        dlg._height_spin.setValue(height_m)
        if dlg.exec():
            bolt = dlg.build_bolt()
            item = GearItem(
                kind="bolt",
                height_m=dlg.height_m(),
                x_offset=x_offset_m,
                label=dlg.label(),
                bolt=bolt,
            )
            self._model.add_gear(item)

    def _on_gear_moved(self, index: int, height_m: float, x_offset: float) -> None:
        self._model.move_gear(index, height_m, x_offset)

    def _sync_canvas_gear(self) -> None:
        self._canvas.load_gear(self._model.gear)

    # ── simulation ────────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        self._props.set_busy(busy)
        self._act_run.setEnabled(not busy)
        self._act_sweep.setEnabled(not busy)
        self._act_zipper.setEnabled(not busy)
        self._act_stop.setEnabled(busy)

    def _run_fall(self) -> None:
        if self._model.simulation_running:
            return
        if not self._model.gear:
            self._sb.showMessage("Add at least one piece of protection first.")
            return
        scenario       = self._model.build_scenario()
        climber_height = self._props.climber_height_m()
        self._model.simulation_running = True
        self._set_busy(True)
        self._props.set_status("Simulating…")

        worker = SimulationWorker(scenario, climber_height, parent=self)
        worker.result_ready.connect(self._model.result_ready)
        worker.error.connect(self._model.simulation_error)
        worker.progress.connect(self._props.set_progress)
        worker.finished.connect(lambda: self._on_worker_finished())
        self._worker = worker
        worker.start()

    def _run_sweep(self) -> None:
        if self._model.simulation_running:
            return
        if not self._model.gear:
            self._sb.showMessage("Add at least one piece of protection first.")
            return
        scenario = self._model.build_scenario()
        steps    = self._props.sweep_steps()
        self._model.simulation_running = True
        self._set_busy(True)
        self._props.set_status("Sweeping…")

        worker = SweepWorker(scenario, steps=steps, parent=self)
        worker.sweep_ready.connect(self._model.sweep_ready)
        worker.error.connect(self._model.simulation_error)
        worker.progress.connect(self._props.set_progress)
        worker.finished.connect(lambda: self._on_worker_finished())
        self._worker = worker
        worker.start()

    def _run_zipper(self) -> None:
        if self._model.simulation_running:
            return
        if not self._model.gear:
            self._sb.showMessage("Add at least one piece of protection first.")
            return
        scenario       = self._model.build_scenario()
        climber_height = self._props.climber_height_m()
        self._model.simulation_running = True
        self._set_busy(True)
        self._props.set_status("Analysing zipper…")

        worker = ZipperWorker(scenario, climber_height, parent=self)
        worker.result_ready.connect(self._on_zipper_ready)
        worker.error.connect(self._model.simulation_error)
        worker.finished.connect(lambda: self._on_worker_finished())
        self._worker = worker
        worker.start()

    def _stop_worker(self) -> None:
        if self._worker is not None:
            self._worker.requestInterruption()
            self._worker.quit()
        self._on_worker_finished()

    def _on_worker_finished(self) -> None:
        self._model.simulation_running = False
        self._set_busy(False)
        self._worker = None

    # ── result handlers ───────────────────────────────────────────────────────

    def _on_result_ready(self, result) -> None:
        self._model.last_result = result
        self._results.display_result(result)
        self._props.set_status(
            f"Peak: {result.peak_force_kn:.2f} kN  FF: {result.fall_factor:.3f}",
            level="success" if result.peak_force_kn < 9.0 else
                  "warning" if result.peak_force_kn < 12.0 else "danger",
        )
        self._sb.showMessage(
            f"Fall complete — peak impact {result.peak_force_kn:.2f} kN "
            f"| fall factor {result.fall_factor:.3f}"
        )
        # Animate on 2D canvas
        self._canvas.play_fall_animation(result, self._props.climber_height_m())
        # Mirror into 3D viewport (always kept in sync, whether visible or not)
        gear_items = list(self._model.gear_items)
        rope_out_m = self._props.rope_out_m() if hasattr(self._props, "rope_out_m") else 20.0
        self._viewport3d.load_result(result, gear_items, rope_out_m)

    def _on_sweep_ready(self, result) -> None:
        self._model.last_sweep = result
        self._results.display_sweep(result)
        self._sb.showMessage(f"Sweep complete — {len(result.climber_heights_m)} positions evaluated.")

    def _on_zipper_ready(self, result) -> None:
        self._results.display_zipper(result)
        n = len(result.failure_sequence) if hasattr(result, "failed_pieces") else 0
        self._sb.showMessage(f"Zipper analysis — {n} piece(s) failed.")

    def _on_sim_error(self, msg: str) -> None:
        self._props.set_status(f"Error: {msg}", level="danger")
        self._sb.showMessage(f"Simulation error: {msg}")
        QMessageBox.warning(self, "Simulation Error", msg)

    # ── export ────────────────────────────────────────────────────────────────

    def _export_pdf(self) -> None:
        if self._model.last_result is None and self._model.last_sweep is None:
            QMessageBox.information(self, "Export", "Run a simulation first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", "ropesim_report.pdf", "PDF files (*.pdf)"
        )
        if not path:
            return
        try:
            self._do_export_pdf(Path(path))
            self._sb.showMessage(f"PDF exported: {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export Error", str(exc))

    def _do_export_pdf(self, path: Path) -> None:
        """Export force-time figure to PDF via matplotlib."""
        result = self._model.last_result
        if result is None:
            raise ValueError("No fall result to export.")
        try:
            import matplotlib
            matplotlib.use("Agg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_pdf import PdfPages
        except ImportError as exc:
            raise ImportError("matplotlib is required for PDF export") from exc

        with PdfPages(str(path)) as pdf:
            fig = Figure(figsize=(8, 4))
            ax = fig.add_subplot(111)
            timestep = getattr(result, "timestep_ms", 1.0)
            t = [i * timestep for i in range(len(result.force_curve))]
            ax.plot(t, result.force_curve, label="Impact force")
            ax.axhline(12.0, color="red", linestyle="--", label="12 kN limit")
            ax.set_xlabel("Time (ms)")
            ax.set_ylabel("Force (kN)")
            ax.set_title(
                f"Fall simulation — peak {result.peak_force_kn:.2f} kN, "
                f"FF {result.fall_factor:.3f}"
            )
            ax.legend()
            pdf.savefig(fig)

    def _export_csv(self) -> None:
        if self._model.last_result is None and self._model.last_sweep is None:
            QMessageBox.information(self, "Export", "Run a simulation first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "ropesim_data.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            self._do_export_csv(Path(path))
            self._sb.showMessage(f"CSV exported: {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export Error", str(exc))

    def _do_export_csv(self, path: Path) -> None:
        sweep = self._model.last_sweep
        result = self._model.last_result
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if sweep is not None:
                arr = sweep.as_numpy()
                writer.writerow(["height_m", "fall_distance_m", "peak_kn", "fall_factor"])
                for row in arr:
                    writer.writerow([f"{v:.4f}" for v in row])
            elif result is not None:
                timestep = getattr(result, "timestep_ms", 1.0)
                writer.writerow(["time_ms", "force_kn"])
                for i, f in enumerate(result.force_curve):
                    writer.writerow([f"{i * timestep:.2f}", f"{f:.4f}"])

    # ── misc ─────────────────────────────────────────────────────────────────

    def _on_new_route(self) -> None:
        reply = QMessageBox.question(
            self, "New Route",
            "Clear the current route and start fresh?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._model.clear_gear()
            self._results.clear()
            self._sb.showMessage("New route — add protection to get started.")

    # -- demo mode ---------------------------------------------------

    def _run_demo(self) -> None:
        """Load a pre-built demo route and run a fall simulation."""
        from ropesim.anchor import Bolt, BoltType, RockType

        self._model.clear_gear()
        self._results.clear()

        # Set a standard demo rope
        names = self._model.all_rope_names()
        demo_rope = next(
            (n for n in names if "Beal" in n or "Opera" in n),
            names[0] if names else None,
        )
        if demo_rope:
            self._model.set_rope_by_name(demo_rope)
            self._props.set_rope_names(names)

        # Add four bolts at realistic sport-climbing heights
        demo_gear = [
            (2.5,  0.0,  "Bolt 1"),
            (5.0,  0.1,  "Bolt 2"),
            (8.0, -0.1,  "Bolt 3"),
            (11.5, 0.0,  "Bolt 4"),
        ]
        for height_m, x_offset, label in demo_gear:
            bolt = Bolt(
                bolt_type=BoltType.GLUE_IN,
                rated_mbs_kn=25.0,
                rock_type=RockType.GRANITE,
                position=(x_offset, height_m),
            )
            from ropesim.gui.models import GearItem
            item = GearItem(
                kind="bolt",
                height_m=height_m,
                x_offset=x_offset,
                label=label,
                bolt=bolt,
            )
            self._model.add_gear(item)

        # Place climber 2 m above the last bolt
        climber_h = 13.5
        self._model.set_climber_height(climber_h)
        self._canvas.set_climber_height(climber_h)

        self._sb.showMessage(
            "Demo route loaded — 4 bolts, climber at 13.5 m. Press F5 to simulate."
        )

    # -- about dialog ------------------------------------------------

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About RopeSim",
            "<b>RopeSim</b> — Climbing Rope Physics Simulator<br><br>"
            "Version 2.0.0<br>"
            "Simulates lead fall forces, sweep analysis, and zipper failures.<br><br>"
            "Physics models: UIAA 101 / EN 892 energy method + Rapier 3D.<br>"
            "Built with Python, Rust (PyO3), Rapier, and PySide6.",
        )