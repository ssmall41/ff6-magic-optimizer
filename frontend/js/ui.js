'use strict';

// ── Character grid ───────────────────────────────────────────

function renderCharacterGrid(gameData, state, onToggle) {
  const grid = document.getElementById('character-grid');
  grid.innerHTML = '';

  for (const char of gameData.characters) {
    if (!char.can_equip_espers) continue;
    const btn = document.createElement('button');
    btn.className = 'toggle-btn';
    btn.textContent = char.name;
    btn.dataset.id = char.id;

    const selected = state.party.includes(char.id);
    if (selected) btn.classList.add('selected');

    const full = state.party.length >= 4 && !selected;
    if (full) btn.disabled = true;

    btn.addEventListener('click', () => onToggle(char.id));
    grid.appendChild(btn);
  }
}

// ── Esper grid ───────────────────────────────────────────────

function renderEsperGrid(gameData, state, filters, onToggle) {
  const grid = document.getElementById('esper-grid');
  grid.innerHTML = '';

  for (const esper of gameData.espers) {
    if (!filters[esper.world]) continue;
    const btn = document.createElement('button');
    btn.className = 'toggle-btn';
    btn.textContent = esper.name;
    btn.dataset.id = esper.id;
    btn.title = Object.entries(esper.spells)
      .map(([s, r]) => `${s} ×${r}`)
      .join(', ');

    if (state.espers.includes(esper.id)) btn.classList.add('selected');
    btn.addEventListener('click', () => onToggle(esper.id));
    grid.appendChild(btn);
  }
}

// ── Spell progress ───────────────────────────────────────────

function renderProgressTabs(state, onTabSelect) {
  const tabRow = document.getElementById('progress-tabs');
  tabRow.innerHTML = '';

  for (const charId of state.party) {
    const btn = document.createElement('button');
    btn.className = 'tab-btn';
    btn.textContent = charId.charAt(0).toUpperCase() + charId.slice(1);
    btn.dataset.id = charId;
    if (charId === state.activeCharTab) btn.classList.add('active');
    btn.addEventListener('click', () => onTabSelect(charId));
    tabRow.appendChild(btn);
  }
}

