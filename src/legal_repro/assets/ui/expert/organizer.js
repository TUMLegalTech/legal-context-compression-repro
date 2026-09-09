/* Private organizer: align answer identities, never anonymous letters across people. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id), A = window.ExpertAgreement;
  const data = JSON.parse($("review-data").textContent), codes = ["annotator_1", "annotator_2"];
  const primary = "legal_llmlingua2-r1p1";
  const names = {raw:"Unkomprimiert", "legal_llmlingua2-r1p1":"Legal LLMLingua-2 · r=1.10", oracle_bgb_paragraph_ids:"Paragrafen-IDs", no_context:"Ohne Kontext"};
  const conditions = Object.keys(names), loaded = {};
  let report = null;
  const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  function validateReturn(value) {
    if (!value || value.format !== "legal-expert-return-v2" || !value.response || !codes.includes(value.response.reviewer_code)) throw new Error("Eine zugewiesene FINAL-Datei wird benötigt.");
    const code = value.response.reviewer_code;
    A.validate(value, data.reviewers[code].packet);
    if (!value.response.finalized_at) throw new Error("Diese Datei ist nur eine Sicherung. Bitte die endgültige FINAL-Datei anfordern.");
    return code;
  }
  function combine() {
    const byRow = {}, summaries = {};
    for (const code of codes) {
      const source = data.reviewers[code], response = loaded[code].response, records = A.validate(loaded[code], source.packet);
      summaries[code + "_vs_llm"] = A.participantSummary(source.packet, response);
      for (const task of source.packet.tasks) {
        const key = source.tasks[task.task_id], r = records[task.task_id];
        const semantic = r.status === "ranked" ? Object.fromEntries(Object.entries(A.midranks(r.rank_groups)).map(([label, rank]) => [key.blind_to_condition[label], rank])) : {};
        const answers = Object.fromEntries(Object.entries(key.answers).map(([label, answer]) => [answer.condition_id, Object.assign({}, answer, {text:task.answers[label]})]));
        if (!byRow[key.row_id]) byRow[key.row_id] = {row_id:key.row_id, context_cluster_id:key.context_cluster_id, question:task.question, gold:task.gold, answers,
          llm_ranking:key.llm_rankings[primary], reviewers:{}};
        const row = byRow[key.row_id];
        if (row.reviewers[code] || row.question !== task.question || row.gold !== task.gold || row.context_cluster_id !== key.context_cluster_id || A.stable(row.answers) !== A.stable(answers) || A.stable(row.llm_ranking) !== A.stable(key.llm_rankings[primary])) throw new Error("Die Abgaben betreffen nicht dieselben Fragen und Antworten.");
        row.reviewers[code] = {task_id:task.task_id, blind_to_condition:key.blind_to_condition, expert_judgment:r,
          expert_condition_midranks:semantic, expert_condition_rank_groups:r.status === "ranked" ? r.rank_groups.map(g => g.map(label => key.blind_to_condition[label])) : null};
      }
    }
    const cases = Object.values(byRow), pairs = [];
    if (cases.length !== data.reviewers.annotator_1.packet.question_count) throw new Error("Die Frageanzahl stimmt nicht überein.");
    for (const row of cases) {
      if (!A.keys(row.reviewers, codes)) throw new Error("Eine der Personen hat andere Fragen bearbeitet.");
      const left = row.reviewers.annotator_1, right = row.reviewers.annotator_2;
      if (left.expert_judgment.status === "ranked" && right.expert_judgment.status === "ranked") pairs.push({left:left.expert_condition_midranks, right:right.expert_condition_midranks, focus_pair:[primary,"raw"]});
    }
    summaries.annotator_1_vs_annotator_2 = A.summarize(pairs, cases.length);
    return {format:"legal-expert-combined-v1", question_count:cases.length, context_cluster_count:new Set(cases.map(c => c.context_cluster_id)).size,
      agreement:summaries, cases, submitted_returns:loaded, inference:"Descriptive only; clustered uncertainty and equivalence are not established."};
  }
  function matrixHTML(s, left, right) {
    const labels = ["schlechter", "gleich", "besser"];
    return `<details><summary>Entscheidungsmatrix: komprimiert gegenüber unkomprimiert</summary><p>Zeilen: ${left}; Spalten: ${right}. Zahlen sind Fragen, keine unabhängigen Antwortpaare.</p><table class="agreement-table"><thead><tr><th></th>${labels.map(l => `<th>${l}</th>`).join("")}</tr></thead><tbody>${s.focus_matrix.map((row,i) => `<tr><th>${labels[i]}</th>${row.map(n => `<td>${n}</td>`).join("")}</tr>`).join("")}</tbody></table></details>`;
  }
  function llmRanks(row) {
    return Object.fromEntries(Object.entries(row.llm_ranking.midranks).map(([role,rank]) => [role === "matching_compressed" ? primary : role, rank]));
  }
  function renderCases() {
    const differentOnly = $("case-filter").value === "different";
    $("organizer-cases").innerHTML = report.cases.map((row,i) => {
      const llm = llmRanks(row), a = row.reviewers.annotator_1.expert_condition_midranks, b = row.reviewers.annotator_2.expert_condition_midranks;
      const different = A.stable(a) !== A.stable(b) || A.stable(a) !== A.stable(llm);
      if (differentOnly && !different) return "";
      const notes = codes.map(code => {
        const r = row.reviewers[code].expert_judgment;
        return `<section><h3>${code}: ${r.status === "ranked" ? "Rangfolge abgegeben" : "Nicht beurteilbar"}</h3><p class="text">${esc(r.notes || "Keine Anmerkung.")}</p><p class="small">Referenzhinweis: ${r.reference_issue ? "ja" : "nein"} · Rechtlich relevante Unterschiede: ${esc(r.material_difference || "keine Angabe")}</p></section>`;
      }).join("");
      const cards = conditions.map(condition => {
        const answer = row.answers[condition];
        const ranks = codes.map(code => {
          const person = row.reviewers[code], label = Object.keys(person.blind_to_condition).find(l => person.blind_to_condition[l] === condition);
          return `${code}: Antwort ${label}, Rang ${person.expert_condition_midranks[condition] === undefined ? "–" : person.expert_condition_midranks[condition]}`;
        }).join(" · ");
        const score = answer.scores.find(s => s.replicate === 1), d = score ? score.dimensions : {};
        return `<section class="answer"><h3>${names[condition]}</h3><p class="small">${ranks} · LLM-Rang ${llm[condition]}</p><div class="answer-text text">${esc(answer.text)}</div><p class="small">LLM-Scores (nicht menschlich): Ergebnis ${esc(d.outcome_correctness)} · Begründung ${esc(d.legal_reasoning_correctness)} · Rechtsgrundlage ${esc(d.legal_basis_correctness)}</p></section>`;
      }).join("");
      return `<details class="organizer-case"><summary>Frage ${i+1}${different ? " · Abweichung / Nichtbeurteilbarkeit" : " · übereinstimmende Rangfolgen"}: ${esc(row.question.slice(0,130))}</summary><h3 class="question">${esc(row.question)}</h3><div class="reference"><h3>Referenzantwort</h3><div class="text">${esc(row.gold)}</div></div><div class="answers">${cards}</div><div class="reviewer-notes">${notes}</div><details><summary>Originalbegründung des LLM (mit ursprünglichen Bezeichnungen)</summary><p class="text">${esc(row.llm_ranking.explanation)}</p></details></details>`;
    }).join("");
  }
  function render() {
    $("load-state").textContent = codes.map(code => code + ": " + (loaded[code] ? "endgültige Abgabe geladen" : "fehlt")).join(" · ");
    if (!codes.every(code => loaded[code])) return;
    report = combine();
    $("overview").hidden = false; $("all-cases").hidden = false; $("download-combined").disabled = false;
    $("sample-info").textContent = `${report.question_count} Fragen · ${report.context_cluster_count} Kontextgruppen · beide unabhängigen Bewertungen bleiben erhalten.`;
    $("summaries").innerHTML = [["annotator_1_vs_llm","Annotator 1","LLM"],["annotator_2_vs_llm","Annotator 2","LLM"],["annotator_1_vs_annotator_2","Annotator 1","Annotator 2"]].map(([key,left,right]) => `<details class="instructions" open><summary>${left} ↔ ${right}</summary>${A.summaryHTML(report.agreement[key], left, right)}${matrixHTML(report.agreement[key],left,right)}</details>`).join("");
    renderCases();
  }
  const read = file => new Promise((resolve,reject) => {
    if (file.size > 20000000) { reject(new Error("Die Datei ist zu groß.")); return; }
    const reader = new FileReader();
    reader.onload = () => { try { resolve(JSON.parse(reader.result)); } catch (_) { reject(new Error("Ungültige JSON-Datei.")); } };
    reader.onerror = () => reject(new Error("Datei konnte nicht gelesen werden."));
    reader.readAsText(file);
  });
  $("returns").addEventListener("change", async () => {
    const files = Array.from($("returns").files), pending = {};
    $("error").hidden = true;
    try {
      for (const file of files) {
        const value = await read(file), code = validateReturn(value);
        if (pending[code] || (loaded[code] && A.stable(loaded[code].response) !== A.stable(value.response))) throw new Error("Mehrere oder abweichende Abgaben derselben Person. Nichts wurde ersetzt.");
        pending[code] = value;
      }
      Object.assign(loaded,pending); render();
    } catch (error) { $("error").hidden = false; $("error").textContent = error.message; }
    $("returns").value = "";
  });
  $("case-filter").addEventListener("change", () => { if (report) renderCases(); });
  $("download-combined").addEventListener("click", () => {
    if (!report) return;
    const url = window.URL.createObjectURL(new Blob([JSON.stringify(report,null,2)], {type:"application/json;charset=utf-8"}));
    const a = document.createElement("a"); a.href = url; a.download = "GESAMTDATEN_zwei_annotatoren.json";
    document.body.appendChild(a); a.click(); a.remove(); window.setTimeout(() => window.URL.revokeObjectURL(url),1000);
    $("load-state").textContent = "Download angefordert. Bitte die Gesamtdaten und beide Original-FINAL-Dateien aufbewahren.";
  });
})();
