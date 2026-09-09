/* Descriptive agreement only. Embedded feedback is not cryptographically hidden. */
(() => {
  "use strict";
  const labels = ["A", "B", "C", "D"];
  const keys = (v, expected) => v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).sort().join("|") === expected.slice().sort().join("|");
  const stable = v => JSON.stringify(v, function (_, x) {
    if (x && typeof x === "object" && !Array.isArray(x)) return Object.keys(x).sort().reduce((out, k) => { out[k] = x[k]; return out; }, {});
    return x;
  });
  function midranks(groups, expected = labels) {
    if (!Array.isArray(groups) || !groups.length || groups.some(g => !Array.isArray(g) || !g.length) || stable(groups.flat().slice().sort()) !== stable(expected.slice().sort())) throw new Error("Ungültige Ranggruppen.");
    const result = {}; let position = 1;
    groups.forEach(g => { g.forEach(l => { result[l] = position + (g.length - 1) / 2; }); position += g.length; });
    return result;
  }
  function groups(positions) {
    if (!keys(positions, labels) || labels.some(l => !Number.isInteger(positions[l]) || positions[l] < 1 || positions[l] > 4) || Math.min(...Object.values(positions)) !== 1) throw new Error("Ungültige Rangwerte.");
    return [...new Set(Object.values(positions))].sort().map(rank => labels.filter(l => positions[l] === rank));
  }
  function unpack(value, packet) {
    if (value && value.format === "legal-expert-return-v2") {
      if (!keys(value, ["format", "packet", "response", "agreement"]) || stable(value.packet) !== stable(packet)) throw new Error("Die Fragen oder Antworten gehören nicht zu diesem Paket.");
      return value.response;
    }
    return value;
  }
  function validate(value, packet) {
    value = unpack(value, packet);
    if (!keys(value, ["schema_version", "study_id", "packet_sha256", "reviewer_code", "revision", "exported_at", "judgments", "finalized_at"]) || value.schema_version !== 2) throw new Error("Unbekanntes Dateiformat.");
    for (const key of ["study_id", "reviewer_code", "packet_sha256"]) if (value[key] !== packet[key]) throw new Error("Die Sicherung gehört zu einer anderen Person oder einem anderen Paket.");
    if (!Number.isInteger(value.revision) || value.revision < 0 || typeof value.exported_at !== "string" || !Array.isArray(value.judgments) || (value.finalized_at !== null && (typeof value.finalized_at !== "string" || !value.finalized_at.trim()))) throw new Error("Ungültige Sicherungsdaten.");
    const ids = new Set(packet.tasks.map(t => t.task_id)), result = {};
    for (const r of value.judgments) {
      if (!keys(r, ["task_id", "status", "positions", "rank_groups", "notes", "reference_issue", "material_difference", "cannot_assess", "updated_at"]) || !ids.has(r.task_id) || result[r.task_id]) throw new Error("Unbekannter oder doppelter Fall.");
      if (!["draft", "ranked", "ungradable"].includes(r.status) || typeof r.notes !== "string" || r.notes.length > 10000 || typeof r.reference_issue !== "boolean" || typeof r.cannot_assess !== "boolean" || !["", "yes", "no", "uncertain"].includes(r.material_difference) || typeof r.updated_at !== "string") throw new Error("Ungültige Bewertung.");
      if (!keys(r.positions, labels) || labels.some(l => r.positions[l] !== null && (!Number.isInteger(r.positions[l]) || r.positions[l] < 1 || r.positions[l] > 4))) throw new Error("Ungültige Rangwerte.");
      if (r.status === "ranked") {
        if (r.cannot_assess || stable(groups(r.positions)) !== stable(r.rank_groups)) throw new Error("Rangfolge und Rangwerte widersprechen sich.");
      } else if (r.rank_groups !== null) throw new Error("Offene und nicht beurteilbare Fälle haben keine Rangfolge.");
      if (r.status === "ungradable" && (!r.cannot_assess || !r.notes.trim())) throw new Error("Nichtbeurteilbarkeit benötigt eine Begründung.");
      if (value.finalized_at && r.status === "draft") throw new Error("Ein endgültiger Abschluss darf keine offenen Fälle enthalten.");
      result[r.task_id] = JSON.parse(JSON.stringify(r));
    }
    if (Object.keys(result).length !== ids.size) throw new Error("Die Sicherung muss alle Fälle enthalten.");
    return result;
  }
  const relation = (a, b) => a > b ? 0 : a === b ? 1 : 2; // worse, tie, better
  function summarize(rows, total) {
    const matrix = [[0,0,0],[0,0,0],[0,0,0]];
    let full = 0, pairMatches = 0;
    for (const row of rows) {
      const names = Object.keys(row.left).sort(), [target, baseline] = row.focus_pair;
      if (names.length !== 4 || !keys(row.right, names) || !names.includes(target) || !names.includes(baseline) || target === baseline) throw new Error("Vergleichbare Antworten fehlen.");
      matrix[relation(row.left[target], row.left[baseline])][relation(row.right[target], row.right[baseline])]++;
      let matches = 0;
      for (let i = 0; i < 4; i++) for (let j = i + 1; j < 4; j++) if (relation(row.left[names[i]], row.left[names[j]]) === relation(row.right[names[i]], row.right[names[j]])) matches++;
      pairMatches += matches; if (matches === 6) full++;
    }
    const n = rows.length, rowTotals = matrix.map(r => r.reduce((a,b) => a+b,0)), colTotals = [0,1,2].map(j => matrix.reduce((a,r) => a+r[j],0));
    let observed = 0, expected = 0;
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
      const w = 1 - Math.abs(i-j)/2;
      if (n) { observed += w*matrix[i][j]/n; expected += w*rowTotals[i]*colTotals[j]/(n*n); }
    }
    const ratio = value => n ? value/n : null;
    return {compared_questions:n, excluded_questions:total-n, focus_matrix:matrix,
      focus_exact_agreement:ratio(matrix[0][0]+matrix[1][1]+matrix[2][2]),
      focus_linear_weighted_kappa:n && Math.abs(1-expected)>1e-12 ? (observed-expected)/(1-expected) : null,
      focus_preference_reversal_rate:ratio(matrix[0][2]+matrix[2][0]),
      left_favourable_rate:ratio(rowTotals[1]+rowTotals[2]), right_favourable_rate:ratio(colTotals[1]+colTotals[2]),
      right_minus_left_favourable_pp:n ? 100*(colTotals[1]+colTotals[2]-rowTotals[1]-rowTotals[2])/n : null,
      complete_ranking_agreement:ratio(full), all_pairwise_agreement:n ? pairMatches/(6*n) : null};
  }
  function participantSummary(packet, response) {
    const records = validate(response, packet);
    if (!response.finalized_at) throw new Error("Die Übersicht ist erst nach dem endgültigen Abschluss verfügbar.");
    const rows = packet.tasks.filter(t => records[t.task_id].status === "ranked").map(t => {
      const ref = packet.completion_feedback[t.task_id];
      return {left:midranks(records[t.task_id].rank_groups), right:midranks(ref.rank_groups), focus_pair:ref.focus_pair};
    });
    return summarize(rows, packet.task_count);
  }
  function envelope(packet, response) {
    validate(response, packet);
    return {format:"legal-expert-return-v2", packet, response, agreement:response.finalized_at ? participantSummary(packet, response) : null};
  }
  const percent = value => value === null ? "nicht berechenbar" : (100*value).toFixed(1).replace(".", ",") + " %";
  const number = value => value === null ? "nicht berechenbar" : value.toFixed(2).replace(".", ",");
  function summaryHTML(s, left = "Sie", right = "LLM") {
    return `<p><strong>${s.compared_questions}</strong> vergleichbare Fragen; ${s.excluded_questions} wegen Nichtbeurteilbarkeit ausgeschlossen.</p><table class="agreement-table"><thead><tr><th>Kennzahl</th><th>Ergebnis</th></tr></thead><tbody>
      <tr><td>Komprimiert vs. unkomprimiert: gleiche Entscheidung (schlechter / gleich / besser)</td><td>${percent(s.focus_exact_agreement)}</td></tr>
      <tr><td>Linear gewichtetes Kappa für diesen Vergleich</td><td>${number(s.focus_linear_weighted_kappa)}</td></tr>
      <tr><td>Entgegengesetzte Präferenz für diesen Vergleich</td><td>${percent(s.focus_preference_reversal_rate)}</td></tr>
      <tr><td>Vollständige Vierer-Rangfolge identisch, einschließlich Gleichständen</td><td>${percent(s.complete_ranking_agreement)}</td></tr>
      <tr><td>Übereinstimmung über alle sechs Antwortpaare, je Frage gemittelt</td><td>${percent(s.all_pairwise_agreement)}</td></tr>
      <tr><td>Komprimiert mindestens gleich gut: ${left} / ${right}</td><td>${percent(s.left_favourable_rate)} / ${percent(s.right_favourable_rate)}</td></tr>
      <tr><td>Differenz zugunsten komprimierter Antworten (${right} minus ${left})</td><td>${number(s.right_minus_left_favourable_pp)} Prozentpunkte</td></tr></tbody></table>
      <p class="small">Deskriptive Übersicht, keine Signifikanz- oder Äquivalenzprüfung. Übereinstimmung ist kein Beweis rechtlicher Richtigkeit. Sechs Antwortpaare sind keine sechs unabhängigen Fragen. Kappa kann bei konstanten Kategorien undefiniert sein.</p>`;
  }
  window.ExpertAgreement = Object.freeze({stable, keys, midranks, groups, unpack, validate, summarize, participantSummary, envelope, summaryHTML});
})();
