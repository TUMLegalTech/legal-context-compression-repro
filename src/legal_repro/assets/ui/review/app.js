/* Offline-only review. All evidence text is escaped, never executed or fetched. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const roles = ["raw", "matching_compressed", "oracle_bgb_paragraph_ids", "no_context"];
  const controlNames = {raw:"Uncompressed", oracle_bgb_paragraph_ids:"Paragraph IDs", no_context:"No context"};
  const metrics = [["outcome_correctness", "Outcome", "Outcome correctness"], ["legal_reasoning_correctness", "Reasoning", "Legal reasoning correctness"], ["legal_basis_correctness", "Legal basis", "Legal basis correctness"]];
  const rankText = rank => Number.isInteger(rank) ? String(rank) : rank.toFixed(1);
  let data, rows, filtered = [], active = "", expanded = false;
  const candidate = () => `${$("method").value}-${$("ratio").value}`;
  const methodOf = condition => condition.slice(0, condition.lastIndexOf("-r"));
  const label = condition => controlNames[condition] || data.methods[methodOf(condition)] || condition;
  const roleLabel = role => role === "matching_compressed" ? label(candidate()) + " · compressed" : controlNames[role];
  const currentRow = () => rows.find(row => row.id === active);

  function scoreGrid(score) {
    return `<div class="score-grid">${metrics.map(([key, short, full]) => `<div class="metric" data-metric="${key}"><span class="metric-label" title="${full}">${short}</span><span class="metric-value">${score.dimensions[key].toFixed(2)}</span><progress max="1" value="${score.dimensions[key]}" aria-label="${full}"></progress></div>`).join("")}</div>`;
  }
  function reasons(score) {
    return `<div class="reason">${metrics.map(([key, , full]) => `<h4>${full}</h4><p class="explanation">${esc(score.reasons[key])}</p>`).join("")}</div>`;
  }
  function blindLabels(rank) {
    return `<div class="rank-labels">${Object.entries(rank.blind_labels).map(([blind, role]) => `<span>${esc(blind)} = ${esc(roleLabel(role))}</span>`).join("")}</div>`;
  }
  function rankOrder(rank) {
    let position = 1;
    return `<div class="rank-order">${rank.groups.map(group => {
      const end = position + group.length - 1;
      const heading = end === position ? `Position ${position}` : `Positions ${position}–${end} · tied`;
      position = end + 1;
      return `<div class="rank-group"><small>${heading}</small>${group.map(role => esc(roleLabel(role))).join(" = ")}</div>`;
    }).join('<span class="rank-arrow" aria-hidden="true">›</span>')}</div>`;
  }
  function rankingPanel(rank) {
    const repeat = rank.retest;
    return `<section class="ranking-panel"><h3>Four-way ranking · primary judgment</h3><p class="caption">Best → worst. Tied answers share positions. This ranking was judged separately from the numerical scores.</p>${rankOrder(rank)}<details><summary>Judge’s ranking explanation and original anonymous labels</summary>${blindLabels(rank)}<p class="explanation">${esc(rank.explanation)}</p></details>${repeat ? `<details class="ranking-repeat"><summary>Reliability repeat · separate judgment</summary><p class="repeat-note">Same answers, another blinded ordering. Not pooled with the primary ranking.</p>${rankOrder(repeat)}${blindLabels(repeat)}<p class="explanation">${esc(repeat.explanation)}</p>${roles.map(role => `<h4>${esc(roleLabel(role))}</h4><p class="explanation">${esc(repeat.reasons[role])}</p>`).join("")}</details>` : '<p class="repeat-note">No ranking repeat was sampled for this comparison.</p>'}</section>`;
  }
  function answerCard(row, conditionId) {
    const condition = row.conditions[conditionId];
    const compressed = !Object.prototype.hasOwnProperty.call(controlNames, conditionId);
    const rank = row.rankings[compressed ? conditionId : candidate()];
    const role = compressed ? "matching_compressed" : conditionId;
    const primary = condition.scores[0];
    const repeat = condition.scores.find(score => score.replicate === 2);
    const method = compressed ? methodOf(conditionId) : "";
    const color = method.startsWith("legal_llm") ? "llmlingua" : method.startsWith("german") ? "selector" : method.startsWith("multi") ? "bge" : method.startsWith("dac") ? "dac" : "";
    const c = condition.compression;
    const subtitle = c ? `${c.requested_ratio.toFixed(2)}× target · ${c.actual_ratio.toFixed(2)}× realized<br>${c.compressed_tokens} / ${c.source_tokens} context tokens${c.no_op ? " · unchanged" : ""}${!c.target_met ? " · target missed" : ""}` : conditionId === "raw" ? "Full supplied statute text" : conditionId === "no_context" ? "No context supplied" : "Ground-truth paragraph identifiers";
    const context = data.contexts[condition.context];
    const title = compressed && $("view").value === "all" ? `${label(conditionId)} · ${c.requested_ratio.toFixed(2)}×` : label(conditionId);
    return `<section class="answer-card ${compressed ? "compressed" : "control"} ${color}" data-condition="${esc(conditionId)}"><div class="card-top"><h3>${esc(title)}</h3><span class="rank-badge" title="Average occupied rank in this method-specific four-answer comparison; 1 is best">Rank ${rankText(rank.midranks[role])}</span></div><p class="card-subtitle">${subtitle}</p>${scoreGrid(primary)}<details><summary>Why these scores? · primary grade</summary>${reasons(primary)}</details><h4 class="answer-title">Answer · ${condition.answer_tokens} tokens</h4><div class="answer-text text" lang="de">${esc(condition.answer)}</div><details><summary>Why this rank?</summary><p class="repeat-note">${compressed ? esc(label(conditionId)) + " · " + c.requested_ratio.toFixed(2) + "×" : "Selected method/target"} four-way comparison.</p><p class="explanation">${esc(rank.reasons[role])}</p>${blindLabelsForCard(rank, compressed ? conditionId : candidate())}</details><details><summary>Exact supplied context</summary>${conditionId === "no_context" ? '<p class="repeat-note">The following is the recorded no-context sentinel, not statute text.</p>' : ""}<div class="context-text text" lang="de">${esc(context) || "(empty)"}</div></details>${repeat ? `<details class="score-repeat"><summary>Score reliability repeat · replicate 2</summary><p class="repeat-note">Separate audit grade; it does not change the primary scores above.</p>${scoreGrid(repeat)}${reasons(repeat)}</details>` : '<p class="repeat-note">No second score replicate sampled.</p>'}</section>`;
  }
  function blindLabelsForCard(rank, comparison) {
    return `<div class="rank-labels">${Object.entries(rank.blind_labels).map(([blind, role]) => `<span>${esc(blind)} = ${esc(role === "matching_compressed" ? label(comparison) + " · compressed" : controlNames[role])}</span>`).join("")}</div>`;
  }
  function comparisonTable(row) {
    return `<details class="comparison-table"><summary>All 15 four-way comparisons for this question</summary><p class="repeat-note">Each row is a separate judgment with the same three control answers. Lower ranks are better; this is not a global method ranking.</p><div class="table-scroll"><table><thead><tr><th>Compression method</th><th>Target</th><th>Uncompressed</th><th>Compressed</th><th>Paragraph IDs</th><th>No context</th></tr></thead><tbody>${data.candidates.map(id => {
      const ranks = row.rankings[id].midranks;
      return `<tr class="${id === candidate() ? "selected" : ""}"><td><button type="button" class="comparison-button" data-comparison="${esc(id)}">${esc(label(id))}</button></td><td>${row.conditions[id].compression.requested_ratio.toFixed(2)}×</td>${roles.map(role => `<td>${rankText(ranks[role])}</td>`).join("")}</tr>`;
    }).join("")}</tbody></table></div></details>`;
  }
  function saveHash() {
    const params = new URLSearchParams({row:active, comparison:candidate(), view:$("view").value});
    if ($("search").value) params.set("q", $("search").value);
    if ($("relation").value !== "any") params.set("filter", $("relation").value);
    history.replaceState(null, "", "#" + params.toString());
  }
  function restoreHash() {
    const params = new URLSearchParams(location.hash.slice(1));
    const comparison = params.get("comparison");
    if (data.candidates.includes(comparison)) {
      $("method").value = methodOf(comparison);
      $("ratio").value = comparison.slice(comparison.lastIndexOf("-r") + 1);
    }
    $("view").value = params.get("view") === "all" ? "all" : "four";
    $("search").value = params.get("q") || "";
    $("relation").value = ["better", "tie", "worse"].includes(params.get("filter")) ? params.get("filter") : "any";
    active = params.get("row") || "";
  }
  function show() {
    const row = currentRow();
    const index = filtered.findIndex(item => item.id === active);
    $("previous").disabled = index <= 0;
    $("next").disabled = index < 0 || index >= filtered.length - 1;
    $("copy-link").disabled = !row;
    $("position").textContent = row ? `${index + 1} / ${filtered.length}` : "0 / 0";
    for (const button of $("question-list").querySelectorAll("button")) {
      button.setAttribute("aria-current", String(button.dataset.row === active));
    }
    if (!row) {
      $("detail").innerHTML = '<p class="empty">No questions match. Clear the search or change the ranking filter.</p>';
      saveHash();
      return;
    }
    const selected = candidate();
    const all = $("view").value === "all";
    const order = all ? ["raw", "oracle_bgb_paragraph_ids", "no_context", ...data.candidates] : ["raw", selected, "oracle_bgb_paragraph_ids", "no_context"];
    $("detail").innerHTML = `<section class="question-header"><div class="row-id">${esc(row.id)} · context ${esc(row.cluster.slice(0, 12))}</div><h2 lang="de">${esc(row.question)}</h2></section><details class="reference" open><summary>Reference answer (Gold)</summary><div class="text" lang="de">${esc(row.gold)}</div></details>${rankingPanel(row.rankings[selected])}${all ? '<p class="all-note">All 18 saved answers. Each compressed rank belongs to its own four-way comparison. Control ranks refer to the selected method/target. Do not read these badges as one 18-answer ranking.</p>' : ""}<div class="cards ${expanded ? "expanded" : ""}">${order.map(id => answerCard(row, id)).join("")}</div>${comparisonTable(row)}`;
    for (const button of $("detail").querySelectorAll("[data-comparison]")) {
      button.addEventListener("click", () => {
        const id = button.dataset.comparison;
        $("method").value = methodOf(id);
        $("ratio").value = id.slice(id.lastIndexOf("-r") + 1);
        $("view").value = "four";
        refresh();
      });
    }
    saveHash();
  }
  function refresh() {
    const needle = $("search").value.trim().toLocaleLowerCase("de");
    const relation = $("relation").value;
    const selected = candidate();
    filtered = rows.filter(row => {
      if (needle && !row.searchText.includes(needle)) return false;
      const ranks = row.rankings[selected].midranks;
      const difference = ranks.matching_compressed - ranks.raw;
      return relation === "any" || (relation === "better" && difference < 0) || (relation === "tie" && difference === 0) || (relation === "worse" && difference > 0);
    });
    if (!filtered.some(row => row.id === active)) active = filtered.length ? filtered[0].id : "";
    $("matches").textContent = `${filtered.length} of ${rows.length} questions`;
    $("question-list").innerHTML = filtered.map(row => `<button class="question-link" type="button" data-row="${esc(row.id)}"><b>Question ${row.number + 1} · ${esc(row.id.split(":").slice(-2).join(":"))}</b><span>${esc(row.question)}</span></button>`).join("");
    for (const button of $("question-list").querySelectorAll("button")) {
      button.addEventListener("click", () => { active = button.dataset.row; show(); });
    }
    show();
  }
  function move(delta) {
    const index = filtered.findIndex(row => row.id === active) + delta;
    if (index >= 0 && index < filtered.length) { active = filtered[index].id; show(); }
  }
  function start() {
    try {
      data = JSON.parse($("review-data").textContent);
      if (data.schema_version !== 1 || !data.meta.read_only || data.rows.length !== data.meta.questions) throw new Error("Invalid review bundle");
      rows = data.rows;
      rows.forEach((row, number) => {
        row.number = number;
        row.searchText = [row.id, row.question, row.gold, ...Object.values(row.conditions).map(c => c.answer)].join("\n").toLocaleLowerCase("de");
      });
      $("coverage").textContent = `${rows.length} questions · ${data.meta.answers.toLocaleString("en")} answers · ${data.meta.primary_rankings.toLocaleString("en")} rankings`;
      $("method").innerHTML = Object.entries(data.methods).map(([id, name]) => `<option value="${esc(id)}">${esc(name)}</option>`).join("");
      $("ratio").innerHTML = Object.entries(data.ratios).map(([id, ratio]) => `<option value="${id}">${ratio.toFixed(2)}×</option>`).join("");
      $("method").disabled = $("ratio").disabled = false;
      $("provenance").innerHTML = `<p>${data.meta.primary_scores.toLocaleString("en")} primary scores + ${data.meta.score_repeats} score repeats; ${data.meta.primary_rankings.toLocaleString("en")} primary rankings + ${data.meta.ranking_repeats} ranking repeats. ${data.meta.clusters} statute-context groups.</p>${Object.entries(data.meta.models).map(([stage, models]) => `<p>${esc(stage)} model: ${models.map(([name]) => esc(name)).join(", ")}</p>`).join("")}<p>Source receipts and ledger hashes were checked at build time; see the companion verification.json.</p>`;
      restoreHash();
      refresh();
      for (const id of ["method", "ratio", "view", "relation"]) $(id).addEventListener("change", refresh);
      $("search").addEventListener("input", refresh);
      $("previous").addEventListener("click", () => move(-1));
      $("next").addEventListener("click", () => move(1));
      $("expand").addEventListener("click", () => {
        expanded = !expanded;
        $("expand").setAttribute("aria-pressed", String(expanded));
        $("expand").textContent = expanded ? "Limit answer height" : "Expand answer text";
        const cards = document.querySelector(".cards");
        if (cards) cards.classList.toggle("expanded", expanded);
      });
      $("copy-link").addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(location.href); $("notice").textContent = "Question link copied. It works with this local review file."; }
        catch { $("notice").textContent = "The question link is in your address bar. Copy it from there."; }
      });
      window.addEventListener("hashchange", () => { restoreHash(); refresh(); });
      document.addEventListener("keydown", event => {
        if (event.ctrlKey || event.metaKey || event.altKey || event.target.closest("input,select,textarea,button,summary")) return;
        if (["ArrowLeft", "ArrowRight"].includes(event.key)) { event.preventDefault(); move(event.key === "ArrowLeft" ? -1 : 1); }
      });
    } catch (error) {
      $("error").hidden = false;
      $("error").textContent = `Could not load the evidence review: ${error.message}. Open the generated index.html, not the source template.`;
      $("coverage").textContent = "Evidence did not load";
    }
  }
  window.setTimeout(start, 0);
})();
