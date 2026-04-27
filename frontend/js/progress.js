'use strict';

/**
 * Apply `apAmount` AP earned in battle to each party character,
 * based on their current esper assignment.
 *
 * Returns an updated progress object (does NOT mutate the input).
 */
function applyAP(progress, assignments, gameData, apAmount) {
  const updated = JSON.parse(JSON.stringify(progress));  // deep clone
  const esperMap = Object.fromEntries(gameData.espers.map(e => [e.id, e]));

  for (const [charId, esperId] of Object.entries(assignments)) {
    if (!esperId) continue;
    const esper = esperMap[esperId];
    if (!esper) continue;

    if (!updated[charId]) updated[charId] = {};

    for (const [spellId, rate] of Object.entries(esper.spells)) {
      const current = updated[charId][spellId] ?? 0;
      if (current >= 100) continue;
      updated[charId][spellId] = Math.min(100, current + rate * apAmount);
    }
  }

  return updated;
}

/**
 * Build a CharacterProgress array for the /api/optimize request.
 */
function buildPartyPayload(partyIds, progress) {
  return partyIds.map(charId => ({
    character_id: charId,
    progress: progress[charId] ?? {},
  }));
}
