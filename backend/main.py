from __future__ import annotations
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.game_data import all_game_data, esper_by_id, load_espers, load_spells
from backend.models import OptimizeRequest, OptimizeResponse
from backend.optimizer import optimize

app = FastAPI(title="FF6 Magic Optimizer")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/game-data")
def game_data():
    return all_game_data()


@app.post("/api/optimize", response_model=OptimizeResponse)
def run_optimize(req: OptimizeRequest):
    espers = load_espers()
    spells = load_spells()

    # Validate character IDs
    party_dicts = []
    for cp in req.party:
        party_dicts.append({
            "character_id": cp.character_id,
            "progress": cp.progress,
        })

    if not party_dicts:
        raise HTTPException(status_code=422, detail="Party must have at least one character.")

    if not req.available_esper_ids:
        raise HTTPException(status_code=422, detail="No espers selected.")

    return optimize(
        party=party_dicts,
        available_esper_ids=req.available_esper_ids,
        all_espers=espers,
        all_spells=spells,
        current_assignments=req.current_assignments,
    )


# Static files mount must be last — after all API routes
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
