from __future__ import annotations
import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linprog

from backend.models import (
    AllocationEntry,
    OptimizeResponse,
    OptimizerWarning,
    PhaseAssignment,
)
from backend.schedule import build_schedule


@dataclass
class _Input:
    char_ids: list[str]
    esper_ids: list[str]   # real espers only
    spell_ids: list[str]
    rates: np.ndarray      # shape (n_espers, n_spells)
    remaining: np.ndarray  # shape (n_chars, n_spells), values 0-100


def _build_lp(_inp: _Input) -> tuple:
    """Return (c_obj, A_ub, b_ub, A_eq, b_eq, bounds) for scipy.optimize.linprog."""
    N = len(_inp.char_ids)
    M = len(_inp.esper_ids)   # real espers
    S = len(_inp.spell_ids)

    # Variable layout: a[c][e] at index c*(M+1)+e, null esper at c*(M+1)+M, T at N*(M+1)
    n_vars = N * (M + 1) + 1
    t_idx = n_vars - 1

    # Objective: minimise T
    c_obj = np.zeros(n_vars)
    c_obj[t_idx] = 1.0

    # --- Equality constraints: sum_e a[c][e] = T for each character c ---
    A_eq = np.zeros((N, n_vars))
    b_eq = np.zeros(N)
    for c in range(N):
        for e in range(M + 1):  # includes null esper
            A_eq[c, c * (M + 1) + e] = 1.0
        A_eq[c, t_idx] = -1.0

    # --- Inequality: sum_c a[c][e] <= T for each real esper e ---
    A_ub_rows: list[np.ndarray] = []
    b_ub_rows: list[float] = []

    for e in range(M):
        row = np.zeros(n_vars)
        for c in range(N):
            row[c * (M + 1) + e] = 1.0
        row[t_idx] = -1.0
        A_ub_rows.append(row)
        b_ub_rows.append(0.0)

    # --- Inequality: spell learning requirements ---
    for c in range(N):
        for s in range(S):
            rem = _inp.remaining[c, s]
            if rem <= 0:
                continue
            row = np.zeros(n_vars)
            for e in range(M):
                rate = _inp.rates[e, s]
                if rate > 0:
                    row[c * (M + 1) + e] = -rate
            # null esper contributes nothing, so no term for e=M
            A_ub_rows.append(row)
            b_ub_rows.append(-rem)

    if A_ub_rows:
        A_ub = np.array(A_ub_rows)
        b_ub = np.array(b_ub_rows)
    else:
        A_ub = np.zeros((0, n_vars))
        b_ub = np.zeros(0)

    bounds = [(0.0, None)] * n_vars

    return c_obj, A_ub, b_ub, A_eq, b_eq, bounds


def _extract_allocations(x: np.ndarray, inp: _Input) -> list[AllocationEntry]:
    N = len(inp.char_ids)
    M = len(inp.esper_ids)
    T = x[-1]
    entries: list[AllocationEntry] = []
    for c, char_id in enumerate(inp.char_ids):
        for e, esper_id in enumerate(inp.esper_ids):
            ap = x[c * (M + 1) + e]
            if ap > 1e-4:
                entries.append(AllocationEntry(
                    character_id=char_id,
                    esper_id=esper_id,
                    ap_amount=round(ap, 4),
                    fraction=round(ap / T, 4) if T > 1e-9 else 0.0,
                ))
        null_ap = x[c * (M + 1) + M]
        if null_ap > 1e-4:
            entries.append(AllocationEntry(
                character_id=char_id,
                esper_id=None,
                ap_amount=round(null_ap, 4),
                fraction=round(null_ap / T, 4) if T > 1e-9 else 0.0,
            ))
    return entries


