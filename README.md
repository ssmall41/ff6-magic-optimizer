# ff6-magic-optimizer

## Final Fantasy VI

Final Fantasy VI (SNES, 1994) is a role-playing game developed by Square. One of its defining mechanics is magic learning: characters do not learn spells on their own. Instead, each character must equip a magicite shard — a crystallized remnant of an Esper — and then earn AP (Ability Points) through battles. Each Esper teaches a set of spells at a fixed rate, and a spell is permanently learned once a character accumulates the required AP. Because only one character can equip a given Esper at a time, routing magic efficiently across a party is a non-trivial planning problem.

## What This Project Does

This tool helps players plan the fastest possible path to fully learning all spells across their party. Given which Espers are available and each character's current spell progress, it calculates the minimum total AP required and produces a concrete, phase-by-phase schedule of which Esper each character should equip during each segment of play.

## Building

Requires Python 3.11+. Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Starting the API

```bash
uvicorn backend.main:app --reload
```

The API is served at `http://localhost:8000`. The frontend is served at the root (`/`), and API endpoints are available under `/api/`.

To run the test suite:

```bash
pytest
```

## Features

### Think Big

The **Think Big** option changes how the LP optimization is seeded. Normally the LP considers only the Espers you have marked as available. With Think Big enabled, the LP is solved over *all* Espers in the game, giving the theoretically minimum AP if you eventually collect everything. The concrete schedule is still built from only your currently available Espers, so the output shows two numbers: the LP-optimal AP assuming full collection, and the realistic schedule AP using what you actually have. The result status is shown as `partial` when Think Big is on and you are missing at least one Esper.

### Odin / Raiden

In FF6, the Odin Esper transforms into Raiden after a late-game event — you can only ever have one or the other. The optimizer enforces this: selecting Odin automatically deselects Raiden, and vice versa. Think Big mode also excludes Odin from its full-roster LP (only Raiden is considered), reflecting the fact that Odin is never available once Raiden exists.

### Ragnarok: Esper vs. Sword

When the player obtains Ragnarok, they must choose between receiving it as an **Esper** (which teaches Ultima) or as a **Sword** (a powerful weapon). This choice is permanent within a playthrough. The Ragnarok button in the UI cycles through three states:

- **Unselected** — Ragnarok has not been obtained yet.
- **Selected** — Ragnarok was taken as an Esper and is available for magic learning.
- **Sword Chosen** — Ragnarok was taken as a sword; the Esper is permanently unavailable.

When Sword Chosen is active, Ragnarok is excluded from both the available-Esper schedule and the Think Big LP optimization.

## Algorithms

### LP Optimization

The optimizer formulates spell learning as a linear program solved by [SciPy's HiGHS solver](https://highs.dev/).

**Variables:** For each character `c` and Esper `e`, a continuous variable `a[c][e]` represents the AP that character `c` spends with Esper `e`. A null Esper is included for each character to absorb any "idle" time. A single global variable `T` represents the total AP budget (the makespan).

**Objective:** Minimize `T`.

**Constraints:**
- *Time balance:* Each character's AP allocations sum to exactly `T` (`Σ_e a[c][e] = T` for each `c`). This ensures all characters finish simultaneously.
- *Esper exclusivity:* Each real Esper's total usage across all characters is at most `T` (`Σ_c a[c][e] ≤ T` for each `e`). This encodes the constraint that an Esper can only be equipped by one character at a time.
- *Spell requirements:* For each (character, spell) pair with remaining progress, the weighted sum of AP spent on Espers that teach that spell must cover the remaining requirement (`Σ_e rate[e][s] * a[c][e] ≥ remaining[c][s]`).

The LP solution gives the theoretically minimum AP makespan and a fractional allocation of AP across (character, Esper) pairs.

### Scheduler

The continuous LP solution is converted to a concrete integer schedule by a greedy simulation in `backend/schedule.py`.

First, integer AP requirements per (character, Esper) pair are derived from the LP solution: for each pair active in the solution, the AP needed is `ceil(net_remaining / rate)`, where `net_remaining` accounts for coverage already provided by other Espers in the LP plan.

The scheduler then runs a greedy loop:
1. Each character picks the Esper with the most remaining AP among those not already claimed by another character in this phase. Characters with no available Esper idle.
2. The phase length is the minimum remaining AP among all active (character, Esper) assignments — i.e., how long until someone finishes their current Esper.
3. AP is decremented accordingly and finished Espers are removed from the pending set.
4. Repeat until all characters have no remaining Esper assignments.

This produces a sequence of phases, each specifying the AP duration and which Esper every character equips.

The scheduler also accepts the player's **current Esper assignments** as seeds. Any character who already has an Esper equipped and still needs AP from it is prioritized in the first phase, claiming that Esper before other characters make their greedy picks. This means the generated schedule respects what characters are already wearing — no unnecessary swaps at the start of play.
