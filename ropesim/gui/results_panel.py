"""ResultsPanel — right panel: summary numbers + embedded matplotlib plots."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGroupBox, QHBoxLayout, QLabel, QSizePolicy,
    QTabWidget, QVBoxLayout, QWidget,
)

from ropesim.gui.style import DANGER, SUCCESS, TEXT_PRIMARY, WARNING, force_color

if TYPE_CHECKING:
    from ropesim.fall import FallResult
    from ropesim.simulate import SweepResult

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    _HAS_MPL = True
except Exception:  # noqa: BLE001
    _HAS_MPL = False


def _make_canvas():
    if not _HAS_MPL:
        return None
    fig = Figure(figsize=(4, 2.8), dpi=90, facecolor="#1e1e2e")
    canvas = FigureCanvasQTAgg(fig)
    canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    return canvas


class _MetricRow(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 11px;")
        self._val = QLabel("—")
        self._val.setStyleSheet("font-weight: bold; font-size: 12px;")
        self._val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._lbl)
        layout.addStretch()
        layout.addWidget(self._val)

    def set_value(self, text: str, color: str = "") -> None:
        self._val.setText(text)
        style = "font-weight: bold; font-size: 12px;"
        if color:
            style += f" color: {color};"
        self._val.setStyleSheet(style)


class ResultsPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(420)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)
        root.addWidget(self._summary_group())
        root.addWidget(self._plot_tabs(), stretch=1)

    def _summary_group(self) -> QGroupBox:
        grp = QGroupBox("Fall Summary")
        layout = QVBoxLayout(grp)
        layout.setSpacing(4)

        self._row_peak    = _MetricRow("Peak impact force:")
        self._row_ff      = _MetricRow("Fall factor:")
        self._row_dist    = _MetricRow("Fall distance:")
        self._row_rope    = _MetricRow("Rope out:")
        self._row_energy  = _MetricRow("Rope absorbed:")
        self._row_survive = _MetricRow("Rope survived:")

        for row in (self._row_peak, self._row_ff, self._row_dist,
                    self._row_rope, self._row_energy, self._row_survive):
            layout.addWidget(row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        self._warnings_label = QLabel()
        self._warnings_label.setWordWrap(True)
        self._warnings_label.setStyleSheet(f"font-size: 10px; color: {WARNING};")
        self._warnings_label.setVisible(False)
        layout.addWidget(self._warnings_label)

        self._zipper_label = QLabel("Zipper risk: —")
        self._zipper_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._zipper_label)

        return grp

    def _plot_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Force-time tab
        ft_w = QWidget()
        ft_l = QVBoxLayout(ft_w)
        ft_l.setContentsMargins(0, 0, 0, 0)
        self._ft_canvas = _make_canvas()
        if self._ft_canvas is not None:
            ft_l.addWidget(self._ft_canvas)
            ax = self._ft_canvas.figure.add_subplot(111)
            self._style_ax(ax, "Force vs Time", "Time (ms)", "Force (kN)")
            self._ft_ax = ax
        else:
            ft_l.addWidget(QLabel("matplotlib not available"))
            self._ft_ax = None
        tabs.addTab(ft_w, "Force-Time")

        # Sweep tab
        sw_w = QWidget()
        sw_l = QVBoxLayout(sw_w)
        sw_l.setContentsMargins(0, 0, 0, 0)
        self._sw_canvas = _make_canvas()
        if self._sw_canvas is not None:
            sw_l.addWidget(self._sw_canvas)
            ax = self._sw_canvas.figure.add_subplot(111)
            self._style_ax(ax, "Peak Force vs Height", "Climber height (m)", "Peak force (kN)")
            self._sw_ax = ax
        else:
            sw_l.addWidget(QLabel("matplotlib not available"))
            self._sw_ax = None
        tabs.addTab(sw_w, "Sweep")

        self._tabs = tabs
        return tabs

    @staticmethod
    def _style_ax(ax, title: str, xlabel: str, ylabel: str) -> None:
        ax.set_facecolor("#313244")
        ax.set_title(title, color="#cdd6f4", fontsize=9)
        ax.set_xlabel(xlabel, color="#cdd6f4", fontsize=8)
        ax.set_ylabel(ylabel, color="#cdd6f4", fontsize=8)
        ax.tick_params(colors="#cdd6f4", labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor("#45475a")

    # ── public API ───────────────────────────────────────────────────────────

    def display_result(self, result: "FallResult") -> None:
        peak = result.peak_force_kn
        color = force_color(peak)
        self._row_peak.set_value(f"{peak:.2f} kN", color)
        self._row_ff.set_value(f"{result.fall_factor:.3f}")
        self._row_dist.set_value(f"{result.fall_distance_m:.2f} m")
        self._row_rope.set_value(f"{result.rope_out_m:.2f} m")
        self._row_energy.set_value(
            f"{result.energy_budget.rope_absorption_j:.0f} J"
        )
        if result.rope_survived:
            self._row_survive.set_value("Yes", SUCCESS)
        else:
            self._row_survive.set_value("Retire rope!", DANGER)

        if result.warnings:
            self._warnings_label.setText("⚠ " + "  ⚠ ".join(result.warnings))
            self._warnings_label.setVisible(True)
        else:
            self._warnings_label.setVisible(False)

        if self._ft_ax is not None and result.force_curve:
            ax = self._ft_ax
            ax.cla()
            self._style_ax(ax, "Force vs Time", "Time (ms)", "Force (kN)")
            t = [i * result.timestep_ms for i in range(len(result.force_curve))]
            ax.plot(t, result.force_curve, color="#89b4fa", linewidth=1.5)
            ax.axhline(12.0, color=DANGER, linewidth=0.8, linestyle="--",
                       label="12 kN limit")
            ax.legend(fontsize=7, facecolor="#313244", labelcolor="#cdd6f4")
            self._ft_canvas.draw()  # type: ignore[union-attr]
            self._tabs.setCurrentIndex(0)

    def display_sweep(self, result: "SweepResult") -> None:
        if self._sw_ax is None:
            return
        arr = result.as_numpy()  # (N,4): height, fall_dist, fall_factor, peak_kn
        if arr.size == 0:
            return
        heights = arr[:, 0]
        peaks   = arr[:, 3]   # column 3 is peak_kn
        ax = self._sw_ax
        ax.cla()
        self._style_ax(ax, "Peak Force vs Height", "Climber height (m)", "Peak force (kN)")
        ax.plot(heights, peaks, color="#89b4fa", linewidth=1.5)
        ax.axhline(12.0, color=DANGER, linewidth=0.8, linestyle="--", label="12 kN")
        ax.axhline(9.0,  color=WARNING, linewidth=0.8, linestyle=":",  label="9 kN warn")
        ax.legend(fontsize=7, facecolor="#313244", labelcolor="#cdd6f4")
        self._sw_canvas.draw()  # type: ignore[union-attr]
        self._tabs.setCurrentIndex(1)

    def display_zipper(self, result) -> None:
        n = result.total_pieces_failed
        peak = result.initial_fall_result.peak_force_kn
        color = force_color(peak)
        self._zipper_label.setText(
            f"Zipper: {n} piece(s) failed — initial peak {peak:.2f} kN"
        )
        self._zipper_label.setStyleSheet(f"font-size: 11px; color: {color};")

    def clear(self) -> None:
        for row in (self._row_peak, self._row_ff, self._row_dist,
                    self._row_rope, self._row_energy, self._row_survive):
            row.set_value("—")
        self._warnings_label.setVisible(False)
        self._zipper_label.setText("Zipper risk: —")
