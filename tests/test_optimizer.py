import math
import pytest
from fastapi.testclient import TestClient
from backend.optimizer import optimize
from backend.main import app
from backend.game_data import load_espers, load_spells

client = TestClient(app)


def run(party, esper_ids):
    return optimize(party, esper_ids, load_espers(), load_spells())


def all_learned_except(spell_ids_to_zero: dict[str, int]) -> dict:
    """Return a progress dict with everything at 100 except the given spells."""
    prog = {s["id"]: 100 for s in load_spells()}
    prog.update(spell_ids_to_zero)
    return prog


# ── Basic correctness ────────────────────────────────────────

def test_all_learned_returns_zero():
    """If all spells are at 100, no AP is needed."""
    prog = {s["id"]: 100 for s in load_spells()}
    party = [{"character_id": "terra", "progress": prog}]
    result = run(party, ["ramuh"])
    assert result.status == "all_learned"
    assert result.total_ap == 0


def test_single_char_single_esper():
    """Terra needs only Fire from Ifrit (rate x10). Remaining=100 → 100/10=10 AP."""
    party = [{"character_id": "terra", "progress": all_learned_except({"fire": 0})}]
    result = run(party, ["ifrit"])
    assert result.status == "optimal"
    assert result.total_ap == 10


def test_partial_progress_reduces_ap():
    """Terra has 50 progress on Fire. 50 remaining / rate 10 = 5 AP."""
    party = [{"character_id": "terra", "progress": all_learned_except({"fire": 50})}]
    result = run(party, ["ifrit"])
    assert result.status == "optimal"
    assert result.total_ap == 5


def test_two_chars_shared_esper():
    """
    Terra and Locke both need Fire (Ifrit x10) only.
    Terra needs 100 AP-progress → 10 AP on Ifrit.
    Locke needs  80 AP-progress →  8 AP on Ifrit.
    They share Ifrit, so min T = 10 + 8 = 18 AP.
    """
    party = [
        {"character_id": "terra", "progress": all_learned_except({"fire": 0})},
        {"character_id": "locke", "progress": all_learned_except({"fire": 20})},
    ]
    result = run(party, ["ifrit"])
    assert result.status == "optimal"
    assert result.total_ap == 18


def test_two_chars_different_espers_parallel():
    """
    Terra needs Fire (Ifrit x10): 10 AP.
    Locke needs Thunder (Ramuh x5): 20 AP.
    No shared esper → they work in parallel. Min T = max(10, 20) = 20 AP.
    """
    party = [
        {"character_id": "terra", "progress": all_learned_except({"fire": 0})},
        {"character_id": "locke", "progress": all_learned_except({"thunder": 0})},
    ]
    result = run(party, ["ifrit", "ramuh"])
    assert result.status == "optimal"
    assert result.total_ap == 20


def test_unlearnable_spell_warned():
    """Quick is only taught by Raiden. With only Ramuh, Quick is unlearnable."""
    party = [{"character_id": "terra", "progress": all_learned_except({"quick": 0})}]
    result = run(party, ["ramuh"])
    assert "quick" in result.unlearnable


def test_no_party_returns_422():
    """Empty party is rejected at the HTTP layer with 422."""
    r = client.post("/api/optimize", json={"party": [], "available_esper_ids": ["ramuh"]})
    assert r.status_code == 422


def test_schedule_has_no_esper_conflicts():
    """No phase should assign the same real esper to two characters."""
    party = [
        {"character_id": "terra", "progress": all_learned_except({"fire": 0, "thunder": 0})},
        {"character_id": "locke", "progress": all_learned_except({"fire": 0, "blizzard": 0})},
        {"character_id": "celes", "progress": all_learned_except({"thunder": 0, "blizzard": 0})},
    ]
    result = run(party, ["ifrit", "ramuh", "shiva"])
    assert result.status == "optimal"
    for phase in result.schedule:
        real = [e for e in phase.assignments.values() if e is not None]
        assert len(real) == len(set(real)), (
            f"Esper conflict in phase {phase.phase}: {phase.assignments}"
        )
