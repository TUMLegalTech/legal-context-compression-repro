/* Participant app. Optional anonymous feedback is gated by final submission. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const letters = ["A", "B", "C", "D"];
  const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const sameKeys = (value, keys) => value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).sort().join("|") === keys.slice().sort().join("|");
  let packet, judgments = {}, active = "", revision = 0, expanded = false;
  let storageKey, storedRaw = null, storageWorking = false, storedRevision = -1, lastExportRevision = 0;
  let completionMode = false, finalizedAt = null;
  const recordKeys = ["task_id", "status", "positions", "rank_groups", "notes", "reference_issue", "material_difference", "cannot_assess", "updated_at"];
  const exportKeys = ["schema_version", "study_id", "packet_sha256", "reviewer_code", "revision", "exported_at", "judgments"];
  const blank = id => ({task_id:id, status:"draft", positions:{A:null,B:null,C:null,D:null}, rank_groups:null, notes:"", reference_issue:false, material_difference:"", cannot_assess:false, updated_at:""});
  const current = () => judgments[active];
  function groups(positions) {
    if (!sameKeys(positions, letters) || letters.some(l => !Number.isInteger(positions[l]) || positions[l] < 1 || positions[l] > 4)) throw new Error("Bitte für alle vier Antworten einen Rang wählen.");
    if (Math.min(...letters.map(l => positions[l])) !== 1) throw new Error("Mindestens eine Antwort muss Rang 1 erhalten.");
    return Array.from(new Set(letters.map(l => positions[l]))).sort().map(rank => letters.filter(l => positions[l] === rank));
  }
  function validate(value) {
    if (completionMode) return window.ExpertAgreement.validate(value, packet);
    if (!sameKeys(value, exportKeys) || value.schema_version !== 1) throw new Error("Unbekanntes Dateiformat.");
    for (const key of ["study_id", "packet_sha256", "reviewer_code"]) if (value[key] !== packet[key]) throw new Error("Die Datei gehört zu einem anderen Bewertungspaket oder einer anderen Kennung.");
    if (!Number.isInteger(value.revision) || value.revision < 0 || typeof value.exported_at !== "string" || !Array.isArray(value.judgments)) throw new Error("Ungültige Sicherungsdaten.");
    const ids = new Set(packet.tasks.map(t => t.task_id));
    const result = {};
    for (const r of value.judgments) {
      if (!sameKeys(r, recordKeys) || !ids.has(r.task_id) || result[r.task_id]) throw new Error("Unbekannter oder doppelter Fall in der Sicherung.");
      if (!["draft","ranked","ungradable"].includes(r.status) || typeof r.notes !== "string" || r.notes.length > 10000 || typeof r.reference_issue !== "boolean" || typeof r.cannot_assess !== "boolean" || !["","yes","no","uncertain"].includes(r.material_difference) || typeof r.updated_at !== "string") throw new Error("Ungültige Bewertung.");
      if (!sameKeys(r.positions, letters) || letters.some(l => r.positions[l] !== null && (!Number.isInteger(r.positions[l]) || r.positions[l] < 1 || r.positions[l] > 4))) throw new Error("Ungültige Rangwerte.");
      if (r.status === "ranked") {
        if (r.cannot_assess || JSON.stringify(groups(r.positions)) !== JSON.stringify(r.rank_groups)) throw new Error("Rangfolge und Rangwerte stimmen nicht überein.");
      } else if (r.rank_groups !== null) throw new Error("Unbestätigte Bewertungen dürfen keine Rangfolge enthalten.");
      if (r.status === "ungradable" && (!r.cannot_assess || !r.notes.trim())) throw new Error("Nichtbeurteilbarkeit benötigt eine Begründung und die entsprechende Auswahl.");
      result[r.task_id] = JSON.parse(JSON.stringify(r));
    }
    if (Object.keys(result).length !== ids.size) throw new Error("Die Sicherung muss auch alle noch offenen Fälle enthalten.");
    return result;
  }
  function exportData() {
    const value = {schema_version:packet.schema_version, study_id:packet.study_id, packet_sha256:packet.packet_sha256, reviewer_code:packet.reviewer_code,
      revision, exported_at:new Date().toISOString(), judgments:packet.tasks.map(t => judgments[t.task_id])};
    if (completionMode) value.finalized_at = finalizedAt;
    return value;
  }
  function unsafe() { return revision > Math.max(storedRevision, lastExportRevision); }
  function warnStorage(message) {
    storageWorking = false;
    $("storage-warning").hidden = false;
    $("storage-warning").textContent = message + " Ihre aktuelle Arbeit bleibt in diesem Tab. Bitte regelmäßig eine Sicherungsdatei herunterladen.";
    $("save-state").textContent = "Nur im aktuellen Tab – Sicherung herunterladen.";
  }
  function persist() {
    if (!storageWorking) { $("save-state").textContent = "Nur im aktuellen Tab – Sicherung herunterladen."; return false; }
    try {
      if (window.localStorage.getItem(storageKey) !== storedRaw) {
        storedRevision = -1;
        warnStorage("Die gespeicherte Sitzung wurde in einem anderen Tab verändert. Nichts wurde überschrieben.");
        return false;
      }
      const serialized = JSON.stringify(exportData());
      if (storedRaw !== null) window.localStorage.setItem(storageKey + ":previous", storedRaw);
      window.localStorage.setItem(storageKey, serialized);
      if (window.localStorage.getItem(storageKey) !== serialized) throw new Error("Speicherung nicht bestätigt");
      storedRaw = serialized;
      storedRevision = revision;
      if (completionMode && finalizedAt) {
        window.localStorage.setItem(storageKey + ":final", serialized);
        if (window.localStorage.getItem(storageKey + ":final") !== serialized) throw new Error("Abschluss nicht bestätigt");
      }
      $("save-state").textContent = "✓ Im Browser gespeichert · " + new Date().toLocaleTimeString("de-DE", {hour:"2-digit",minute:"2-digit"});
      return true;
    } catch (_) { warnStorage("Die Browser-Speicherung ist nicht verfügbar oder wurde nicht bestätigt."); return false; }
  }
  function semantic(r) {
    return JSON.stringify([r.status, letters.map(l => r.positions[l]), r.rank_groups, r.notes, r.reference_issue, r.material_difference, r.cannot_assess]);
  }
  function importData(value) {
    const incoming = validate(value);
    if (completionMode) {
      value = window.ExpertAgreement.unpack(value, packet);
      if (finalizedAt) {
        if (value.finalized_at !== finalizedAt || packet.tasks.some(t => semantic(incoming[t.task_id]) !== semantic(judgments[t.task_id]))) throw new Error("Nach dem endgültigen Abschluss sind Bewertungen gesperrt.");
        $("notice").textContent = "Dieser endgültige Abschluss ist bereits geladen.";
        return;
      }
    }
    const merged = {};
    for (const task of packet.tasks) {
      const id = task.task_id, old = judgments[id], next = incoming[id];
      if (semantic(old) === semantic(next) || semantic(old) === semantic(blank(id))) merged[id] = next;
      else if (semantic(next) === semantic(blank(id))) merged[id] = old;
      else throw new Error("Die Sicherung enthält abweichende Bewertungen. Die aktuelle Sitzung wurde nicht verändert. Bitte sichern und die Studienleitung kontaktieren.");
    }
    judgments = merged;
    if (completionMode) finalizedAt = value.finalized_at;
    revision = Math.max(revision, value.revision) + 1;
    persist();
    active = (packet.tasks.find(t => judgments[t.task_id].status === "draft") || packet.tasks[0]).task_id;
    $("filter").value = "all";
    refresh();
    $("notice").textContent = "Sicherung geprüft und geladen. Bereits vorhandene, abweichende Bewertungen werden niemals still überschrieben.";
  }
  function progress() {
    const counts = {draft:0,ranked:0,ungradable:0};
    Object.values(judgments).forEach(r => counts[r.status]++);
    const finished = counts.ranked + counts.ungradable;
    $("progress").textContent = `${finished} / ${packet.task_count} bearbeitet · ${counts.ranked} Rangfolgen · ${counts.ungradable} nicht beurteilbar`;
    $("progress-bar").max = packet.task_count;
    $("progress-bar").value = finished;
    $("finished").hidden = finished !== packet.task_count;
    for (const button of $("cases").querySelectorAll("button")) {
      const r = judgments[button.dataset.task];
      button.classList.toggle("done", r.status !== "draft");
      button.querySelector("span").textContent = r.status === "ranked" ? "Rangfolge bestätigt" : r.status === "ungradable" ? "Nicht beurteilbar" : r.updated_at ? "Entwurf · noch nicht bestätigt" : "Noch offen";
    }
    navigationState();
    if (completionMode) {
      $("finished").hidden = true;
      $("submission").hidden = finished !== packet.task_count || Boolean(finalizedAt);
      $("agreement").hidden = !finalizedAt;
      if (finalizedAt) {
        $("download").textContent = "FINAL-Ergebnisdatei herunterladen";
        $("agreement-body").innerHTML = window.ExpertAgreement.summaryHTML(window.ExpertAgreement.participantSummary(packet, exportData()));
        $("finished").hidden = true;
      }
    }
  }
  function navigationState() {
    const visible = visibleTasks(), index = visible.findIndex(t => t.task_id === active);
    $("previous").disabled = unsafe() || index <= 0;
    $("next").disabled = unsafe() || index < 0 || index >= visible.length - 1;
    $("filter").disabled = unsafe();
    for (const button of $("cases").querySelectorAll("button")) button.disabled = unsafe();
  }
  function visibleTasks() {
    const filter = $("filter").value;
    return packet.tasks.filter(t => filter === "all" || (filter === "open" ? judgments[t.task_id].status === "draft" : judgments[t.task_id].status === filter));
  }
  function renderPreview() {
    const ungradable = $("ungradable").checked;
    letters.forEach(l => { $("rank-" + l).disabled = ungradable; });
    $("all-tied").disabled = ungradable;
    $("confirm").textContent = ungradable ? "Nichtbeurteilbarkeit bestätigen & weiter" : "Bewertung bestätigen & weiter";
    try {
      if (ungradable) {
        $("rank-preview").textContent = "Keine Rangfolge · nicht beurteilbar";
        if (!current().notes.trim()) throw new Error("Bitte begründen Sie die Nichtbeurteilbarkeit.");
      } else {
        $("rank-preview").textContent = groups(current().positions).map(g => g.join(" = ")).join(" → ");
      }
      $("confirm").disabled = false;
      $("validation").textContent = current().status === "draft" ? "Bitte ausdrücklich bestätigen." : "Diese Bewertung ist bestätigt. Änderungen müssen erneut bestätigt werden.";
    } catch (error) {
      if (!ungradable) $("rank-preview").textContent = "Noch keine vollständige Rangfolge";
      $("confirm").disabled = true;
      $("validation").textContent = error.message;
    }
    if (finalizedAt) {
      letters.forEach(l => { $("rank-" + l).disabled = true; });
      $("all-tied").disabled = true; $("confirm").disabled = true;
      $("validation").textContent = "Endgültig abgeschlossen. Die ursprünglichen Bewertungen sind gesperrt.";
    }
  }
  function edited() {
    if (finalizedAt) return;
    const r = current();
    letters.forEach(l => { r.positions[l] = $("rank-" + l).value ? Number($("rank-" + l).value) : null; });
    r.notes = $("notes").value;
    r.reference_issue = $("reference-issue").checked;
    r.material_difference = $("material").value;
    r.cannot_assess = $("ungradable").checked;
    r.status = "draft";
    r.rank_groups = null;
    r.updated_at = new Date().toISOString();
    revision++;
    persist(); progress(); renderPreview();
  }
  function show() {
    const task = packet.tasks.find(t => t.task_id === active);
    navigationState();
    $("assessment-title").parentElement.hidden = !task;
    $("expand").disabled = !task;
    if (!task) { $("case").innerHTML = "<p>Keine Fälle in dieser Ansicht. Wählen Sie einen anderen Filter.</p>"; $("case-position").textContent = ""; return; }
    const number = packet.tasks.findIndex(t => t.task_id === active) + 1;
    $("case-position").textContent = `Fall ${number} / ${packet.task_count}`;
    $("case").innerHTML = `<div class="case-caption">Fall ${number}</div><h2 class="question">${esc(task.question)}</h2><details class="reference" open><summary>Referenzantwort</summary><div class="text">${esc(task.gold)}</div></details><div class="answers ${expanded ? "expanded" : ""}">${letters.map(l => `<section class="answer" data-answer="${l}"><div class="answer-header"><h3>Antwort ${l}</h3><label class="rank-control" for="rank-${l}">Rang<select id="rank-${l}"><option value="">–</option>${[1,2,3,4].map(v => `<option value="${v}">${v}</option>`).join("")}</select></label></div><div class="answer-text text">${esc(task.answers[l])}</div></section>`).join("")}</div>`;
    const r = current();
    letters.forEach(l => { $("rank-" + l).value = r.positions[l] === null ? "" : String(r.positions[l]); $("rank-" + l).addEventListener("change", edited); });
    $("notes").value = r.notes;
    $("reference-issue").checked = r.reference_issue;
    $("material").value = r.material_difference;
    $("ungradable").checked = r.cannot_assess;
    for (const id of ["notes", "reference-issue", "material", "ungradable"]) $(id).disabled = Boolean(finalizedAt);
    $("extras").open = Boolean(r.notes || r.reference_issue || r.material_difference || r.cannot_assess);
    for (const button of $("cases").querySelectorAll("button")) button.setAttribute("aria-current", String(button.dataset.task === active));
    renderPreview();
  }
  function refresh() {
    const visible = visibleTasks();
    if (!visible.some(t => t.task_id === active)) active = visible.length ? visible[0].task_id : "";
    $("cases").innerHTML = visible.map(t => `<button type="button" class="case-button" data-task="${t.task_id}">Fall ${packet.tasks.findIndex(task => task.task_id === t.task_id) + 1}<span></span></button>`).join("");
    for (const button of $("cases").querySelectorAll("button")) button.addEventListener("click", () => { if (unsafe()) return; active = button.dataset.task; show(); $("case").focus(); });
    progress(); show();
  }
  function move(delta) {
    if (unsafe()) return;
    const visible = visibleTasks();
    const index = visible.findIndex(t => t.task_id === active) + delta;
    if (index >= 0 && index < visible.length) { active = visible[index].task_id; show(); $("case").focus(); }
  }
  function confirmJudgment() {
    if ($("confirm").disabled || finalizedAt) return;
    const r = current(), previousId = active;
    if (r.status === "draft") {
      if ($("ungradable").checked) { r.status = "ungradable"; r.rank_groups = null; }
      else { r.rank_groups = groups(r.positions); r.status = "ranked"; }
      r.updated_at = new Date().toISOString();
      revision++;
      persist();
    }
    if (unsafe()) {
      progress(); renderPreview();
      $("notice").textContent = "Bewertung nur in diesem Tab. Bitte eine Sicherung herunterladen, bevor Sie zum nächsten Fall wechseln.";
      return;
    }
    const index = packet.tasks.findIndex(t => t.task_id === previousId);
    const remaining = packet.tasks.slice(index + 1).concat(packet.tasks.slice(0, index)).find(t => judgments[t.task_id].status === "draft");
    active = remaining ? remaining.task_id : previousId;
    refresh();
    $("case").focus();
    if (!remaining && completionMode) $("submission").scrollIntoView({block:"start"});
    const completed = Object.values(judgments).filter(item => item.status !== "draft").length;
    $("notice").textContent = completed % 10 === 0 ? "Bewertung bestätigt. Bitte jetzt eine Sicherungsdatei herunterladen." : "Bewertung bestätigt.";
  }
  function download() {
    try {
      const value = exportData();
      validate(value);
      const payload = completionMode ? window.ExpertAgreement.envelope(packet, value) : value;
      const blob = new Blob([JSON.stringify(payload, null, 2)], {type:"application/json;charset=utf-8"});
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const prefix = completionMode ? (finalizedAt ? "FINAL" : "SICHERUNG") : "Bewertungen";
      a.download = `${prefix}_${packet.reviewer_code}_${new Date().toISOString().replace(/[:.]/g,"-")}.json`;
      document.body.appendChild(a); a.click(); a.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
      lastExportRevision = revision;
      navigationState();
      $("notice").textContent = "Download angefordert. Bitte prüfen, dass die JSON-Datei gespeichert wurde. Diese Datei am Ende an die Studienleitung senden.";
      return true;
    } catch (error) { $("notice").textContent = "Download fehlgeschlagen: " + error.message; return false; }
  }
  function finalize() {
    if (!completionMode || finalizedAt || packet.tasks.some(t => judgments[t.task_id].status === "draft")) return;
    if (!window.confirm("Endgültig abschließen? Danach sind Ihre Bewertungen gesperrt und die LLM-Übereinstimmung wird sichtbar. Bitte erst nach dem Abschluss beider Personen über die Ergebnisse sprechen.")) return;
    finalizedAt = new Date().toISOString(); revision++;
    persist();
    download(); // Self-contained frozen return; check the browser's Downloads folder.
    refresh();
    $("agreement").scrollIntoView({block:"start"});
  }
  function start() {
    try {
      packet = JSON.parse($("review-data").textContent);
      completionMode = packet.schema_version === 2;
      const packetKeys = ["schema_version","study_id","reviewer_code","question_count","task_count","tasks","packet_sha256"];
      if (completionMode) packetKeys.push("completion_feedback");
      if (!sameKeys(packet, packetKeys) || ![1,2].includes(packet.schema_version) || !Array.isArray(packet.tasks) || !packet.tasks.length || packet.tasks.length !== packet.task_count || (completionMode && !window.ExpertAgreement)) throw new Error("Ungültiges Bewertungspaket.");
      packet.tasks.forEach(task => {
        if (!sameKeys(task, ["task_id","question","gold","answers"]) || !/^task-[0-9a-f]{24}$/.test(task.task_id) || judgments[task.task_id] || !sameKeys(task.answers, letters) || [task.question,task.gold,...Object.values(task.answers)].some(text => typeof text !== "string" || !text.trim())) throw new Error("Ungültiger oder doppelter Fall.");
        judgments[task.task_id] = blank(task.task_id);
      });
      if (completionMode) {
        if (!sameKeys(packet.completion_feedback, packet.tasks.map(t => t.task_id))) throw new Error("Unvollständiger Vergleichsschlüssel.");
        for (const ref of Object.values(packet.completion_feedback)) {
          if (!sameKeys(ref, ["rank_groups", "focus_pair"]) || !Array.isArray(ref.focus_pair) || ref.focus_pair.length !== 2 || ref.focus_pair[0] === ref.focus_pair[1] || ref.focus_pair.some(l => !letters.includes(l))) throw new Error("Ungültiger Vergleichsschlüssel.");
          window.ExpertAgreement.midranks(ref.rank_groups);
        }
        $("completion-guide").hidden = false;
      }
      storageKey = "expert-ranking-v1:" + packet.study_id + ":" + packet.reviewer_code;
      try {
        storedRaw = window.localStorage.getItem(storageKey);
        if (storedRaw !== null) { const saved = JSON.parse(storedRaw); judgments = validate(saved); revision = saved.revision; storedRevision = revision; finalizedAt = saved.finalized_at || null; }
        if (completionMode) {
          const finalRaw = window.localStorage.getItem(storageKey + ":final");
          if (finalRaw !== null) {
            const saved = JSON.parse(finalRaw), checked = validate(saved);
            if (!saved.finalized_at) throw new Error("Ungültiger Abschluss");
            judgments = checked; revision = saved.revision; finalizedAt = saved.finalized_at;
          }
        }
        storageWorking = true;
        persist(); // Probe storage and verify readback before the first judgment.
      } catch (_) {
        warnStorage("Browserdaten sind nicht verfügbar oder nicht lesbar. Vorhandene Daten wurden nicht überschrieben.");
        try {
          const earlier = (completionMode && window.localStorage.getItem(storageKey + ":final")) || window.localStorage.getItem(storageKey + ":previous");
          if (earlier !== null) {
            const saved = JSON.parse(earlier); judgments = validate(saved); revision = saved.revision; finalizedAt = saved.finalized_at || null;
            $("storage-warning").textContent += " Die vorherige gültige Sicherung wurde geladen; bitte zuletzt bearbeitete Fälle prüfen.";
          }
        } catch (_) { /* Keep unreadable snapshots untouched. */ }
      }
      active = (packet.tasks.find(t => judgments[t.task_id].status === "draft") || packet.tasks[0]).task_id;
      $("study-info").textContent = `${packet.question_count} Fragen · ${packet.task_count} Bewertungsfälle · Kennung ${packet.reviewer_code}`;
      $("download").disabled = false; $("import").disabled = false;
      refresh();
      $("filter").addEventListener("change", refresh);
      $("previous").addEventListener("click", () => move(-1));
      $("next").addEventListener("click", () => move(1));
      for (const id of ["ungradable", "reference-issue", "material"]) $(id).addEventListener("change", edited);
      $("notes").addEventListener("input", edited);
      $("all-tied").addEventListener("click", () => { if (finalizedAt) return; letters.forEach(l => { $("rank-" + l).value = "1"; }); edited(); });
      $("confirm").addEventListener("click", confirmJudgment);
      $("finalize").addEventListener("click", finalize);
      $("download").addEventListener("click", download);
      $("expand").addEventListener("click", () => { expanded = !expanded; $("expand").setAttribute("aria-pressed", String(expanded)); $("expand").textContent = expanded ? "Antwortenhöhe begrenzen" : "Antworten vollständig ausklappen"; show(); });
      $("import").addEventListener("change", () => {
        const file = $("import").files[0];
        if (!file) return;
        $("notice").textContent = "Sicherung wird gelesen und geprüft …";
        if (file.size > 20000000) { $("notice").textContent = "Die Sicherungsdatei ist zu groß."; return; }
        const reader = new FileReader();
        reader.onload = () => { try { importData(JSON.parse(reader.result)); } catch (error) { $("notice").textContent = "Sicherung nicht geladen: " + error.message; } $("import").value = ""; };
        reader.onerror = () => { $("notice").textContent = "Die Datei konnte nicht gelesen werden."; };
        try { reader.readAsText(file); }
        catch (error) { $("notice").textContent = "Die Datei konnte nicht geöffnet werden: " + error.message; }
      });
      window.addEventListener("storage", event => {
        if ((event.key === storageKey && event.newValue !== storedRaw) || event.key === null) {
          storedRevision = -1;
          warnStorage("Ein anderer Tab hat die Sitzung verändert. Automatisches Überschreiben wurde verhindert.");
          navigationState();
        }
      });
      window.addEventListener("beforeunload", event => { if (revision > lastExportRevision) { event.preventDefault(); event.returnValue = "Bitte vorher eine Sicherung herunterladen."; } });
    } catch (error) { $("error").hidden = false; $("error").textContent = "Bewertungspaket konnte nicht geladen werden: " + error.message; }
  }
  window.setTimeout(start, 0);
})();
