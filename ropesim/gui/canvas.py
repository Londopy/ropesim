"""RouteCanvas — QGraphicsView for bolt/cam/nut placement and fall animation."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QPointF, QRectF, QSizeF, Qt, Signal, QTimer, QObject,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
    QTransform, QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem,
    QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsRectItem,
    QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView,
)

from ropesim.gui.style import (
    BOLT_COLOR, CAM_COLOR, CLIMBER_COLOR, DARK_BG, NUT_COLOR,
    ROPE_COLOR, TEXT_PRIMARY, WALL_COLOR,
)

if TYPE_CHECKING:
    from ropesim.fall import FallResult
    from ropesim.simulate import SweepResult
    from ropesim.gui.models import GearItem

# ── coordinate helpers ──────────────────────────────────────────────────────
# Scene units: 1 scene unit == 1 metre.  Y is *inverted* so up == positive.
PIXELS_PER_METRE = 60.0   # initial zoom level
WALL_WIDTH_M     = 4.0    # metres wide


def metres_to_scene(height_m: float, x_offset_m: float = 0.0) -> QPointF:
    """Convert real-world metres to scene coords (Y inverted)."""
    return QPointF(x_offset_m * PIXELS_PER_METRE,
                   -height_m * PIXELS_PER_METRE)


# ── gear graphics items ──────────────────────────────────────────────────────

class _GearBase(QGraphicsItem):
    """Abstract base for draggable gear items."""

    KIND: str = "base"
    _SIZE = 18.0   # bounding-box half-size in scene units

    def __init__(self, gear_index: int, label: str = ""):
        super().__init__()
        self._index = gear_index
        self._label = label
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setCursor(Qt.OpenHandCursor)
        self.setZValue(10)

    @property
    def gear_index(self) -> int:
        return self._index

    def boundingRect(self) -> QRectF:
        s = self._SIZE
        return QRectF(-s, -s, 2 * s, 2 * s)

    def height_m(self) -> float:
        return -self.y() / PIXELS_PER_METRE

    def x_offset_m(self) -> float:
        return self.x() / PIXELS_PER_METRE

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            # constrain x to wall bounds
            new_pos = value
            wall_px = WALL_WIDTH_M * PIXELS_PER_METRE
            new_x = max(-wall_px / 2, min(wall_px / 2, new_pos.x()))
            # constrain y >= 0 (height >= 0)
            new_y = min(0.0, new_pos.y())
            return QPointF(new_x, new_y)
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        super().mouseReleaseEvent(event)
        scene = self.scene()
        if scene is not None:
            scene.gear_moved.emit(self._index, self.height_m(), self.x_offset_m())


class BoltItem(_GearBase):
    KIND = "bolt"
    _SIZE = 10.0

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing)
        selected = self.isSelected()
        color = QColor(BOLT_COLOR)
        pen = QPen(color.darker(130) if selected else color.darker(150), 2)
        brush = QBrush(color.lighter(120) if selected else color)
        painter.setPen(pen)
        painter.setBrush(brush)
        r = self._SIZE
        # Hexagonal bolt head approximation — use circle for simplicity
        painter.drawEllipse(QRectF(-r, -r, 2 * r, 2 * r))
        # crosshair
        painter.setPen(QPen(QColor(DARK_BG), 2))
        painter.drawLine(QPointF(-r * 0.5, 0), QPointF(r * 0.5, 0))
        painter.drawLine(QPointF(0, -r * 0.5), QPointF(0, r * 0.5))
        if self._label:
            painter.setPen(QPen(QColor(TEXT_PRIMARY)))
            painter.setFont(QFont("monospace", 7))
            painter.drawText(QPointF(r + 2, 4), self._label)


class CamItem(_GearBase):
    KIND = "cam"
    _SIZE = 12.0

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing)
        selected = self.isSelected()
        color = QColor(CAM_COLOR)
        pen = QPen(color.darker(130) if selected else color.darker(160), 2)
        brush = QBrush(color.lighter(110) if selected else color)
        painter.setPen(pen)
        painter.setBrush(brush)
        r = self._SIZE
        # Diamond shape for cam
        path = QPainterPath()
        path.moveTo(0, -r)
        path.lineTo(r, 0)
        path.lineTo(0, r)
        path.lineTo(-r, 0)
        path.closeSubpath()
        painter.drawPath(path)
        if self._label:
            painter.setPen(QPen(QColor(TEXT_PRIMARY)))
            painter.setFont(QFont("monospace", 7))
            painter.drawText(QPointF(r + 2, 4), self._label)


class NutItem(_GearBase):
    KIND = "nut"
    _SIZE = 9.0

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing)
        selected = self.isSelected()
        color = QColor(NUT_COLOR)
        pen = QPen(color.darker(130) if selected else color.darker(160), 2)
        brush = QBrush(color.lighter(110) if selected else color)
        painter.setPen(pen)
        painter.setBrush(brush)
        r = self._SIZE
        # Triangle for nut
        path = QPainterPath()
        path.moveTo(0, -r)
        path.lineTo(r, r * 0.7)
        path.lineTo(-r, r * 0.7)
        path.closeSubpath()
        painter.drawPath(path)
        if self._label:
            painter.setPen(QPen(QColor(TEXT_PRIMARY)))
            painter.setFont(QFont("monospace", 7))
            painter.drawText(QPointF(r + 2, 4), self._label)


class ClimberItem(QGraphicsItem):
    """Stick-figure climber icon."""

    _RADIUS = 10.0

    def __init__(self):
        super().__init__()
        self.setZValue(20)

    def boundingRect(self) -> QRectF:
        r = self._RADIUS
        return QRectF(-r, -r * 3, r * 2, r * 4)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(CLIMBER_COLOR)
        pen = QPen(color, 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(color))
        r = self._RADIUS
        # head
        painter.drawEllipse(QRectF(-r * 0.5, -r * 3, r, r))
        # body
        painter.drawLine(QPointF(0, -r * 2), QPointF(0, 0))
        # arms
        painter.drawLine(QPointF(-r, -r * 1.5), QPointF(r, -r * 1.5))
        # legs
        painter.drawLine(QPointF(0, 0), QPointF(-r * 0.8, r))
        painter.drawLine(QPointF(0, 0), QPointF(r * 0.8, r))


class _RouteScene(QGraphicsScene):
    """Scene that emits signals when gear items are moved."""

    gear_moved    = Signal(int, float, float)   # index, height_m, x_offset_m
    gear_selected = Signal(int)                 # index (-1 = deselected)
    request_add   = Signal(float, float)        # height_m, x_offset_m on double-click

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        pos = event.scenePos()
        h = -pos.y() / PIXELS_PER_METRE
        x = pos.x() / PIXELS_PER_METRE
        self.request_add.emit(max(0.0, h), x)
        super().mouseDoubleClickEvent(event)


# ── main canvas widget ───────────────────────────────────────────────────────

class RouteCanvas(QGraphicsView):
    """Central canvas: rope route editor + fall animation playback."""

    gear_moved    = Signal(int, float, float)
    gear_selected = Signal(int)
    add_requested = Signal(float, float)   # height_m, x_offset_m

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = _RouteScene(self)
        self.setScene(self._scene)

        self.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )
        self.setBackgroundBrush(QBrush(QColor(DARK_BG)))
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

        # Initial transform: flip Y so up == positive
        self.setTransform(QTransform().scale(1, 1))

        self._gear_items: dict[int, _GearBase] = {}
        self._rope_item: QGraphicsPathItem | None = None
        self._climber_item: ClimberItem | None = None
        self._force_arrows: list[QGraphicsLineItem] = []
        self._wall_item: QGraphicsRectItem | None = None

        self._anim_timer   = QTimer(self)
        self._anim_frames: list[float] = []
        self._anim_index   = 0
        self._anim_start_y = 0.0

        self._draw_wall()
        self._scene.gear_moved.connect(self.gear_moved)
        self._scene.gear_selected.connect(self.gear_selected)
        self._scene.request_add.connect(self.add_requested)

        # fit view after a moment
        QTimer.singleShot(0, self._fit_initial)

    # ── wall background ──────────────────────────────────────────────────────

    def _draw_wall(self) -> None:
        wall_px = WALL_WIDTH_M * PIXELS_PER_METRE
        height_px = 30 * PIXELS_PER_METRE  # 30 m tall wall
        rect = QRectF(-wall_px / 2, -height_px, wall_px, height_px + 1)
        brush = QBrush(QColor(WALL_COLOR))
        pen = QPen(QColor(WALL_COLOR).darker(130), 1)
        self._wall_item = self._scene.addRect(rect, pen, brush)
        self._wall_item.setZValue(0)

        # height tick marks every 5 m
        tick_pen = QPen(QColor(TEXT_PRIMARY).darker(160), 1, Qt.DotLine)
        label_font = QFont("monospace", 7)
        for h in range(0, 31, 5):
            y = -h * PIXELS_PER_METRE
            line = self._scene.addLine(
                -wall_px / 2, y, wall_px / 2, y, tick_pen
            )
            line.setZValue(1)
            txt = self._scene.addSimpleText(f"{h}m", label_font)
            txt.setPos(-wall_px / 2 - 30, y - 7)
            txt.setBrush(QBrush(QColor(TEXT_PRIMARY).darker(140)))
            txt.setZValue(1)

    def _fit_initial(self) -> None:
        self.fitInView(
            QRectF(
                -WALL_WIDTH_M / 2 * PIXELS_PER_METRE - 40,
                -15 * PIXELS_PER_METRE,
                WALL_WIDTH_M * PIXELS_PER_METRE + 80,
                15 * PIXELS_PER_METRE + 20,
            ),
            Qt.KeepAspectRatio,
        )

    # ── gear management ──────────────────────────────────────────────────────

    def load_gear(self, gear_items: list["GearItem"]) -> None:
        """Replace all gear items on the canvas."""
        for item in list(self._gear_items.values()):
            self._scene.removeItem(item)
        self._gear_items.clear()

        for idx, gi in enumerate(gear_items):
            self._add_gear_item(idx, gi)

        self._redraw_rope(gear_items)

    def _add_gear_item(self, idx: int, gi: "GearItem") -> None:
        kind = gi.kind
        label = gi.label or f"{kind[0].upper()}{idx + 1}"
        if kind == "bolt":
            item: _GearBase = BoltItem(idx, label)
        elif kind == "cam":
            item = CamItem(idx, label)
        else:
            item = NutItem(idx, label)
        pos = metres_to_scene(gi.height_m, gi.x_offset)
        item.setPos(pos)
        self._scene.addItem(item)
        self._gear_items[idx] = item

    def add_gear_item(self, idx: int, gi: "GearItem") -> None:
        self._add_gear_item(idx, gi)

    def remove_gear_item(self, idx: int) -> None:
        item = self._gear_items.pop(idx, None)
        if item is not None:
            self._scene.removeItem(item)

    def set_climber_height(self, height_m: float) -> None:
        if self._climber_item is None:
            self._climber_item = ClimberItem()
            self._scene.addItem(self._climber_item)
        self._climber_item.setPos(metres_to_scene(height_m, 0.0))

    # ── rope path ────────────────────────────────────────────────────────────

    def _redraw_rope(self, gear_items: list["GearItem"]) -> None:
        if self._rope_item is not None:
            self._scene.removeItem(self._rope_item)
            self._rope_item = None

        if not gear_items:
            return

        path = QPainterPath()
        # Start at ground (belay)
        path.moveTo(0, 0)
        for gi in sorted(gear_items, key=lambda g: g.height_m):
            path.lineTo(metres_to_scene(gi.height_m, gi.x_offset))

        pen = QPen(QColor(ROPE_COLOR), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        self._rope_item = self._scene.addPath(path, pen)
        self._rope_item.setZValue(5)

    def update_rope(self, gear_items: list["GearItem"]) -> None:
        self._redraw_rope(gear_items)

    # ── force arrows ─────────────────────────────────────────────────────────

    def show_force_arrows(self, gear_items: list["GearItem"], forces_kn: list[float]) -> None:
        self._clear_force_arrows()
        max_f = max(forces_kn) if forces_kn else 1.0
        for gi, f in zip(gear_items, forces_kn):
            if f <= 0:
                continue
            length = (f / max_f) * 40.0
            pos = metres_to_scene(gi.height_m, gi.x_offset)
            # Arrow pointing up (force pulls anchor upward)
            pen = QPen(QColor("#f38ba8"), 2)
            line = self._scene.addLine(
                pos.x(), pos.y(), pos.x(), pos.y() - length, pen
            )
            line.setZValue(15)
            self._force_arrows.append(line)

    def _clear_force_arrows(self) -> None:
        for arrow in self._force_arrows:
            self._scene.removeItem(arrow)
        self._force_arrows.clear()

    # ── fall animation ────────────────────────────────────────────────────────

    def play_fall_animation(self, result: "FallResult", climber_height_m: float) -> None:
        """Animate the climber falling based on force-time curve."""
        if self._climber_item is None:
            self.set_climber_height(climber_height_m)

        fall_dist = result.fall_distance_m
        n_frames = min(len(result.force_curve_kn), 120)
        step = max(1, len(result.force_curve_kn) // n_frames)
        self._anim_frames = [
            climber_height_m - (i / n_frames) * fall_dist
            for i in range(n_frames + 1)
        ]
        self._anim_index = 0
        self._anim_timer.timeout.connect(self._advance_frame)
        self._anim_timer.start(16)  # ~60 fps

    def _advance_frame(self) -> None:
        if self._anim_index >= len(self._anim_frames):
            self._anim_timer.stop()
            try:
                self._anim_timer.timeout.disconnect(self._advance_frame)
            except RuntimeError:
                pass
            return
        h = self._anim_frames[self._anim_index]
        self.set_climber_height(max(0.0, h))
        self._anim_index += 1

    def stop_animation(self) -> None:
        self._anim_timer.stop()

    # ── zoom / pan ────────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.RubberBandDrag)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key_F:
            self._fit_initial()
        elif event.key() == Qt.Key_Delete:
            for item in self._scene.selectedItems():
                if isinstance(item, _GearBase):
                    self._scene.gear_selected.emit(item.gear_index)
        super().keyPressEvent(event)
