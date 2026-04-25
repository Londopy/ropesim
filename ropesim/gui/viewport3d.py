"""
ropesim.gui.viewport3d
======================
3D Vispy-based viewport for ropesim v2.

Replaces / supplements RouteCanvas for 3D simulation visualization.
Activated via the [2D View] / [3D View] toolbar toggle in MainWindow.

Requires:
    pip install vispy pyopengl pyside6
"""
from __future__ import annotations

import math
from typing import Optional, TYPE_CHECKING

import numpy as np

try:
    import vispy
    vispy.use("pyside6")
    from vispy import scene as _vs
    from vispy.scene import SceneCanvas, TurntableCamera
    _VISPY_OK = True
except Exception:
    _VISPY_OK = False

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui  import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel,
    QPushButton, QSlider, QVBoxLayout, QWidget,
)

if TYPE_CHECKING:
    from ropesim.fall    import FallResult
    from ropesim.replay  import SimulationReplay
    from ropesim.gui.models import GearItem


# ── Tension colour map (blue=slack → green → yellow → red=high) ──────────────

_TKN   = np.array([0.0,  3.0,  6.0,  9.0, 12.0], dtype=np.float32)
_TCOL  = np.array([
    [0.20, 0.40, 1.00, 1.0],   # 0 kN  blue
    [0.10, 0.80, 0.10, 1.0],   # 3 kN  green
    [1.00, 0.80, 0.00, 1.0],   # 6 kN  yellow
    [1.00, 0.40, 0.00, 1.0],   # 9 kN  orange
    [1.00, 0.10, 0.10, 1.0],   # 12 kN red
], dtype=np.float32)


def _tension_color(kn: float) -> np.ndarray:
    idx = int(np.clip(np.searchsorted(_TKN, kn, side="right") - 1, 0, len(_TKN) - 2))
    t   = float(np.clip((kn - _TKN[idx]) / (_TKN[idx + 1] - _TKN[idx] + 1e-9), 0.0, 1.0))
    return (1.0 - t) * _TCOL[idx] + t * _TCOL[idx + 1]


_GEAR_COLS = {
    "bolt":  np.array([0.2, 0.9, 0.2, 1.0], np.float32),
    "cam":   np.array([0.2, 0.6, 1.0, 1.0], np.float32),
    "nut":   np.array([0.9, 0.7, 0.1, 1.0], np.float32),
    "sling": np.array([0.9, 0.2, 0.9, 1.0], np.float32),
}
_CLIMBER_COL   = np.array([0.9, 0.5, 0.1, 1.0], np.float32)
_ROCK_BASE_COL = np.array([0.45, 0.40, 0.35, 0.85], np.float32)
_ARROW_COL     = np.array([1.0, 0.3, 0.3, 1.0], np.float32)


# ── Rock face plane mesh ──────────────────────────────────────────────────────

def _plane_mesh(width: float = 4.0, height: float = 30.0,
                nx: int = 4, ny: int = 20):
    xs = np.linspace(-width / 2, width / 2, nx + 1)
    ys = np.linspace(0.0, height, ny + 1)
    verts = np.array([[x, y, 0.0]
                      for y in ys for x in xs], dtype=np.float32)
    cols_ = nx + 1
    faces = []
    for row in range(ny):
        for col in range(nx):
            i0, i1 = row * cols_ + col, row * cols_ + col + 1
            i2, i3 = i0 + cols_, i1 + cols_
            faces += [[i0, i1, i2], [i1, i3, i2]]
    faces = np.array(faces, dtype=np.uint32)
    rng   = np.random.default_rng(42)
    rgb   = np.clip(
        _ROCK_BASE_COL[:3] + rng.uniform(-0.05, 0.05, (len(verts), 3)),
        0.0, 1.0,
    ).astype(np.float32)
    alpha = np.full((len(verts), 1), _ROCK_BASE_COL[3], dtype=np.float32)
    return verts, faces, np.hstack([rgb, alpha]).astype(np.float32)


# ── Playback bar ──────────────────────────────────────────────────────────────

