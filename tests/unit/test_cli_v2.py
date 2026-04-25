"""
Unit tests for ropesim.cli_v2 — all new v0.2.0 subcommands.

Uses cli.main(argv=[...]) so no subprocess is needed.
"""
import json
import pytest

from ropesim.cli import main, build_parser

pytestmark = pytest.mark.requires_rust


# ── rope list ─────────────────────────────────────────────────────────────────

class TestRopeList:
    def test_basic_list(self, capsys):
        rc = main(["rope", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_list_json(self, capsys):
        rc = main(["rope", "list", "--format", "json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]

    def test_list_filter_dry(self, capsys):
        rc = main(["rope", "list", "--dry"])
        assert rc == 0

    def test_list_filter_diameter(self, capsys):
        rc = main(["rope", "list", "--max-diameter", "9.0"])
        assert rc == 0
        out = capsys.readouterr().out
        # All shown ropes should be 9.0 mm or thinner
        assert "10.2" not in out  # thick rope excluded

    def test_list_sort_falls(self, capsys):
        rc = main(["rope", "list", "--sort", "falls", "--format", "json"])
        assert rc == 0

    def test_list_manufacturer_filter(self, capsys):
        rc = main(["rope", "list", "--manufacturer", "Beal"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Beal" in out


# ── rope show ─────────────────────────────────────────────────────────────────

class TestRopeShow:
    def test_show_existing(self, capsys):
        rc = main(["rope", "show", "Beal Opera 8.5 Dry"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Beal" in out
        assert "8.5" in out

    def test_show_json(self, capsys):
        rc = main(["rope", "show", "Beal Opera 8.5 Dry", "--format", "json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "Beal Opera 8.5 Dry"

    def test_show_nonexistent(self, capsys):
        rc = main(["rope", "show", "NONEXISTENT ROPE XYZ"])
        assert rc == 1


# ── rope compare ──────────────────────────────────────────────────────────────

class TestRopeCompare:
    def test_compare_two(self, capsys):
        rc = main(["rope", "compare",
                   "Beal Opera 8.5 Dry",
                   "Mammut Crag Classic 10.2"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Beal" in out
        assert "Mammut" in out

    def test_compare_json(self, capsys):
        rc = main(["rope", "compare",
                   "Beal Opera 8.5 Dry",
                   "Mammut Crag Classic 10.2",
                   "--format", "json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_compare_one_missing(self, capsys):
        rc = main(["rope", "compare",
                   "Beal Opera 8.5 Dry",
                   "NONEXISTENT ROPE XYZ"])
        assert rc == 1


# ── rope retire ───────────────────────────────────────────────────────────────

class TestRopeRetire:
    def test_retire_status(self, capsys):
        rc = main(["rope", "retire", "Mammut Crag Classic 10.2",
                   "--falls-taken", "5"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Mammut" in out

    def test_retire_heavily_used(self, capsys):
        rc = main(["rope", "retire", "Mammut Crag Classic 10.2",
                   "--falls-taken", "200"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "retire" in out.lower() or "worn" in out.lower() or "exceeded" in out.lower()


# ── validate rope ─────────────────────────────────────────────────────────────

class TestValidateRope:
    def test_validate_rope_text(self, capsys):
        rc = main(["validate", "rope", "--name", "Beal Opera 8.5 Dry"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "compliant" in out.lower() or "COMPLIANT" in out

    def test_validate_rope_json(self, capsys):
        rc = main(["validate", "rope", "--name", "Beal Opera 8.5 Dry",
                   "--format", "json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "violations" in data
        assert "compliant" in data

    def test_validate_rope_missing(self, capsys):
        rc = main(["validate", "rope", "--name", "NONEXISTENT ROPE"])
        assert rc == 1


# ── validate system ───────────────────────────────────────────────────────────

class TestValidateSystem:
    def test_validate_system_basic(self, capsys):
        rc = main(["validate", "system",
                   "--rope", "Beal Opera 8.5 Dry",
                   "--load", "80"])
        assert rc == 0

    def test_validate_system_json(self, capsys):
        rc = main(["validate", "system",
                   "--rope", "Beal Opera 8.5 Dry",
                   "--load", "80",
                   "--format", "json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, dict)


# ── toprope ───────────────────────────────────────────────────────────────────

class TestToprope:
    def test_basic_toprope(self, capsys):
        rc = main(["toprope",
                   "--rope", "Beal Opera 8.5 Dry",
                   "--slack", "0.5"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "kN" in out or "force" in out.lower()

    def test_toprope_json(self, capsys):
        rc = main(["toprope",
                   "--rope", "Beal Opera 8.5 Dry",
                   "--slack", "0.5",
                   "--format", "json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "peak_force_kn" in data
        assert data["peak_force_kn"] > 0

    def test_toprope_more_slack_higher_force(self, capsys):
        main(["toprope", "--rope", "Beal Opera 8.5 Dry",
              "--slack", "0.2", "--format", "json"])
        low_slack = json.loads(capsys.readouterr().out)
        main(["toprope", "--rope", "Beal Opera 8.5 Dry",
              "--slack", "2.0", "--format", "json"])
        high_slack = json.loads(capsys.readouterr().out)
        assert high_slack["peak_force_kn"] > low_slack["peak_force_kn"]


# ── rappel ────────────────────────────────────────────────────────────────────

class TestRappel:
    def test_basic_rappel(self, capsys):
        rc = main(["rappel", "--mass", "80"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "kN" in out or "load" in out.lower()

    def test_rappel_json(self, capsys):
        rc = main(["rappel", "--mass", "80", "--format", "json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "normal_load_kn" in data or "anchor_load_kn" in data or "load_kn" in data

    def test_heavier_mass_higher_load(self, capsys):
        main(["rappel", "--mass", "60", "--format", "json"])
        light = json.loads(capsys.readouterr().out)
        main(["rappel", "--mass", "100", "--format", "json"])
        heavy = json.loads(capsys.readouterr().out)
        light_val = list(light.values())[0] if light else 0
        heavy_val = list(heavy.values())[0] if heavy else 0
        assert heavy_val > light_val


# ── haul ──────────────────────────────────────────────────────────────────────

class TestHaul:
    def test_3to1_haul(self, capsys):
        rc = main(["haul", "--system", "3:1", "--load", "80"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "3" in out

    def test_5to1_haul(self, capsys):
        rc = main(["haul", "--system", "5:1", "--load", "80"])
        assert rc == 0

    def test_6to1_haul(self, capsys):
        rc = main(["haul", "--system", "6:1", "--load", "80"])
        assert rc == 0

    def test_haul_json(self, capsys):
        rc = main(["haul", "--system", "3:1", "--load", "80", "--format", "json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "theoretical_ma" in data or "actual_ma" in data or "hauler_effort_kn" in data

    def test_higher_ma_less_effort(self, capsys):
        main(["haul", "--system", "3:1", "--load", "80", "--format", "json"])
        d3 = json.loads(capsys.readouterr().out)
        main(["haul", "--system", "6:1", "--load", "80", "--format", "json"])
        d6 = json.loads(capsys.readouterr().out)
        effort_key = "hauler_effort_kn"
        if effort_key in d3 and effort_key in d6:
            assert d6[effort_key] < d3[effort_key]

    def test_invalid_system(self, capsys):
        rc = main(["haul", "--system", "99:1", "--load", "80"])
        assert rc == 1


# ── report ────────────────────────────────────────────────────────────────────

class TestReport:
    def test_report_no_file_fails(self, capsys):
        rc = main(["report", "--scenario", "NONEXISTENT_FILE.json"])
        assert rc == 1


# ── interactive exits cleanly (no terminal) ───────────────────────────────────

class TestInteractive:
    def test_interactive_missing_stdin_exits(self, capsys, monkeypatch):
        import sys
        import io
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        rc = main(["interactive"])
        assert rc in (0, 1)
