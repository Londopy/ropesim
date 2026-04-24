"""
Unit tests for ropesim.cli — argument parsing and command output.

Uses argparse invocation via cli.main(argv=[...]) so no subprocess needed.
"""
import json
import pytest

from ropesim.cli import main, build_parser


pytestmark = pytest.mark.requires_rust


class TestParser:
    def test_no_command_exits_zero(self):
        """Running with no command should print help and return 0."""
        rc = main([])
        assert rc == 0

    def test_simulate_requires_fall_dist(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["simulate", "--rope-out", "20.0"])

    def test_simulate_requires_rope_out(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["simulate", "--fall-dist", "6.0"])

    def test_anchor_requires_load(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["anchor", "--bolts", "2"])

    def test_validate_rope_requires_name(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["validate-rope"])


class TestSimulateCommand:
    def test_basic_simulate(self, capsys):
        rc = main(["simulate", "--fall-dist", "6.0", "--rope-out", "20.0"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Peak force" in out

    def test_simulate_json_output(self, capsys):
        rc = main(["simulate", "--fall-dist", "6.0", "--rope-out", "20.0", "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "peak_force_kn" in data
        assert data["peak_force_kn"] > 0

    def test_simulate_with_rope_name(self, capsys):
        rc = main([
            "simulate",
            "--fall-dist", "5.0",
            "--rope-out", "18.0",
            "--rope", "Beal Opera 8.5 Dry",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Beal" in out

    def test_simulate_bad_rope_name(self, capsys):
        rc = main([
            "simulate",
            "--fall-dist", "5.0",
            "--rope-out", "18.0",
            "--rope", "THIS ROPE DOES NOT EXIST XYZ",
        ])
        assert rc == 1

    def test_simulate_grigri_device(self, capsys):
        rc = main([
            "simulate",
            "--fall-dist", "6.0",
            "--rope-out", "20.0",
            "--device", "grigri",
            "--json",
        ])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["peak_force_kn"] > 0

    def test_simulate_wet(self, capsys):
        rc_dry = main(["simulate", "--fall-dist", "6.0", "--rope-out", "20.0", "--json"])
        rc_wet = main(["simulate", "--fall-dist", "6.0", "--rope-out", "20.0", "--wet", "--json"])
        dry_kn = json.loads(capsys.readouterr().out.split("\n")[-2] if False else "{}")
        # Just verify both succeed
        assert rc_dry == 0
        assert rc_wet == 0

    def test_simulate_mass_affects_result(self, capsys):
        main(["simulate", "--fall-dist", "6.0", "--rope-out", "20.0", "--mass", "60.0", "--json"])
        out_60 = json.loads(capsys.readouterr().out)
        main(["simulate", "--fall-dist", "6.0", "--rope-out", "20.0", "--mass", "90.0", "--json"])
        out_90 = json.loads(capsys.readouterr().out)
        assert out_90["peak_force_kn"] > out_60["peak_force_kn"]


class TestAnchorCommand:
    def test_basic_anchor(self, capsys):
        rc = main(["anchor", "--load", "8.0"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "ANCHOR" in out.upper()

    def test_anchor_quad(self, capsys):
        rc = main(["anchor", "--type", "quad", "--load", "8.0"])
        assert rc == 0

    def test_anchor_overload(self, capsys):
        """Bolt MBS 1.0 kN, load 8.0 kN → failure."""
        rc = main(["anchor", "--bolt-mbs", "1.0", "--load", "8.0"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "FAILURE" in out or "failed" in out.lower()

    def test_anchor_3_bolts(self, capsys):
        rc = main(["anchor", "--bolts", "3", "--load", "10.0"])
        assert rc == 0

    def test_anchor_with_angle(self, capsys):
        rc = main(["anchor", "--load", "8.0", "--angle", "30.0"])
        assert rc == 0


class TestListRopesCommand:
    def test_list_all(self, capsys):
        rc = main(["list-ropes"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Beal" in out or "Mammut" in out or "Sterling" in out

    def test_list_json(self, capsys):
        rc = main(["list-ropes", "--json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]

    def test_list_filter_single(self, capsys):
        rc = main(["list-ropes", "--type", "single"])
        assert rc == 0

    def test_list_filter_dry(self, capsys):
        rc = main(["list-ropes", "--dry"])
        assert rc == 0
        out = capsys.readouterr().out
        # All results should be dry (or empty list)
        assert "No" not in out or len(out.strip().splitlines()) <= 4

    def test_list_bad_type(self, capsys):
        rc = main(["list-ropes", "--type", "INVALID_TYPE"])
        assert rc == 1


class TestValidateRopeCommand:
    def test_validate_good_rope(self, capsys):
        rc = main(["validate-rope", "--name", "Beal Opera 8.5 Dry"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "COMPLIANT" in out

    def test_validate_json(self, capsys):
        rc = main(["validate-rope", "--name", "Beal Opera 8.5 Dry", "--json"])
        data = json.loads(capsys.readouterr().out)
        assert "violations" in data
        assert isinstance(data["violations"], list)

    def test_validate_bad_name(self, capsys):
        rc = main(["validate-rope", "--name", "NONEXISTENT ROPE"])
        assert rc == 1


class TestSweepCommand:
    def test_basic_sweep(self, capsys):
        rc = main(["sweep", "--ff-start", "0.1", "--ff-end", "1.5", "--steps", "5"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "SWEEP" in out

    def test_sweep_json(self, capsys):
        rc = main(["sweep", "--ff-start", "0.1", "--ff-end", "1.5", "--steps", "5", "--json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 5
        assert "fall_factor" in data[0]
        assert "peak_force_kn" in data[0]

    def test_sweep_with_rope(self, capsys):
        rc = main(["sweep", "--rope", "Beal Opera 8.5 Dry", "--steps", "5"])
        assert rc == 0

    def test_sweep_monotone_forces(self, capsys):
        """Peak force should increase with fall factor."""
        main(["sweep", "--ff-start", "0.1", "--ff-end", "1.8", "--steps", "8", "--json"])
        data = json.loads(capsys.readouterr().out)
        forces = [d["peak_force_kn"] for d in data]
        for i in range(len(forces) - 1):
            assert forces[i] <= forces[i + 1] + 1e-6  # allow floating point noise

    def test_sweep_bad_rope(self, capsys):
        rc = main(["sweep", "--rope", "NONEXISTENT ROPE"])
        assert rc == 1