class _PlaybackBar(QWidget):
    """Slim playback control strip at the bottom of Viewport3D."""

    frame_changed    = Signal(int)
    play_requested   = Signal()
    pause_requested  = Signal()
    stop_requested   = Signal()
    speed_changed    = Signal(float)

    _SPEEDS = [0.1, 0.25, 0.5, 1.0, 2.0]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._total = 0
        self._playing = False
        self._setup()

    def _setup(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)

        self._btn_prev  = QPushButton("⏮"); self._btn_prev.setFixedWidth(28)
        self._btn_play  = QPushButton("▶"); self._btn_play.setFixedWidth(28)
        self._btn_next  = QPushButton("⏭"); self._btn_next.setFixedWidth(28)
        self._btn_stop  = QPushButton("⏹"); self._btn_stop.setFixedWidth(28)
        self._slider    = QSlider(Qt.Horizontal)
        self._lbl       = QLabel("0 / 0")
        self._lbl.setFont(QFont("Monospace", 8))
        self._lbl.setMinimumWidth(64)
        self._speed_cb  = QComboBox()
        for s in ["0.1×", "0.25×", "0.5×", "1×", "2×"]:
            self._speed_cb.addItem(s)
        self._speed_cb.setCurrentIndex(3)
        self._speed_cb.setFixedWidth(60)
        self._chk_loop  = QCheckBox("Loop")

        for w in [self._btn_prev, self._btn_play, self._btn_next, self._btn_stop,
                  self._slider, self._lbl, self._speed_cb, self._chk_loop]:
            lay.addWidget(w)

        self._btn_play.clicked.connect(self._on_play_pause)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_prev.clicked.connect(lambda: self._step(-1))
        self._btn_next.clicked.connect(lambda: self._step(1))
        self._slider.valueChanged.connect(self._on_slider)
        self._speed_cb.currentIndexChanged.connect(
            lambda _: self.speed_changed.emit(self.speed())
        )

    # public
    def set_total_frames(self, n: int) -> None:
        self._total = n
        self._slider.setMaximum(max(0, n - 1))
        self._lbl.setText(f"0 / {n}")

    def set_frame(self, f: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(f)
        self._slider.blockSignals(False)
        self._lbl.setText(f"{f} / {self._total}")

    def speed(self) -> float:
        return self._SPEEDS[self._speed_cb.currentIndex()]

    def is_looping(self) -> bool:
        return self._chk_loop.isChecked()

    # slots
    def _on_play_pause(self) -> None:
        self._playing = not self._playing
        self._btn_play.setText("⏸" if self._playing else "▶")
        (self.play_requested if self._playing else self.pause_requested).emit()

    def _on_stop(self) -> None:
        self._playing = False
        self._btn_play.setText("▶")
        self.stop_requested.emit()

    def _step(self, d: int) -> None:
        self._slider.setValue(max(0, min(self._total - 1, self._slider.value() + d)))

    def _on_slider(self, v: int) -> None:
        self._lbl.setText(f"{v} / {self._total}")
        self.frame_changed.emit(v)


# ── Viewport3D ────────────────────────────────────────────────────────────────

class Viewport3D(QWidget):
    """
    3D Vispy viewport for ropesim v2.

    Public interface (mirrors RouteCanvas where applicable):

        load_result(result, gear_items, rope_out_m)   -- static analytical result
        load_replay(replay)                            -- Rapier frame-by-frame
        set_rope_links(positions)                      -- update rope from link list
        set_climber_pos(pos)                           -- move climber marker
        set_view_preset(name)                          -- "front"|"side"|"top"|"iso"
        reset_camera()                                 -- R key / toolbar button
        set_physics_mode(mode)                         -- "analytical"|"rapier_3d"
        set_force_arrows_visible(visible)              -- toggle force arrows
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._replay:  Optional[SimulationReplay] = None
        self._frame    = 0
        self._timer    = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._arrows_on = True
        self._mode      = "analytical"
        self._canvas    = None
        self._view      = None
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if not _VISPY_OK:
            msg = QLabel(
                "3D viewport requires Vispy.\npip install vispy pyopengl"
            )
            msg.setAlignment(Qt.AlignCenter)
            layout.addWidget(msg)
            return

        # ── Vispy scene ──
        self._canvas = SceneCanvas(keys="interactive", bgcolor="#1a1a2e", show=False)
        self._view   = self._canvas.central_widget.add_view()
        self._view.camera = TurntableCamera(
            elevation=25.0, azimuth=-60.0, fov=45.0, distance=25.0,
        )
        self._canvas.connect(self._on_key)
        self._build_visuals()
        layout.addWidget(self._canvas.native, stretch=1)

        # ── view preset bar ──
        pbar = QWidget()
        pl   = QHBoxLayout(pbar)
        pl.setContentsMargins(4, 2, 4, 2); pl.setSpacing(4)
        for name, el, az in [("Front", 0.0, 0.0), ("Side", 0.0, -90.0),
                              ("Top", 90.0, 0.0), ("Iso", 25.0, -45.0)]:
            btn = QPushButton(name); btn.setFixedWidth(48)
            btn.clicked.connect(
                (lambda e=el, a=az: lambda: self._set_cam(e, a))()
            )
            pl.addWidget(btn)
        pl.addStretch()
        self._chk_arrows = QCheckBox("Force arrows")
        self._chk_arrows.setChecked(True)
        self._chk_arrows.toggled.connect(self._on_toggle_arrows)
        pl.addWidget(self._chk_arrows)
        layout.addWidget(pbar)

        # ── playback bar ──
        self._pbar = _PlaybackBar(self)
        self._pbar.frame_changed.connect(self._goto)
        self._pbar.play_requested.connect(self._play)
        self._pbar.pause_requested.connect(self._pause)
        self._pbar.stop_requested.connect(self._stop)
        self._pbar.speed_changed.connect(self._on_speed)
        layout.addWidget(self._pbar)

    def _build_visuals(self) -> None:
        """Allocate all persistent Vispy visuals."""
        # Rock face
        verts, faces, cols = _plane_mesh()
        self._rock = _vs.visuals.Mesh(
            vertices=verts, faces=faces, vertex_colors=cols,
            parent=self._view.scene,
        )
        self._rock.set_gl_state("translucent", depth_test=True)

        # Rope polyline
        dummy = np.zeros((2, 3), dtype=np.float32)
        self._rope = _vs.visuals.Line(
            pos=dummy,
            color=np.array([0.2, 0.4, 1.0, 1.0], np.float32),
            width=3.0,
            parent=self._view.scene,
        )

        # Gear markers
        self._gear_mkr = _vs.visuals.Markers(parent=self._view.scene)
        self._gear_mkr.set_data(
            pos=np.zeros((1, 3), np.float32),
            face_color=np.array([[0.2, 0.9, 0.2, 1.0]], np.float32),
            size=14,
        )

        # Climber
        self._climber_mkr = _vs.visuals.Markers(parent=self._view.scene)
        self._climber_mkr.set_data(
            pos=np.array([[0.0, 0.0, 0.5]], np.float32),
            face_color=np.array([_CLIMBER_COL], np.float32),
            size=22, symbol="o",
        )
        self._climber_mkr.visible = False

        # Force arrows (segment pairs)
        self._arrows = _vs.visuals.Line(
            pos=np.zeros((2, 3), np.float32),
            color=_ARROW_COL,
            width=2.0,
            connect="segments",
            parent=self._view.scene,
        )
        self._arrows.visible = False

    # ── Public API ────────────────────────────────────────────────────────────

    def load_result(
        self,
        result:      "FallResult",
        gear_items:  list["GearItem"] | None = None,
        rope_out_m:  float = 20.0,
    ) -> None:
        """Display a static FallResult (analytical or Rapier peak)."""
        if not _VISPY_OK or self._view is None:
            return

        self._replay = None
        self._pbar.set_total_frames(0)
        peak = result.peak_force_kn

        # Rope with tension gradient
        n    = max(20, int(rope_out_m / 0.4))
        pts  = np.zeros((n, 3), np.float32)
        pts[:, 1] = np.linspace(0.0, rope_out_m, n)
        sag  = rope_out_m * 0.018
        pts[:, 0] = sag * np.sin(np.linspace(0, math.pi, n))
        colors = np.array(
            [_tension_color(t) for t in np.linspace(0.0, peak, n)],
            dtype=np.float32,
        )
        self._rope.set_data(pos=pts, color=colors)

        # Gear markers
        if gear_items:
            self._refresh_gear_markers(gear_items, peak)

        # Climber
        ch = rope_out_m + result.fall_distance_m
        self._climber_mkr.set_data(
            pos=np.array([[0.0, float(ch), 0.5]], np.float32),
            face_color=np.array([_CLIMBER_COL], np.float32),
            size=22,
        )
        self._climber_mkr.visible = True

        # Force arrow at anchor
        self._refresh_arrows(
            positions=[(0.0, float(rope_out_m), 0.0)],
            forces=[(0.0, -peak, 0.0)],
        )

        self._view.camera.set_range(
            x=(-3, 3), y=(-1, rope_out_m + 3), z=(-2, 4)
        )
        self._canvas.update()

    def load_replay(self, replay: "SimulationReplay") -> None:
        """Load a SimulationReplay for Rapier frame playback."""
        if not _VISPY_OK or self._view is None:
            return
        self._replay = replay
        self._frame  = 0
        self._pbar.set_total_frames(replay.total_frames())
        self._goto(0)

    def set_rope_links(self, positions: list[tuple[float, float, float]]) -> None:
        """Update rope visual directly from Rapier link positions."""
        if not _VISPY_OK or not positions:
            return
        pts   = np.array(positions, np.float32)
        yspan = pts[:, 1].max() - pts[:, 1].min() + 1e-9
        norms = (pts[:, 1] - pts[:, 1].min()) / yspan
        cols  = np.array([_tension_color(v * 12.0) for v in norms], np.float32)
        self._rope.set_data(pos=pts, color=cols)
        self._canvas.update()

    def set_climber_pos(self, pos: tuple[float, float, float]) -> None:
        """Move the climber marker."""
        if not _VISPY_OK:
            return
        self._climber_mkr.set_data(
            pos=np.array([pos], np.float32),
            face_color=np.array([_CLIMBER_COL], np.float32),
            size=22,
        )
        self._climber_mkr.visible = True
        self._canvas.update()

    def set_view_preset(self, name: str) -> None:
        """Camera preset: "front", "side", "top", "iso"."""
        presets = {"front": (0.0, 0.0), "side": (0.0, -90.0),
                   "top": (90.0, 0.0), "iso": (25.0, -45.0)}
        if name in presets:
            self._set_cam(*presets[name])

    def reset_camera(self) -> None:
        self._set_cam(25.0, -60.0)
        if self._view:
            self._view.camera.distance = 25.0

    def set_physics_mode(self, mode: str) -> None:
        self._mode = mode

    def set_force_arrows_visible(self, visible: bool) -> None:
        self._arrows_on = visible
        if self._arrows:
            self._arrows.visible = visible
        if self._canvas:
            self._canvas.update()

    # ── Camera helpers ────────────────────────────────────────────────────────

    def _set_cam(self, elevation: float, azimuth: float) -> None:
        if self._view is None:
            return
        self._view.camera.elevation = elevation
        self._view.camera.azimuth   = azimuth
        self._canvas.update()

    def _on_key(self, event) -> None:
        if getattr(event, "key", None) == "R":
            self.reset_camera()

    # ── Playback ──────────────────────────────────────────────────────────────

    def _goto(self, frame: int) -> None:
        if self._replay is None:
            return
        self._frame = frame
        self._pbar.set_frame(frame)
        frm = self._replay.frame(frame)
        if hasattr(frm, "link_positions") and frm.link_positions:
            self.set_rope_links(frm.link_positions)
        if hasattr(frm, "climber_pos") and frm.climber_pos:
            self.set_climber_pos(frm.climber_pos)

    def _play(self) -> None:
        if self._replay is None:
            return
        ms = max(1, int(1000.0 / (self._pbar.speed() * 60.0)))
        self._timer.start(ms)

    def _pause(self) -> None:
        self._timer.stop()

    def _stop(self) -> None:
        self._timer.stop()
        self._goto(0)

    def _tick(self) -> None:
        if self._replay is None:
            self._timer.stop(); return
        nxt = self._frame + 1
        if nxt >= self._replay.total_frames():
            if self._pbar.is_looping():
                nxt = 0
            else:
                self._timer.stop(); self._pbar._on_stop(); return
        self._goto(nxt)

    def _on_speed(self, speed: float) -> None:
        if self._timer.isActive():
            self._timer.setInterval(max(1, int(1000.0 / (speed * 60.0))))

    # ── Visual helpers ────────────────────────────────────────────────────────

    def _refresh_gear_markers(
        self,
        items:          list["GearItem"],
        peak_force_kn:  float = 0.0,
    ) -> None:
        pos, col = [], []
        for item in items:
            h    = getattr(item, "height_m", 0.0)
            x    = getattr(item, "x_offset_m", 0.0)
            pos.append([x, h, 0.0])
            kind = getattr(item, "kind", "bolt").lower()
            c    = _GEAR_COLS.get(kind, _GEAR_COLS["bolt"]).copy()
            mbs  = getattr(item, "rated_mbs_kn", 12.0)
            frac = float(np.clip(peak_force_kn / max(mbs, 1e-3), 0.0, 1.0))
            c[0] = min(1.0, c[0] + frac * 0.8)
            c[1] = max(0.0, c[1] - frac * 0.7)
            c[2] = max(0.0, c[2] - frac * 0.5)
            col.append(c)
        self._gear_mkr.set_data(
            pos=np.array(pos, np.float32),
            face_color=np.array(col, np.float32),
            size=16, symbol="diamond",
        )

    def _refresh_arrows(
        self,
        positions: list[tuple[float, float, float]],
        forces:    list[tuple[float, float, float]],
        scale:     float = 0.3,
    ) -> None:
        if not positions or not self._arrows_on:
            return
        pts = []
        for (px, py, pz), (fx, fy, fz) in zip(positions, forces):
            mag = math.sqrt(fx * fx + fy * fy + fz * fz)
            if mag < 0.01:
                continue
            pts.extend([[px, py, pz], [px + fx * scale, py + fy * scale, pz + fz * scale]])
        if not pts:
            return
        self._arrows.set_data(pos=np.array(pts, np.float32))
        self._arrows.visible = True
        if self._canvas:
            self._canvas.update()

    def _on_toggle_arrows(self, checked: bool) -> None:
        self._arrows_on = checked
        if self._arrows:
            self._arrows.visible = checked
        if self._canvas:
            self._canvas.update()
