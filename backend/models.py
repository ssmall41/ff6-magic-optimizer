from __future__ import annotations
from pydantic import BaseModel, Field


class CharacterProgress(BaseModel):
    character_id: str
    progress: dict[str, float] = Field(
        default_factory=dict,
        description="spell_id -> progress points (0-100). Omit or 100 = learned.",
    )


class OptimizeRequest(BaseModel):
    party: list[CharacterProgress]
    available_esper_ids: list[str]
    current_assignments: dict[str, str | None] = Field(default_factory=dict)


class PhaseAssignment(BaseModel):
    phase: int
    ap: int
    cumulative_ap: int
    assignments: dict[str, str | None]  # char_id -> esper_id (None = idle)


class AllocationEntry(BaseModel):
    character_id: str
    esper_id: str | None
    ap_amount: float
    fraction: float


class OptimizerWarning(BaseModel):
    kind: str  # "unlearnable"
    character_id: str | None = None
    spell_id: str | None = None
    message: str


class OptimizeResponse(BaseModel):
    status: str  # "optimal" | "all_learned" | "infeasible" | "error"
    total_ap: int
    total_ap_exact: float
    schedule: list[PhaseAssignment]
    allocations: list[AllocationEntry]
    warnings: list[OptimizerWarning]
    unlearnable: list[str]  # spell IDs with no available teacher
