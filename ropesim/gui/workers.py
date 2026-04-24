"""Background worker threads for off-main-thread simulation."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class SimulationWorker(QThread):
    """Runs simulate_fall() off the main thread to keep the UI responsive."""

    result_ready = Signal(object)   # FallResult
    error        = Signal(str)
    progress     = Signal(int)      # 0–100

    def __init__(self, scenario, climber_height_m: float, parent=None):
        super().__init__(parent)
        self._scenario        = scenario
        self._climber_height_m = climber_height_m

    def run(self) -> None:
        try:
            self.progress.emit(10)
            result = self._scenario.simulate_fall(self._climber_height_m)
            self.progress.emit(100)
            self.result_ready.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class SweepWorker(QThread):
    """Runs sweep_fall_positions() off the main thread."""

    sweep_ready = Signal(object)    # SweepResult
    error       = Signal(str)
    progress    = Signal(int)       # 0–100

    def __init__(
        self,
        scenario,
        height_range: tuple[float, float] | None = None,
        steps: int = 40,
        parent=None,
    ):
        super().__init__(parent)
        self._scenario    = scenario
        self._height_range = height_range
        self._steps       = steps

    def run(self) -> None:
        try:
            self.progress.emit(5)
            kwargs: dict = {"steps": self._steps}
            if self._height_range is not None:
                kwargs["height_range"] = self._height_range
            result = self._scenario.sweep_fall_positions(**kwargs)
            self.progress.emit(100)
            self.sweep_ready.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class ZipperWorker(QThread):
    """Runs simulate_zipper() off the main thread."""

    result_ready = Signal(object)   # ZipperResult
    error        = Signal(str)

    def __init__(self, scenario, climber_height_m: float, parent=None):
        super().__init__(parent)
        self._scenario        = scenario
        self._climber_height_m = climber_height_m

    def run(self) -> None:
        try:
            result = self._scenario.simulate_zipper(self._climber_height_m)
            self.result_ready.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
