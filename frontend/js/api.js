'use strict';

const BASE = '';  // same origin

async function fetchGameData() {
  const res = await fetch(`${BASE}/api/game-data`);
  if (!res.ok) throw new Error(`Failed to load game data: ${res.status}`);
  return res.json();
}

async function fetchOptimize(party, availableEsperIds, currentAssignments, thinkBig = false, swordChosen = false) {
  const res = await fetch(`${BASE}/api/optimize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ party, available_esper_ids: availableEsperIds, current_assignments: currentAssignments, think_big: thinkBig, sword_chosen: swordChosen }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}
