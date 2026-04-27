from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


@lru_cache(maxsize=1)
def load_characters() -> list[dict]:
    return json.loads((DATA_DIR / "characters.json").read_text())


@lru_cache(maxsize=1)
def load_spells() -> list[dict]:
    return json.loads((DATA_DIR / "spells.json").read_text())


@lru_cache(maxsize=1)
def load_espers() -> list[dict]:
    return json.loads((DATA_DIR / "espers.json").read_text())


@lru_cache(maxsize=1)
def esper_by_id() -> dict[str, dict]:
    return {e["id"]: e for e in load_espers()}


@lru_cache(maxsize=1)
def spell_ids() -> list[str]:
    return [s["id"] for s in load_spells()]


def all_game_data() -> dict:
    return {
        "characters": load_characters(),
        "espers": load_espers(),
        "spells": load_spells(),
    }
