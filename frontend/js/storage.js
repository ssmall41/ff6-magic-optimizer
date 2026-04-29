'use strict';

const STORAGE_KEY = 'ff6_optimizer_state';

const DEFAULT_STATE = {
  party: [],          // list of character IDs (max 4)
  espers: [],         // list of selected esper IDs
  progress: {},       // { char_id: { spell_id: 0-100 } }
  assignments: {},    // { char_id: esper_id | null } — current equipped espers
  activeCharTab: null,
  thinkBig: false,
};

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT_STATE);
    return { ...structuredClone(DEFAULT_STATE), ...JSON.parse(raw) };
  } catch {
    return structuredClone(DEFAULT_STATE);
  }
}

function saveState(state) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function resetState() {
  localStorage.removeItem(STORAGE_KEY);
  return structuredClone(DEFAULT_STATE);
}
