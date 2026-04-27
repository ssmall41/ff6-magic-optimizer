import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_game_data_has_required_keys():
    r = client.get("/api/game-data")
    assert r.status_code == 200
    data = r.json()
    assert "characters" in data
    assert "espers" in data
    assert "spells" in data
    assert len(data["characters"]) == 14
    assert len(data["espers"]) > 0
    assert len(data["spells"]) > 0


def test_optimize_all_learned():
    r = client.post("/api/optimize", json={
        "party": [
            {"character_id": "terra", "progress": {s["id"]: 100 for s in client.get("/api/game-data").json()["spells"]}}
        ],
        "available_esper_ids": ["ramuh"],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "all_learned"
    assert body["total_ap"] == 0


def test_optimize_basic():
    r = client.post("/api/optimize", json={
        "party": [{"character_id": "terra", "progress": {"fire": 0}}],
        "available_esper_ids": ["ifrit"],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "optimal"
    assert body["total_ap"] > 0
    assert isinstance(body["schedule"], list)
    assert isinstance(body["allocations"], list)


def test_optimize_empty_party_422():
    r = client.post("/api/optimize", json={
        "party": [],
        "available_esper_ids": ["ramuh"],
    })
    assert r.status_code == 422


def test_optimize_empty_espers_422():
    r = client.post("/api/optimize", json={
        "party": [{"character_id": "terra", "progress": {}}],
        "available_esper_ids": [],
    })
    assert r.status_code == 422


def test_optimize_schedule_no_conflicts():
    """Schedule phases must not assign the same real esper to two characters."""
    r = client.post("/api/optimize", json={
        "party": [
            {"character_id": "terra", "progress": {}},
            {"character_id": "locke", "progress": {}},
        ],
        "available_esper_ids": ["ifrit", "ramuh", "shiva"],
    })
    assert r.status_code == 200
    body = r.json()
    for phase in body["schedule"]:
        real = [e for e in phase["assignments"].values() if e is not None]
        assert len(real) == len(set(real)), f"Conflict in phase {phase}"
