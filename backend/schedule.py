from __future__ import annotations
import math


def build_schedule(
    alloc_by_char: dict[str, dict[str | None, float]],
    total_ap_exact: float,
) -> list[dict]:
    """
    Convert LP allocations to a phased schedule with no esper conflicts.

    alloc_by_char: {char_id: {esper_id_or_None: ap_amount}}
    Returns: list of {phase, ap, cumulative_ap, assignments: {char_id: esper_id|None}}

    Algorithm: greedy simulation.
    At each step, each character picks their highest-remaining-ap esper that is
    not already in use by another character. If all real espers are taken, the
    character uses their null allocation (or waits). Advance time by the minimum
    remaining AP among currently active assignments, then repeat.
    """
    # Mutable pending allocations per character
    pending: dict[str, dict[str | None, float]] = {
        char_id: {e: a for e, a in allocs.items() if a > 1e-4}
        for char_id, allocs in alloc_by_char.items()
    }
    char_ids = list(pending.keys())

    def pick(char_id: str, in_use: set) -> str | None:
        """Best available (non-conflicted) esper for char; None = idle."""
        real = [
            (ap, e) for e, ap in pending[char_id].items()
            if e is not None and e not in in_use and ap > 1e-4
        ]
        if real:
            real.sort(reverse=True)
            return real[0][1]
        if pending[char_id].get(None, 0.0) > 1e-4:
            return None  # use null allocation
        return None  # waiting (no allocation to consume)

    phases: list[dict] = []
    MAX_PHASES = 500

    while any(pending[c] for c in char_ids) and len(phases) < MAX_PHASES:
        # Assign espers without conflicts
        in_use: set[str] = set()
        assignment: dict[str, str | None] = {}
        for char_id in char_ids:
            e = pick(char_id, in_use)
            assignment[char_id] = e
            if e is not None:
                in_use.add(e)

        # Collect AP amounts for active assignments
        step_candidates: list[float] = []
        for char_id, esper_id in assignment.items():
            if esper_id is not None:
                ap = pending[char_id].get(esper_id, 0.0)
                if ap > 1e-4:
                    step_candidates.append(ap)
            else:
                # Consuming null allocation
                null_ap = pending[char_id].get(None, 0.0)
                if null_ap > 1e-4:
                    step_candidates.append(null_ap)

        if not step_candidates:
            break

        step_ap = min(step_candidates)

        phases.append({
            "ap": math.ceil(step_ap),
            "assignments": dict(assignment),
        })

        # Deduct step_ap from consumed allocations
        for char_id, esper_id in assignment.items():
            key = esper_id  # None for null
            if key in pending[char_id]:
                pending[char_id][key] -= step_ap
                if pending[char_id][key] <= 1e-4:
                    del pending[char_id][key]

    # Annotate with phase numbers and cumulative AP
    cumulative = 0
    for i, phase in enumerate(phases):
        cumulative += phase["ap"]
        phase["phase"] = i + 1
        phase["cumulative_ap"] = cumulative

    return phases
