"""
Unit tests for RopeDatabase CRUD operations and the bundled ropes.json.
"""
import json
import tempfile
from pathlib import Path

import pytest

from ropesim.rope import Rope, RopeDatabase, RopeSpec, RopeType, RopeStandard


def _tmp_db(initial_specs: list[RopeSpec] | None = None) -> RopeDatabase:
    """Create an isolated database backed by a temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    path = Path(tmp.name)
    tmp.close()
    db = RopeDatabase(path=path)
    if initial_specs:
        db.save(initial_specs)
    return db


def _sample_spec(name: str = "Test Rope 9.5") -> RopeSpec:
    return RopeSpec(
        name=name,
        manufacturer="TestCo",
        rope_type=RopeType.SINGLE,
        standard=RopeStandard.BOTH,
        diameter_mm=9.5,
        weight_gpm=60.0,
        sheath_percentage=40.0,
        impact_force_kn=9.0,
        number_of_falls=7,
        static_elongation_pct=8.0,
        dynamic_elongation_pct=34.0,
        dry_treated=False,
    )


class TestRopeDatabaseCRUD:
    def test_empty_database(self):
        db = _tmp_db()
        assert db.load() == []
        assert len(db) == 0

    def test_add_and_get(self):
        db = _tmp_db()
        spec = _sample_spec()
        db.add(spec)
        retrieved = db.get("Test Rope 9.5")
        assert retrieved is not None
        assert retrieved.name == "Test Rope 9.5"

    def test_add_duplicate_raises(self):
        db = _tmp_db()
        spec = _sample_spec()
        db.add(spec)
        with pytest.raises(ValueError, match="already exists"):
            db.add(spec)

    def test_get_case_insensitive(self):
        db = _tmp_db()
        db.add(_sample_spec("My Rope"))
        assert db.get("my rope") is not None
        assert db.get("MY ROPE") is not None

    def test_get_missing_returns_none(self):
        db = _tmp_db()
        assert db.get("Nonexistent Rope") is None

    def test_remove(self):
        db = _tmp_db()
        db.add(_sample_spec())
        db.remove("Test Rope 9.5")
        assert db.get("Test Rope 9.5") is None

    def test_remove_missing_raises(self):
        db = _tmp_db()
        with pytest.raises(KeyError):
            db.remove("Ghost Rope")

    def test_update(self):
        db = _tmp_db()
        spec = _sample_spec()
        db.add(spec)
        updated = spec.model_copy(update={"impact_force_kn": 10.5})
        db.update("Test Rope 9.5", updated)
        retrieved = db.get("Test Rope 9.5")
        assert retrieved.impact_force_kn == 10.5

    def test_update_missing_raises(self):
        db = _tmp_db()
        with pytest.raises(KeyError):
            db.update("Nonexistent", _sample_spec())

    def test_save_and_reload(self):
        specs = [_sample_spec(f"Rope {i}") for i in range(5)]
        db = _tmp_db(specs)
        loaded = db.load()
        assert len(loaded) == 5
        names = {s.name for s in loaded}
        assert names == {f"Rope {i}" for i in range(5)}

    def test_search_by_type(self):
        db = _tmp_db()
        db.add(_sample_spec("Single A"))
        db.add(
            RopeSpec(
                name="Half B", manufacturer="Co", rope_type=RopeType.HALF,
                standard=RopeStandard.BOTH, diameter_mm=8.2, weight_gpm=44.0,
                sheath_percentage=35.0, impact_force_kn=6.5, number_of_falls=5,
                static_elongation_pct=7.0, dynamic_elongation_pct=30.0,
            )
        )
        singles = db.search(rope_type=RopeType.SINGLE)
        halves  = db.search(rope_type=RopeType.HALF)
        assert len(singles) == 1
        assert len(halves)  == 1

    def test_len(self):
        db = _tmp_db()
        for i in range(4):
            db.add(_sample_spec(f"R{i}"))
        assert len(db) == 4


class TestBundledDatabase:
    """Tests against the real ropes.json shipped with ropesim."""

    def test_bundled_db_loads(self):
        db = RopeDatabase()
        specs = db.load()
        assert len(specs) >= 10, f"Expected ≥10 ropes, got {len(specs)}"

    def test_all_specs_valid(self):
        db = RopeDatabase()
        for spec in db.load():
            violations = type(spec).model_fields  # access on class, not instance (Pydantic v2.11+)
            assert spec.impact_force_kn > 0

    def test_from_db_factory(self):
        rope = Rope.from_db("Beal Opera 8.5 Dry")
        assert rope.spec.manufacturer == "Beal"
        assert rope.spec.diameter_mm == 8.5

    def test_from_db_missing_raises(self):
        with pytest.raises(KeyError):
            Rope.from_db("Definitely Not A Real Rope XYZ123")

    def test_search_dry_only(self):
        results = Rope.search(dry_only=True)
        assert len(results) >= 1
        for r in results:
            assert r.spec.dry_treated is True

    def test_search_by_diameter_range(self):
        results = Rope.search(diameter_range=(9.0, 9.5))
        for r in results:
            assert 9.0 <= r.spec.diameter_mm <= 9.5

    def test_rope_json_roundtrip(self):
        rope = Rope.from_db("Mammut Crag Classic 10.2")
        json_str = rope.to_json()
        recovered = Rope.from_json(json_str)
        assert recovered.spec.name == rope.spec.name
        assert recovered.spec.impact_force_kn == rope.spec.impact_force_kn
