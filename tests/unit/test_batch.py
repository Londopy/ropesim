"""
Unit tests for ropesim._rustcore batch sweep functions.
"""
import pytest
import numpy as np

pytestmark = pytest.mark.requires_rust


@pytest.fixture
def rc():
    from ropesim import _rustcore
    return _rustcore


class TestBatchSweepFallFactors:
    def test_returns_list(self, rc):
        result = rc.batch_sweep_fall_factors(80.0, [0.3, 0.5, 1.0], 40.0, 0.35)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_all_positive(self, rc):
        result = rc.batch_sweep_fall_factors(80.0, [0.1, 0.5, 1.0, 1.5], 40.0, 0.35)
        assert all(f > 0 for f in result)

    def test_monotone_increasing(self, rc):
        """Higher fall factor → higher peak force."""
        ffs = [0.1, 0.5, 1.0, 1.5, 2.0]
        result = rc.batch_sweep_fall_factors(80.0, ffs, 40.0, 0.35)
        for i in range(len(result) - 1):
            assert result[i] <= result[i + 1], f"Force not increasing at ff={ffs[i]}"

    def test_single_value(self, rc):
        result = rc.batch_sweep_fall_factors(80.0, [1.0], 40.0, 0.35)
        assert len(result) == 1
        assert result[0] > 0

    def test_empty_input(self, rc):
        result = rc.batch_sweep_fall_factors(80.0, [], 40.0, 0.35)
        assert result == []

    def test_matches_single_calls(self, rc):
        """Batch result must match sequential compute_impact_force_uiaa calls."""
        ffs = [0.3, 0.7, 1.2]
        batch = rc.batch_sweep_fall_factors(80.0, ffs, 40.0, 0.35)
        for ff, bf in zip(ffs, batch):
            single = rc.compute_impact_force_uiaa(80.0, ff, 40.0, 0.35)
            assert abs(bf - single) < 1e-10


class TestBatchSweepRopeOut:
    def test_returns_correct_length(self, rc):
        result = rc.batch_sweep_rope_out(80.0, 6.0, 5.0, 30.0, 20, 40.0, 0.35)
        assert len(result) == 20

    def test_all_positive(self, rc):
        result = rc.batch_sweep_rope_out(80.0, 6.0, 5.0, 30.0, 10, 40.0, 0.35)
        assert all(f > 0 for f in result)

    def test_longer_rope_lower_ff_lower_force(self, rc):
        """More rope out → lower fall factor → lower peak force."""
        result = rc.batch_sweep_rope_out(80.0, 6.0, 5.0, 50.0, 10, 40.0, 0.35)
        # First point (short rope) should be higher force than last (long rope)
        assert result[0] >= result[-1]

    def test_zero_steps_raises(self, rc):
        with pytest.raises(Exception):
            rc.batch_sweep_rope_out(80.0, 6.0, 5.0, 30.0, 0, 40.0, 0.35)

    def test_zero_rope_raises(self, rc):
        with pytest.raises(Exception):
            rc.batch_sweep_rope_out(80.0, 6.0, 0.0, 30.0, 5, 40.0, 0.35)


class TestParallelForceCurves:
    def test_returns_list_of_lists(self, rc):
        params = [
            (80.0, 6.0, 20.0, 40.0, 0.12, 1.0),
            (70.0, 4.0, 15.0, 35.0, 0.12, 1.0),
        ]
        result = rc.parallel_force_curves(params)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(curve, list) for curve in result)

    def test_each_curve_nonempty(self, rc):
        params = [(80.0, 6.0, 20.0, 40.0, 0.12, 1.0)]
        result = rc.parallel_force_curves(params)
        assert len(result[0]) > 0

    def test_all_values_nonnegative(self, rc):
        params = [(80.0, 6.0, 20.0, 40.0, 0.12, 1.0)]
        result = rc.parallel_force_curves(params)
        assert all(v >= 0 for v in result[0])

    def test_empty_params(self, rc):
        result = rc.parallel_force_curves([])
        assert result == []

    def test_matches_single_curve(self, rc):
        """Parallel result must match sequential compute_force_curve."""
        params = [(80.0, 6.0, 20.0, 40.0, 0.12, 1.0)]
        parallel = rc.parallel_force_curves(params)[0]
        sequential = rc.compute_force_curve(80.0, 6.0, 20.0, 40.0, 0.12, 1.0)
        assert parallel == sequential

    def test_multiple_params_independent(self, rc):
        """Each parallel run must be independent."""
        params = [
            (80.0, 6.0, 20.0, 40.0, 0.12, 1.0),
            (80.0, 12.0, 10.0, 40.0, 0.12, 1.0),  # higher ff
        ]
        result = rc.parallel_force_curves(params)
        # Both curves should be valid
        assert max(result[0]) > 0
        assert max(result[1]) > 0


class TestSweepClimberHeight:
    def test_returns_correct_flat_length(self, rc):
        result = rc.sweep_climber_height(80.0, 0.0, 8.0, 10.0, 20.0, 5, 40.0, 0.35)
        assert isinstance(result, list)
        assert len(result) == 5 * 3  # steps × 3 columns

    def test_heights_in_range(self, rc):
        result = rc.sweep_climber_height(80.0, 0.0, 8.0, 10.0, 20.0, 5, 40.0, 0.35)
        heights = result[0::3]  # every 3rd element starting at 0
        assert all(10.0 <= h <= 20.0 for h in heights)

    def test_fall_distances_positive(self, rc):
        result = rc.sweep_climber_height(80.0, 0.0, 8.0, 10.0, 20.0, 5, 40.0, 0.35)
        fall_dists = result[1::3]
        assert all(fd > 0 for fd in fall_dists)

    def test_peak_forces_positive(self, rc):
        result = rc.sweep_climber_height(80.0, 0.0, 8.0, 10.0, 20.0, 5, 40.0, 0.35)
        forces = result[2::3]
        assert all(f > 0 for f in forces)

    def test_zero_steps_raises(self, rc):
        with pytest.raises(Exception):
            rc.sweep_climber_height(80.0, 0.0, 8.0, 10.0, 20.0, 0, 40.0, 0.35)
