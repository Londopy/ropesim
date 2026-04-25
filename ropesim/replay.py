"""
ropesim.replay
==============
SimulationReplay: frame-by-frame access to SimFrameData from a Rapier
simulation run.  Used by the GUI for smooth playback at any speed.

Typical usage::

    world = scenario.build_rapier_world()
    frame_data = world.step_n(720, 1/240)

    replay = SimulationReplay(frame_data)
    print(replay.total_frames())          # 720
    f = replay.at_time(500.0)             # interpolated frame at t=500ms
    peak_idx = replay.peak_force_frame()  # frame with highest anchor force
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid circular import at runtime; only used for type hints.
    from ropesim._rustcore import SimFrameData, SimFrame


class SimulationReplay:
    """
    Wraps a :class:`SimFrameData` object and provides convenient frame-indexed
    access for GUI playback and offline analysis.

    All frame indices are zero-based.  Timestamps are in milliseconds matching
    the ``SimFrame.timestamp_ms`` field.
    """

    def __init__(self, data: "SimFrameData") -> None:
        self._data = data
        self._frames = data.frames  # cached list reference

    # ── Frame access ─────────────────────────────────────────────────────────

    def frame(self, n: int) -> "SimFrame":
        """Return the ``n``-th frame (zero-based)."""
        if not 0 <= n < len(self._frames):
            raise IndexError(
                f"Frame index {n} out of range (0..{len(self._frames) - 1})"
            )
        return self._frames[n]

    def total_frames(self) -> int:
        """Total number of recorded frames."""
        return len(self._frames)

    def at_time(self, t_ms: float) -> "SimFrame":
        """
        Return the frame whose timestamp is closest to ``t_ms``.

        No interpolation between frames is performed -- the nearest stored
        frame is returned.  For smooth animation, pass the pre-simulated
        ``frame_data`` and step by one frame at a time.
        """
        frames = self._frames
        if not frames:
            raise ValueError("SimulationReplay has no frames")

        # Binary-search style: find first frame at or past t_ms
        lo, hi = 0, len(frames) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if frames[mid].timestamp_ms < t_ms:
                lo = mid + 1
            else:
                hi = mid

        # lo is the first frame >= t_ms; pick nearest of lo and lo-1
        if lo == 0:
            return frames[0]
        before = frames[lo - 1]
        after  = frames[lo]
        if abs(after.timestamp_ms - t_ms) < abs(before.timestamp_ms - t_ms):
            return after
        return before

    # ── Analysis helpers ─────────────────────────────────────────────────────

    def peak_force_frame(self) -> int:
        """Return the index of the frame with the highest anchor force."""
        frames = self._frames
        if not frames:
            raise ValueError("SimulationReplay has no frames")
        return max(range(len(frames)), key=lambda i: frames[i].anchor_force_kn)

    def first_catch_frame(self, threshold_kn: float = 0.05) -> int:
        """
        Return the index of the first frame where the rope goes taut.

        "Taut" is defined as anchor force exceeding ``threshold_kn`` (default
        0.05 kN) -- this filters out numerical noise during free fall.
        Returns 0 if the rope never goes taut.
        """
        for i, f in enumerate(self._frames):
            if f.anchor_force_kn > threshold_kn:
                return i
        return 0

    @property
    def dt_seconds(self) -> float:
        """Simulation timestep (seconds)."""
        return self._data.dt_seconds

    @property
    def total_time_seconds(self) -> float:
        """Total simulated time (seconds)."""
        return self._data.total_time_seconds

    def peak_anchor_force_kn(self) -> float:
        """Maximum anchor force across all frames (kN)."""
        return self._data.peak_anchor_force()

    def force_curve(self) -> list[float]:
        """Anchor force at every frame as a flat list (kN)."""
        return self._data.force_curve_numpy()

    # ── Dunder ───────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._frames)

    def __getitem__(self, idx: int) -> "SimFrame":
        return self.frame(idx)

    def __repr__(self) -> str:
        return (
            f"SimulationReplay("
            f"frames={self.total_frames}, "
            f"peak={self.peak_anchor_force_kn:.2f}kN)"
        )
