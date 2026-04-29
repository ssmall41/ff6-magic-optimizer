'use strict';

// ── Bootstrap ────────────────────────────────────────────────

let gameData = null;
let state = loadState();

document.addEventListener('DOMContentLoaded', async () => {
  try {
    gameData = await fetchGameData();
  } catch (err) {
    document.querySelector('main').innerHTML =
      `<p class="error" style="padding:2rem">Failed to load game data: ${err.message}.<br>Is the server running at <code>http://127.0.0.1:8000</code>?</p>`;
    return;
  }

  // Ensure activeCharTab is valid
  if (!state.party.includes(state.activeCharTab)) {
    state.activeCharTab = state.party[0] ?? null;
  }

  renderAll();
  bindEvents();
});

// ── Render everything ────────────────────────────────────────

function renderAll() {
  const filters = getEsperFilters();
  renderCharacterGrid(gameData, state, toggleCharacter);
  renderEsperGrid(gameData, state, filters, toggleEsper);
  renderProgressTabs(state, selectCharTab);
  renderProgressTable(gameData, state, setProgress);
  renderAPAssignments(gameData, state, setAssignment);
}

// ── Event binding ────────────────────────────────────────────

function bindEvents() {
  document.getElementById('filter-wob').addEventListener('change', () => {
    renderEsperGrid(gameData, state, getEsperFilters(), toggleEsper);
  });
  document.getElementById('filter-wor').addEventListener('change', () => {
    renderEsperGrid(gameData, state, getEsperFilters(), toggleEsper);
  });

  document.getElementById('btn-mark-all').addEventListener('click', markAllLearned);
  document.getElementById('btn-reset-progress').addEventListener('click', resetCharProgress);

  document.getElementById('btn-apply-ap').addEventListener('click', handleApplyAP);
  document.getElementById('btn-optimize').addEventListener('click', handleOptimize);
  document.getElementById('btn-use-assignments').addEventListener('click', useFirstPhaseAssignments);
}

// ── Party / esper toggles ────────────────────────────────────

function toggleCharacter(charId) {
  const idx = state.party.indexOf(charId);
  if (idx >= 0) {
    state.party.splice(idx, 1);
    if (state.activeCharTab === charId) {
      state.activeCharTab = state.party[0] ?? null;
    }
  } else {
    if (state.party.length >= 4) return;
    state.party.push(charId);
    if (!state.activeCharTab) state.activeCharTab = charId;
  }
  saveState(state);
  renderAll();
}

function toggleEsper(esperId) {
  const idx = state.espers.indexOf(esperId);
  if (idx >= 0) {
    state.espers.splice(idx, 1);
  } else {
    state.espers.push(esperId);
  }
  saveState(state);
  renderEsperGrid(gameData, state, getEsperFilters(), toggleEsper);
  renderProgressTable(gameData, state, setProgress);
  renderAPAssignments(gameData, state, setAssignment);
}

// ── Spell progress ───────────────────────────────────────────

function selectCharTab(charId) {
  state.activeCharTab = charId;
  saveState(state);
  renderProgressTabs(state, selectCharTab);
  renderProgressTable(gameData, state, setProgress);
}

function setProgress(charId, spellId, value) {
  if (!state.progress[charId]) state.progress[charId] = {};
  state.progress[charId][spellId] = value;
  saveState(state);
  // Re-render the row status without full table rebuild
  renderProgressTable(gameData, state, setProgress);
}

function markAllLearned() {
  const charId = state.activeCharTab;
  if (!charId) return;
  if (!state.progress[charId]) state.progress[charId] = {};
  const esperMap = Object.fromEntries(gameData.espers.map(e => [e.id, e]));
  for (const esperId of state.espers) {
    const esper = esperMap[esperId];
    if (!esper) continue;
    for (const spellId of Object.keys(esper.spells)) {
      state.progress[charId][spellId] = 100;
    }
  }
  saveState(state);
  renderProgressTable(gameData, state, setProgress);
}

function resetCharProgress() {
  const charId = state.activeCharTab;
  if (!charId) return;
  state.progress[charId] = {};
  saveState(state);
  renderProgressTable(gameData, state, setProgress);
}

// ── AP assignment ────────────────────────────────────────────

function setAssignment(charId, esperId) {
  if (esperId) {
    for (const [otherId, otherEsperId] of Object.entries(state.assignments)) {
      if (otherId !== charId && otherEsperId === esperId) {
        state.assignments[otherId] = null;
      }
    }
  }
  state.assignments[charId] = esperId;
  saveState(state);
  renderAPAssignments(gameData, state, setAssignment);
}

// ── Apply AP ─────────────────────────────────────────────────

function handleApplyAP() {
  const apInput = document.getElementById('ap-amount');
  const feedback = document.getElementById('ap-feedback');
  const apAmount = parseFloat(apInput.value);

  if (!apAmount || apAmount <= 0) {
    showFeedback(feedback, 'Enter a positive AP amount.', 'err');
    return;
  }

  if (state.party.length === 0) {
    showFeedback(feedback, 'Select party members first.', 'err');
    return;
  }

  const assigned = {};
  for (const charId of state.party) {
    assigned[charId] = state.assignments[charId] ?? null;
  }

  state.progress = applyAP(state.progress, assigned, gameData, apAmount);
  saveState(state);
  renderProgressTable(gameData, state, setProgress);
  apInput.value = '';
  showFeedback(feedback, `Applied ${apAmount} AP to all party members.`, 'ok');
}

// ── Optimize ─────────────────────────────────────────────────

async function handleOptimize() {
  const btn = document.getElementById('btn-optimize');
  const errEl = document.getElementById('optimize-error');
  errEl.classList.add('hidden');

  if (state.party.length === 0) {
    errEl.textContent = 'Select at least one party member.';
    errEl.classList.remove('hidden');
    return;
  }
  if (state.espers.length === 0) {
    errEl.textContent = 'Select at least one esper.';
    errEl.classList.remove('hidden');
    return;
  }

  btn.textContent = 'Optimizing…';
  btn.disabled = true;

  try {
    const party = buildPartyPayload(state.party, state.progress);
    const assignments = {};
    for (const charId of state.party) {
      assignments[charId] = state.assignments[charId] ?? null;
    }
    const result = await fetchOptimize(party, state.espers, assignments);
    renderResults(result, gameData);
  } catch (err) {
    errEl.textContent = `Error: ${err.message}`;
    errEl.classList.remove('hidden');
  } finally {
    btn.textContent = 'Optimize';
    btn.disabled = false;
  }
}

// ── Use first-phase assignments ──────────────────────────────

function useFirstPhaseAssignments() {
  const panel = document.getElementById('panel-results');
  const rawAssignments = panel.dataset.firstPhase;
  if (!rawAssignments) return;
  try {
    const assignments = JSON.parse(rawAssignments);
    for (const [charId, esperId] of Object.entries(assignments)) {
      state.assignments[charId] = esperId;
    }
    saveState(state);
    renderAPAssignments(gameData, state, setAssignment);
  } catch {
    // ignore parse error
  }
}

// ── Helpers ──────────────────────────────────────────────────

function getEsperFilters() {
  return {
    wob: document.getElementById('filter-wob').checked,
    wor: document.getElementById('filter-wor').checked,
  };
}

function showFeedback(el, msg, kind) {
  el.textContent = msg;
  el.className = `feedback ${kind}`;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 4000);
}