function renderProgressTable(gameData, state, onProgressChange) {
  const content = document.getElementById('progress-content');
  const charId = state.activeCharTab;

  if (!charId || !state.party.includes(charId)) {
    content.innerHTML = '<p class="placeholder">Select a character tab to view spell progress.</p>';
    return;
  }

  const charProgress = state.progress[charId] ?? {};

  // Determine which spells are reachable with selected espers
  const teachableSpells = new Set();
  const esperMap = Object.fromEntries(gameData.espers.map(e => [e.id, e]));
  for (const esperId of state.espers) {
    const esper = esperMap[esperId];
    if (esper) Object.keys(esper.spells).forEach(s => teachableSpells.add(s));
  }

  const table = document.createElement('table');
  table.className = 'spell-table';
  table.innerHTML = `
    <thead>
      <tr>
        <th>Spell</th>
        <th>School</th>
        <th>Progress (0–100)</th>
        <th>Status</th>
      </tr>
    </thead>
  `;
  const tbody = document.createElement('tbody');

  for (const spell of gameData.spells) {
    if (!teachableSpells.has(spell.id)) continue;

    const current = charProgress[spell.id] ?? 0;
    const learned = current >= 100;

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="spell-name">${spell.name}</td>
      <td class="spell-school">${spell.school.replace('_', ' ')}</td>
      <td>
        <input
          type="number" min="0" max="100"
          class="progress-input"
          data-char="${charId}"
          data-spell="${spell.id}"
          value="${Math.round(current)}"
        />
      </td>
      <td>${learned ? '<span class="learned-badge">Learned</span>' : ''}</td>
    `;
    tbody.appendChild(tr);
  }

  table.appendChild(tbody);
  content.innerHTML = '';
  content.appendChild(table);

  content.querySelectorAll('.progress-input').forEach(input => {
    input.addEventListener('change', () => {
      const val = Math.min(100, Math.max(0, Number(input.value) || 0));
      input.value = val;
      onProgressChange(input.dataset.char, input.dataset.spell, val);
    });
  });
}

// ── AP assignment selectors ──────────────────────────────────

function renderAPAssignments(gameData, state, onAssignChange) {
  const grid = document.getElementById('ap-assignments');
  grid.innerHTML = '';

  if (state.party.length === 0) {
    grid.innerHTML = '<span class="placeholder">Select party members first.</span>';
    return;
  }

  const charMap = Object.fromEntries(gameData.characters.map(c => [c.id, c]));

  for (const charId of state.party) {
    const char = charMap[charId];
    const item = document.createElement('div');
    item.className = 'ap-assign-item';

    const label = document.createElement('span');
    label.textContent = char.name + ':';

    const select = document.createElement('select');
    select.dataset.char = charId;

    const noneOpt = document.createElement('option');
    noneOpt.value = '';
    noneOpt.textContent = '— none —';
    select.appendChild(noneOpt);

    for (const esper of gameData.espers) {
      if (!state.espers.includes(esper.id)) continue;
      const opt = document.createElement('option');
      opt.value = esper.id;
      opt.textContent = esper.name;
      select.appendChild(opt);
    }

    select.value = state.assignments[charId] ?? '';
    select.addEventListener('change', () => onAssignChange(charId, select.value || null));

    item.appendChild(label);
    item.appendChild(select);
    grid.appendChild(item);
  }
}

// ── Results ──────────────────────────────────────────────────

function renderResults(result, gameData) {
  const panel = document.getElementById('panel-results');
  panel.classList.remove('hidden');

  // Summary
  const summary = document.getElementById('results-summary');
  if (result.status === 'all_learned') {
    summary.innerHTML = '<span class="stat"><span class="stat-value" style="color:var(--learned)">All spells already learned!</span></span>';
  } else {
    summary.innerHTML = `
      <span class="stat">
        <span class="stat-label">Status:</span>
        <span class="stat-value">${result.status}</span>
      </span>
      <span class="stat">
        <span class="stat-label">Minimum AP needed:</span>
        <span class="stat-value">${result.total_ap}</span>
      </span>
    `;
  }

  // Warnings
  const warnBox = document.getElementById('results-warnings');
  const allWarnings = [...result.warnings];
  if (allWarnings.length) {
    warnBox.classList.remove('hidden');
    warnBox.innerHTML = '<strong>Warnings</strong><ul>' +
      allWarnings.map(w => `<li>${w.message}</li>`).join('') +
      '</ul>';
  } else {
    warnBox.classList.add('hidden');
    warnBox.innerHTML = '';
  }

  // Schedule table
  const schedDiv = document.getElementById('results-schedule');
  schedDiv.innerHTML = '';

  if (!result.schedule.length) return;

  const charIds = [...new Set(result.schedule.flatMap(p => Object.keys(p.assignments)))];
  const charMap = Object.fromEntries(gameData.characters.map(c => [c.id, c]));
  const esperMap = Object.fromEntries(gameData.espers.map(e => [e.id, e]));

  const table = document.createElement('table');
  table.className = 'schedule-table';

  const thead = document.createElement('thead');
  thead.innerHTML = '<tr>' +
    '<th>Phase</th><th>AP</th><th>Cumul. AP</th>' +
    charIds.map(c => `<th>${charMap[c]?.name ?? c}</th>`).join('') +
    '</tr>';
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  for (const phase of result.schedule) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td class="ap-cell">${phase.phase}</td>` +
      `<td class="ap-cell">${phase.ap}</td>` +
      `<td class="ap-cell">${phase.cumulative_ap}</td>` +
      charIds.map(c => {
        const esperId = phase.assignments[c];
        if (!esperId) return '<td class="idle-cell">—</td>';
        return `<td class="esper-cell">${esperMap[esperId]?.name ?? esperId}</td>`;
      }).join('');
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  schedDiv.appendChild(table);

  // Expose first-phase assignments for "Use These Assignments" button
  panel.dataset.firstPhase = JSON.stringify(result.schedule[0]?.assignments ?? {});
}
