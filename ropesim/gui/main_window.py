"""MainWindow — three-panel QSplitter with menu/toolbar and live simulation."""
from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QMainWindow, QMessageBox,
    QSplitter, QStatusBar, QToolBar,
)

from ropesim.anchor import Bolt, Cam, Nut
from ropesim.gui.canvas import RouteCanvas
from ropesim.gui.models import GearItem, RouteModel
from ropesim.gui.properties_panel import PropertiesPanel
from ropesim.gui.results_panel import ResultsPanel
from ropesim.gui.style import STYLESHEET
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
        self._props   = PropertiesPanel(self)
        self._canvas  = RouteCanvas(self)
        self._results = ResultsPanel(self)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._props)
        splitter.addWidget(self._canvas)
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
        # Animate on canvas
        self._canvas.play_fall_animation(result, self._props.climber_height_m())

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

    # ── demo mode ─────────────────────────────────────────────────────────────

    def _run_demo(self) -> None:
        """
        Animated demo: place a realistic mixed trad/sport route piece-by-piece,
        then run a fall simulation followed by a position sweep.

        Gear sequence (bottom → top):
          3 m  — nut  (passive stopper, marginal placement)
          6 m  — cam  (SLCD, good placement)
          9 m  — nut  (passive, perfect placement)
         13 m  — cam  (SLCD, good placement)
         17 m  — bolt (sport, glue-in)
         20 m  — bolt (sport, glue-in)  ← last piece of pro
        Climber at 22 m → fall factor ≈ 0.40
        """
        from ropesim.anchor import (
            AnchorSystem, AnchorType,
            Bolt, Cam, Nut,
            BoltType, CamPlacement, RockType,
        )
        from ropesim.gui.models import GearItem

        # ── stop any running simulation first
        self._stop_worker()
        self._model.clear_gear()
        self._results.clear()
        self._sb.showMessage("★ Demo mode — watch the route build…")

        # ── gear definitions ─────────────────────────────────────────────────
        def _nut(height_m: float, placement: CamPlacement, label: str, x: float = 0.0) -> GearItem:
            n = Nut(rated_mbs_kn=9.0, placement=placement, rock_type=RockType.GRANITE)
            return GearItem(kind="nut", height_m=height_m, x_offset=x, label=label, nut=n)

        def _cam(height_m: float, placement: CamPlacement, label: str, x: float = 0.25) -> GearItem:
            c = Cam(brand="Wild Country", size="1", rated_mbs_kn=12.0,
                    placement=placement, rock_type=RockType.GRANITE, walking_risk=False)
            return GearItem(kind="cam", height_m=height_m, x_offset=x, label=label, cam=c)

        def _bolt(height_m: float, label: str, x: float = 0.0) -> GearItem:
            b = Bolt(bolt_type=BoltType.GLUE_IN, rated_mbs_kn=25.0,
                     age_years=3, rock_type=RockType.GRANITE)
            return GearItem(kind="bolt", height_m=height_m, x_offset=x, label=label, bolt=b)

        sequence = [
            _nut (  3.0, CamPlacement.MARGINAL, "Nut 1",  x= 0.0),
            _cam (  6.0, CamPlacement.GOOD,     "Cam 1",  x= 0.25),
            _nut (  9.0, CamPlacement.PERFECT,  "Nut 2",  x=-0.2),
            _cam ( 13.0, CamPlacement.GOOD,     "Cam 2",  x= 0.25),
            _bolt( 17.0,                        "Bolt 1", x= 0.0),
            _bolt( 20.0,                        "Bolt 2", x= 0.0),
        ]

        CLIMBER_HEIGHT = 22.0
        DELAY_MS       = 500   # ms between each piece appearing

        # ── schedule each gear item with increasing delay ────────────────────
        for i, item in enumerate(sequence):
            QTimer.singleShot(
                i * DELAY_MS,
                lambda it=item, idx=i: self._demo_add_piece(it, idx, len(sequence)),
            )

        # ── after all gear is placed: set climber, run fall, then sweep ──────
        total_gear_delay = len(sequence) * DELAY_MS

        QTimer.singleShot(
            total_gear_delay + 300,
            lambda: self._demo_set_climber(CLIMBER_HEIGHT),
        )
        QTimer.singleShot(
            total_gear_delay + 700,
            self._run_fall,
        )
        # sweep starts after fall animation (~3 s)
        QTimer.singleShot(
            total_gear_delay + 4200,
            self._run_sweep,
        )

    def _demo_add_piece(self, item, idx: int, total: int) -> None:
        """Called by QTimer to add one gear item and update the status bar."""
        self._model.add_gear(item)
        kind_icon = {"bolt": "🔩", "cam": "🟣", "nut": "🔶"}.get(item.kind, "•")
        self._sb.showMessage(
            f"★ Demo — placing gear {idx + 1}/{total}: "
            f"{kind_icon} {item.label} at {item.height_m:.0f} m"
        )

    def _demo_set_climber(self, height_m: float) -> None:
        """Move climber to demo height and update the canvas."""
        self._props._height_spin.setValue(height_m)
        self._model.set_climber_height(height_m)
        self._canvas.set_climber_height(height_m)
        self._sb.showMessage(
            f"★ Demo — climber at {height_m:.0f} m, simulating fall…"
        )

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About RopeSim",
            "<b>RopeSim</b> — Climbing Rope Physics Simulator<br><br>"
            "Simulates UIAA 101 / EN 892 fall scenarios using a "
            "Rust RK4 physics engine.<br><br>"
            "Double-click the canvas to place gear.<br>"
            "Ctrl+Scroll to zoom, Middle-drag to pan.",
        )
