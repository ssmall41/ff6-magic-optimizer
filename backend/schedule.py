from __future__ import annotations


def build_schedule(
    char_esper_ap: dict[str, dict[str, int]],
    seed_assignments: dict[str, str | None] | None = None,
) -> list[dict]:
    """
    Convert integer AP requirements to a phased schedule with no esper conflicts.

    char_esper_ap: {char_id: {esper_id: integer_ap_needed}}
    Returns: list of {phase, ap, cumulative_ap, assignments: {char_id: esper_id|None}}

    Algorithm: greedy simulation.
    At each step, each character picks their highest-remaining-ap esper that is
    not already in use by another character. If no real esper is available, the
    character idles (None). Advance time by the minimum remaining AP among
    currently active real-esper assignments, then repeat.
    """
    pending: dict[str, dict[str, int]] = {
        char_id: {e: a for e, a in allocs.items() if a > 0}
        for char_id, allocs in char_esper_ap.items()
    }
    char_ids = list(pending.keys())

    def pick(char_id: str, in_use: set) -> str | None:
        """Best available (non-conflicted) esper for char; None = idle."""
        seed = (seed_assignments or {}).get(char_id)
        if seed and seed not in in_use and pending[char_id].get(seed, 0) > 0:
            return seed
        real = [
            (ap, e) for e, ap in pending[char_id].items()
            if e not in in_use and ap > 0
        ]
        if real:
            real.sort(reverse=True)
            return real[0][1]
        return None

    phases: list[dict] = []
    MAX_PHASES = 500

    while any(pending[c] for c in char_ids) and len(phases) < MAX_PHASES:
        in_use: set[str] = set()
        assignment: dict[str, str | None] = {}
        for char_id in char_ids:
            e = pick(char_id, in_use)
            assignment[char_id] = e
            if e is not None:
                in_use.add(e)

        step_candidates: list[int] = [
            pending[char_id][esper_id]
            for char_id, esper_id in assignment.items()
            if esper_id is not None
        ]

        if not step_candidates:
            break

        step_ap = min(step_candidates)

        phases.append({
            "ap": step_ap,
            "assignments": dict(assignment),
        })

        for char_id, esper_id in assignment.items():
            if esper_id is not None:
                pending[char_id][esper_id] -= step_ap
                if pending[char_id][esper_id] <= 0:
                    del pending[char_id][esper_id]

    cumulative = 0
    for i, phase in enumerate(phases):
        cumulative += phase["ap"]
        phase["phase"] = i + 1
        phase["cumulative_ap"] = cumulative

    return phases
