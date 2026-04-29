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
    Locke needs Thundara (Ramuh x2): 50 AP.
    No shared esper → they work in parallel. Min T = max(10, 50) = 50 AP.
    """
    party = [
        {"character_id": "terra", "progress": all_learned_except({"fire": 0})},
        {"character_id": "locke", "progress": all_learned_except({"thundara": 0})},
    ]
    result = run(party, ["ifrit", "ramuh"])
    assert result.status == "optimal"
    assert result.total_ap == 50


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


# ── Fractional AP / integer schedule correctness ─────────────

def _phase_ap_per_char_esper(result) -> dict[tuple[str, str | None], int]:
    """Sum schedule phase APs by (character, esper) pair."""
    earned: dict[tuple[str, str | None], int] = {}
    for phase in result.schedule:
        for char_id, esper_id in phase.assignments.items():
            key = (char_id, esper_id)
            earned[key] = earned.get(key, 0) + phase.ap
    return earned


def test_fractional_rate_no_ap_inflation():
    """
    Siren teaches Fire at rate 6, so each character needs ceil(100/6) = 17 AP on
    Siren (not 16.666...).  That fractional LP value previously caused the
    schedule builder to ceil each phase independently, inflating AP attributed to
    other espers in those same phases (Kirin showed 102 instead of 100, Ramuh
    showed 51 instead of 50).

    With the integer-AP schedule, each character earns exactly the minimum AP
    needed on each esper: 100 on Kirin (Cura rate 1), 50 on Ramuh (Thundara
    rate 2), 17 on Siren (Fire rate 6).
    """
    party = [
        {"character_id": "celes", "progress": {}},
        {"character_id": "locke", "progress": {}},
        {"character_id": "sabin", "progress": {}},
        {"character_id": "edgar", "progress": {}},
    ]
    result = run(party, ["ramuh", "kirin", "siren"])
    assert result.status == "optimal"
    assert result.total_ap == 400  # 4 chars × 100 AP on Kirin serially

    earned = _phase_ap_per_char_esper(result)
    for char_id in ["celes", "locke", "sabin", "edgar"]:
        assert earned.get((char_id, "kirin"), 0) == 100, f"{char_id} kirin"
        assert earned.get((char_id, "ramuh"), 0) == 50,  f"{char_id} ramuh"
        assert earned.get((char_id, "siren"), 0) == 17,  f"{char_id} siren"


def test_integer_rate_no_inflation():
    """
    When all spell rates divide evenly into 100, there are no fractional LP
    values, so the old and new schedule builders agree.  This guards against
    regressions in the simple case.

    Terra needs only Fire (Ifrit x10): exactly 10 AP, no fractions.
    """
    party = [{"character_id": "terra", "progress": all_learned_except({"fire": 0})}]
    result = run(party, ["ifrit"])
    assert result.status == "optimal"
    assert result.total_ap == 10

    earned = _phase_ap_per_char_esper(result)
    assert earned.get(("terra", "ifrit"), 0) == 10


def test_fractional_rate_single_char():
    """
    Single character needing a fractional-rate spell: ceil(100/6) = 17 AP,
    not the truncated 16.
    """
    party = [{"character_id": "terra", "progress": all_learned_except({"fire": 0})}]
    result = run(party, ["siren"])  # Fire x6
    assert result.status == "optimal"
    assert result.total_ap == 17

    earned = _phase_ap_per_char_esper(result)
    assert earned.get(("terra", "siren"), 0) == 17


# ── Seed assignments ─────────────────────────────────────────

def test_seed_locke_second():
    """
    Celes is listed first in the party, but check that we can give Locke any
    esper to seed.
    """
    party = [
        {"character_id": "celes", "progress": {}},
        {"character_id": "locke", "progress": {}},
    ]
    result = optimize(
        party=party,
        available_esper_ids=["ramuh", "kirin", "siren", "cait_sith"],
        all_espers=load_espers(),
        all_spells=load_spells(),
        current_assignments={"locke": "ramuh"},
    )
    assert result.status == "optimal"
    assert result.schedule[0].assignments["locke"] == "ramuh"

    party = [
        {"character_id": "celes", "progress": {}},
        {"character_id": "locke", "progress": {}},
    ]
    result = optimize(
        party=party,
        available_esper_ids=["ramuh", "kirin", "siren", "cait_sith"],
        all_espers=load_espers(),
        all_spells=load_spells(),
        current_assignments={"locke": "kirin"},
    )
    assert result.status == "optimal"
    assert result.schedule[0].assignments["locke"] == "kirin"


def test_think_big_all_espers_ap_matches_normal_run():
    """
    Think Big mode: total_ap_all_espers must equal the total_ap you'd get by
    running a normal (non-Think-Big) optimize with all espers selected.

    Party: Celes + Locke, no prior progress.
    Available espers: Ramuh, Kirin, Siren, Cait Sith (a strict subset).
    """
    party = [
        {"character_id": "celes", "progress": {}},
        {"character_id": "locke", "progress": {}},
    ]
    all_esper_ids = [e["id"] for e in load_espers()]

    normal_all = optimize(party, all_esper_ids, load_espers(), load_spells())
    think_big = optimize(
        party,
        available_esper_ids=["ramuh", "kirin", "siren", "cait_sith"],
        all_espers=load_espers(),
        all_spells=load_spells(),
        think_big=True,
    )

    assert think_big.status == "partial"
    assert think_big.total_ap_all_espers is not None
    assert think_big.total_ap_all_espers == normal_all.total_ap
    assert think_big.total_ap < think_big.total_ap_all_espers


def test_single_char_all_espers_no_progress():
    """
    Celes with all espers and no progress. The integer conversion must use
    LP-aware net remaining so that spells covered by other espers don't inflate
    the AP assigned to a given esper.

    Key cases that differ from naive ceil(100/rate):
    - siren: 13, not 17  (fire/slow covered by ifrit/palidor)
    - bismarck: 1, not 50 (raise covered by phoenix; blizzard split with shiva)
    - shiva: 8, not 20    (blizzard split with bismarck; blizzara split with maduin)
    """
    all_esper_ids = [e["id"] for e in load_espers()]
    party = [{"character_id": "celes", "progress": {}}]
    result = run(party, all_esper_ids)
    assert result.status == "optimal"

    earned: dict[str, int] = {}
    for phase in result.schedule:
        for char_id, esper_id in phase.assignments.items():
            if esper_id is not None:
                earned[esper_id] = earned.get(esper_id, 0) + phase.ap

    expected = {
        "alexander":    50,
        "bahamut":      50,
        "bismarck":      1,
        "cait_sith":    20,
        "carbuncle":    20,
        "catoblepas":   50,
        "crusader":    100,
        "fenrir":       20,
        "golem":         8,
        "ifrit":       100,
        "kirin":        25,
        "lakshmi":       3,
        "maduin":       20,
        "midgardsornmr": 100,
        "phantom":      34,
        "phoenix":     100,
        "palidor":      50,
        "ragnarok":    100,
        "raiden":      100,
        "ramuh":        20,
        "shiva":         8,
        "siren":        13,
        "tritoch":     100,
        "zona_seeker":   5,
    }
    absent = {"seraph", "unicorn", "odin"}

    for esper_id, ap in expected.items():
        assert earned.get(esper_id, 0) == ap, (
            f"{esper_id}: expected {ap} AP, got {earned.get(esper_id, 0)}"
        )
    for esper_id in absent:
        assert esper_id not in earned, (
            f"{esper_id}: expected 0 AP but got {earned.get(esper_id)} AP"
        )