def optimize(
    party: list[dict],            # [{"character_id": str, "progress": {spell_id: float}}]
    available_esper_ids: list[str],
    all_espers: list[dict],
    all_spells: list[dict],
    current_assignments: dict[str, str | None] | None = None,
    think_big: bool = False,
) -> OptimizeResponse:
    char_ids = [p["character_id"] for p in party]
    s_ids = [s["id"] for s in all_spells]
    N = len(char_ids)
    S = len(s_ids)

    esper_map = {e["id"]: e for e in all_espers}
    sched_esper_ids = [eid for eid in available_esper_ids if eid in esper_map]
    lp_esper_ids = [e for e in esper_map if e != "odin"] if think_big else sched_esper_ids
    valid_esper_ids = lp_esper_ids
    M = len(valid_esper_ids)

    # Build rates matrix (M × S)
    rates = np.zeros((M, S))
    s_index = {sid: i for i, sid in enumerate(s_ids)}
    for ei, eid in enumerate(valid_esper_ids):
        esper = esper_map[eid]
        for spell_id, rate in esper.get("spells", {}).items():
            if spell_id in s_index:
                rates[ei, s_index[spell_id]] = float(rate)

    # Build remaining matrix (N × S)
    remaining = np.zeros((N, S))
    for ci, p in enumerate(party):
        prog = p.get("progress", {})
        for si, spell_id in enumerate(s_ids):
            current = float(prog.get(spell_id, 0.0))
            remaining[ci, si] = max(0.0, 100.0 - current)

    # Pre-check: identify unlearnable spells (needed but no esper teaches them)
    warnings: list[OptimizerWarning] = []
    unlearnable: list[str] = []
    for si, spell_id in enumerate(s_ids):
        for ci in range(N):
            if remaining[ci, si] > 0 and not np.any(rates[:, si] > 0):
                if spell_id not in unlearnable:
                    unlearnable.append(spell_id)
                remaining[ci, si] = 0.0  # exclude from LP

    # Short-circuit if nothing left to learn
    if not np.any(remaining > 0):
        return OptimizeResponse(
            status="all_learned",
            total_ap=0,
            total_ap_exact=0.0,
            schedule=[],
            allocations=[],
            warnings=warnings,
            unlearnable=unlearnable,
        )

    inp = _Input(
        char_ids=char_ids,
        esper_ids=valid_esper_ids,
        spell_ids=s_ids,
        rates=rates,
        remaining=remaining,
    )

    c_obj, A_ub, b_ub, A_eq, b_eq, bounds = _build_lp(inp)

    result = linprog(
        c_obj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
        bounds=bounds, method="highs",
    )

    if result.status != 0:
        return OptimizeResponse(
            status="infeasible",
            total_ap=0,
            total_ap_exact=0.0,
            schedule=[],
            allocations=[],
            warnings=warnings + [OptimizerWarning(
                kind="solver_error",
                message=f"Solver returned status {result.status}: {result.message}",
            )],
            unlearnable=unlearnable,
        )

    T_exact = float(result.fun)
    allocations = _extract_allocations(result.x, inp)

    # Compute integer AP needed per (char, esper) from spell requirements.
    # ceil(remaining/rate) gives the exact integer AP a character must earn
    # with an esper to learn every spell it teaches, accounting for partial
    # progress. This avoids fractional LP values propagating into phase lengths.
    char_esper_ap: dict[str, dict[str, int]] = {c: {} for c in char_ids}
    for ci, char_id in enumerate(char_ids):
        for ei, esper_id in enumerate(valid_esper_ids):
            if result.x[ci * (M + 1) + ei] <= 1e-4:
                continue
            ap_needed = 0
            for si in range(S):
                rate = inp.rates[ei, si]
                rem = inp.remaining[ci, si]
                if rate <= 0 or rem <= 0:
                    continue
                # Subtract coverage already provided by other espers in the LP
                # solution, so we don't inflate AP for spells covered elsewhere.
                other_coverage = sum(
                    inp.rates[ej, si] * result.x[ci * (M + 1) + ej]
                    for ej in range(M)
                    if ej != ei and inp.rates[ej, si] > 0
                )
                net_rem = max(0.0, rem - other_coverage)
                if net_rem > 0:
                    ap_needed = max(ap_needed, math.ceil(net_rem / rate - 1e-9))
            if ap_needed > 0:
                char_esper_ap[char_id][esper_id] = ap_needed

    T_int_all_espers: int | None = None
    if think_big:
        all_phases = build_schedule(char_esper_ap, seed_assignments=current_assignments)
        T_int_all_espers = all_phases[-1]["cumulative_ap"] if all_phases else 0
        avail_set = set(sched_esper_ids)
        char_esper_ap = {
            cid: {eid: ap for eid, ap in esper_aps.items() if eid in avail_set}
            for cid, esper_aps in char_esper_ap.items()
        }

    raw_phases = build_schedule(char_esper_ap, seed_assignments=current_assignments)
    schedule = [PhaseAssignment(**p) for p in raw_phases]
    T_int = raw_phases[-1]["cumulative_ap"] if raw_phases else 0

    is_partial = think_big and bool(set(lp_esper_ids) - set(sched_esper_ids))
    return OptimizeResponse(
        status="partial" if is_partial else "optimal",
        total_ap_all_espers=T_int_all_espers,
        total_ap=T_int,
        total_ap_exact=round(T_exact, 4),
        schedule=schedule,
        allocations=allocations,
        warnings=warnings,
        unlearnable=unlearnable,
    )
