"""
Unit tests for ropesim.replay.SimulationReplay.

SimulationReplay wraps a SimFrameData object. Since we cannot easily construct
a real SimFrameData without the Rust extension, we use a lightweight fake
that mirrors the required interface.
"""
import pytest
from ropesim.replay import SimulationReplay


# ── Fake frame / frame-data for pure-Python tests ────────────────────────────

class _FakeFrame:
    def __init__(self, timestamp_ms: float, anchor_force_kn: float):
        self.timestamp_ms    = timestamp_ms
        self.anchor_force_kn = anchor_force_kn
        self.link_positions  = [[0.0, float(i), 0.0] for i in range(5)]


class _FakeFrameData:
    def __init__(self, frames, dt_seconds=1/60, total_time_seconds=1.0):
        self.frames              = frames
        self.dt_seconds          = dt_seconds
        self.total_time_seconds  = total_time_seconds

    def peak_anchor_force(self):
        return max(f.anchor_force_kn for f in self.frames)

    def force_curve_numpy(self):
        return [f.anchor_force_kn for f in self.frames]


def _make_replay(n=10, peak_at=5):
    frames = [
        _FakeFrame(
            timestamp_ms=i * (1000 / 60),
            anchor_force_kn=float(i) if i <= peak_at else float(2 * peak_at - i),
        )
        for i in range(n)
    ]
    data = _FakeFrameData(frames, dt_seconds=1/60, total_time_seconds=n/60)
    return SimulationReplay(data)


# ── Basic construction ────────────────────────────────────────────────────────

class TestSimulationReplayConstruction:
    def test_len(self):
        r = _make_replay(10)
        assert len(r) == 10

    def test_total_frames(self):
        r = _make_replay(7)
        assert r.total_frames() == 7

    def test_dt_seconds(self):
        r = _make_replay()
        assert r.dt_seconds == pytest.approx(1/60, rel=0.01)

    def test_total_time_seconds(self):
        r = _make_replay(n=6)
        assert r.total_time_seconds == pytest.approx(6/60, rel=0.01)

    def test_repr_contains_frames(self):
        r = _make_replay(8)
        assert "8" in repr(r)


# ── Frame access ──────────────────────────────────────────────────────────────

class TestFrameAccess:
    def test_frame_zero(self):
        r = _make_replay(5)
        f = r.frame(0)
        assert f.timestamp_ms == pytest.approx(0.0)

    def test_frame_last(self):
        r = _make_replay(5)
        f = r.frame(4)
        assert f is not None

    def test_frame_out_of_range_raises(self):
        r = _make_replay(5)
        with pytest.raises(IndexError):
            r.frame(5)

    def test_frame_negative_raises(self):
        r = _make_replay(5)
        with pytest.raises(IndexError):
            r.frame(-1)

    def test_getitem_works(self):
        r = _make_replay(5)
        assert r[0].timestamp_ms == r.frame(0).timestamp_ms

    def test_getitem_out_of_range_raises(self):
        r = _make_replay(5)
        with pytest.raises(IndexError):
            _ = r[10]


# ── at_time binary search ─────────────────────────────────────────────────────

class TestAtTime:
    def test_at_time_zero(self):
        r = _make_replay(10)
        f = r.at_time(0.0)
        assert f.timestamp_ms == pytest.approx(0.0)

    def test_at_time_returns_nearest(self):
        r = _make_replay(10)
        # Frame timestamps are multiples of 1000/60 ~ 16.67 ms
        dt = 1000 / 60
        # Query halfway between frame 3 and frame 4
        t_query = 3 * dt + dt / 2
        f = r.at_time(t_query)
        # Should be one of frame 3 or 4
        assert f.timestamp_ms in [pytest.approx(3 * dt), pytest.approx(4 * dt)]

    def test_at_time_past_end_returns_last(self):
        r = _make_replay(5)
        f = r.at_time(999999.0)
        assert f is r.frame(4)

    def test_at_time_before_start_returns_first(self):
        r = _make_replay(5)
        f = r.at_time(-100.0)
        assert f is r.frame(0)

    def test_at_time_empty_raises(self):
        data = _FakeFrameData([], dt_seconds=1/60, total_time_seconds=0.0)
        r = SimulationReplay(data)
        with pytest.raises(ValueError):
            r.at_time(0.0)


# ── Analysis helpers ──────────────────────────────────────────────────────────

class TestAnalysisHelpers:
    def test_peak_force_frame(self):
        r = _make_replay(n=10, peak_at=5)
        idx = r.peak_force_frame()
        # peak_at=5 → frame 5 has force 5.0, which is max for triangle shape
        assert idx == 5

    def test_peak_anchor_force_kn(self):
        r = _make_replay(n=10, peak_at=5)
        peak = r.peak_anchor_force_kn()
        assert peak == pytest.approx(5.0)

    def test_first_catch_frame_default_threshold(self):
        frames = [_FakeFrame(i * 16.0, 0.0) for i in range(5)]
        frames[2].anchor_force_kn = 0.1  # first non-zero
        data = _FakeFrameData(frames)
        r = SimulationReplay(data)
        assert r.first_catch_frame() == 2

    def test_first_catch_frame_never_taut(self):
        frames = [_FakeFrame(i * 16.0, 0.0) for i in range(5)]
        data = _FakeFrameData(frames)
        r = SimulationReplay(data)
        assert r.first_catch_frame() == 0

    def test_first_catch_frame_custom_threshold(self):
        frames = [_FakeFrame(i * 16.0, float(i) * 0.5) for i in range(10)]
        data = _FakeFrameData(frames)
        r = SimulationReplay(data)
        # threshold=2.0 → first frame with force >= 2.0 is frame 4 (force=2.0)
        # threshold=2.0: uses strict >, first frame with force > 2.0 is frame 5 (force=2.5)
        idx = r.first_catch_frame(threshold_kn=2.0)
        assert idx == 5
    def test_force_curve_length(self):
        r = _make_replay(8)
        curve = r.force_curve()
        assert len(curve) == 8

    def test_force_curve_values(self):
        r = _make_replay(5, peak_at=2)
        curve = r.force_curve()
        assert all(isinstance(v, float) for v in curve)

    def test_peak_force_frame_empty_raises(self):
        data = _FakeFrameData([], dt_seconds=1/60, total_time_seconds=0.0)
        r = SimulationReplay(data)
        with pytest.raises(ValueError):
            r.peak_force_frame()
