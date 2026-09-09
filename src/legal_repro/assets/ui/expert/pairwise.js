/* Offline, blinded A/B review. No condition key or automated grades are included. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const labels = ["A", "B"];
  const esc = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const keys = (value, expected) => value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).sort().join("|") === expected.slice().sort().join("|");
  const recordKeys = ["task_id","status","positions","rank_groups","notes","reference_issue","material_difference","cannot_assess","updated_at"];
  const exportKeys = ["schema_version","study_id","packet_sha256","reviewer_code","revision","exported_at","judgments"];
  const blank = id => ({task_id:id,status:"draft",positions:{A:null,B:null},rank_groups:null,notes:"",reference_issue:false,material_difference:"",cannot_assess:false,updated_at:""});
  const choices = {A:{A:1,B:2}, tie:{A:1,B:1}, B:{A:2,B:1}};
  const wording = {A:"A besser",tie:"Gleichstand",B:"B besser"};
  let packet, records = {}, index = 0, revision = 0, storedRevision = -1, exportedRevision = 0;
  let storageKey, storedRaw = null, storageReady = false;
  const current = () => records[packet.tasks[index].task_id];
  function groups(positions) {
    if (!keys(positions, labels) || labels.some(l => !Number.isInteger(positions[l]) || positions[l] < 1 || positions[l] > 2) || Math.min(positions.A, positions.B) !== 1) throw new Error("Ungültiger Antwortvergleich.");
    return positions.A === positions.B ? [["A","B"]] : positions.A < positions.B ? [["A"],["B"]] : [["B"],["A"]];
  }
  function validate(value) {
    if (!keys(value, exportKeys) || value.schema_version !== 1) throw new Error("Unbekanntes Dateiformat.");
    for (const key of ["study_id","reviewer_code","packet_sha256"]) if (value[key] !== packet[key]) throw new Error("Diese Sicherung gehört zu einem anderen Bewertungspaket.");
    if (!Number.isInteger(value.revision) || value.revision < 0 || typeof value.exported_at !== "string" || !Array.isArray(value.judgments)) throw new Error("Ungültige Sicherungsdaten.");
    const ids = new Set(packet.tasks.map(t => t.task_id)), result = {};
    for (const r of value.judgments) {
      if (!keys(r, recordKeys) || !ids.has(r.task_id) || result[r.task_id]) throw new Error("Unbekannter oder doppelter Fall.");
      if (!["draft","ranked","ungradable"].includes(r.status) || typeof r.notes !== "string" || r.notes.length > 10000 || typeof r.reference_issue !== "boolean" || typeof r.cannot_assess !== "boolean" || !["","yes","no","uncertain"].includes(r.material_difference) || typeof r.updated_at !== "string") throw new Error("Ungültige Bewertung.");
      if (!keys(r.positions, labels) || labels.some(l => r.positions[l] !== null && (!Number.isInteger(r.positions[l]) || r.positions[l] < 1 || r.positions[l] > 2))) throw new Error("Ungültige Rangwerte.");
      if (r.status === "ranked") {
        if (r.cannot_assess || JSON.stringify(groups(r.positions)) !== JSON.stringify(r.rank_groups)) throw new Error("Widersprüchliche Bewertung.");
      } else if (r.rank_groups !== null) throw new Error("Ein offener oder nicht beurteilbarer Fall darf keine Rangfolge haben.");
      if (r.status === "ungradable" && (!r.cannot_assess || !r.notes.trim())) throw new Error("Nichtbeurteilbarkeit benötigt eine Begründung.");
      result[r.task_id] = JSON.parse(JSON.stringify(r));
    }
    if (Object.keys(result).length !== ids.size) throw new Error("Die Sicherung muss alle Fälle enthalten, auch offene.");
    return result;
  }
  function exportData() {
    return {schema_version:1,study_id:packet.study_id,packet_sha256:packet.packet_sha256,reviewer_code:packet.reviewer_code,
      revision,exported_at:new Date().toISOString(),judgments:packet.tasks.map(t => records[t.task_id])};
  }
  function unsafe() { return revision > Math.max(storedRevision, exportedRevision); }
  function warn(message) {
    storageReady = false;
    $("storage-warning").hidden = false;
    $("storage-warning").textContent = message + " Bitte jetzt Ergebnisse sichern. Ihre aktuelle Arbeit bleibt in diesem Tab; ohne Sicherung nicht schließen.";
    $("save-state").textContent = "Nicht dauerhaft gespeichert – Ergebnisse sichern.";
  }
  function persist() {
    if (!storageReady) return false;
    try {
      if (window.localStorage.getItem(storageKey) !== storedRaw) { warn("Eine andere Sitzung hat die Browserdaten verändert. Nichts wurde überschrieben."); return false; }
      const next = JSON.stringify(exportData());
      if (storedRaw !== null) window.localStorage.setItem(storageKey + ":previous", storedRaw);
      window.localStorage.setItem(storageKey, next);
      if (window.localStorage.getItem(storageKey) !== next) throw new Error("Speicherung nicht bestätigt");
      storedRaw = next;
      storedRevision = revision;
      $("save-state").textContent = "✓ Im Browser gespeichert · " + new Date().toLocaleTimeString("de-DE", {hour:"2-digit",minute:"2-digit"});
      return true;
    } catch (_) { warn("Die Browser-Speicherung funktioniert nicht."); return false; }
  }
  function selected(r) { return r.status !== "ranked" ? null : r.positions.A === r.positions.B ? "tie" : r.positions.A < r.positions.B ? "A" : "B"; }
  function progress() {
    const ranked = Object.values(records).filter(r => r.status === "ranked").length;
    const abstained = Object.values(records).filter(r => r.status === "ungradable").length;
    const done = ranked + abstained;
    $("progress").textContent = `${done} / ${packet.task_count} bearbeitet` + (abstained ? ` · ${abstained} nicht beurteilbar` : "");
    $("progress-bar").max = packet.task_count; $("progress-bar").value = done;
    $("finished").hidden = done !== packet.task_count;
    for (const option of $("jump").options) {
      const r = records[packet.tasks[Number(option.value)].task_id];
      option.textContent = String(Number(option.value) + 1) + (r.status === "ranked" ? " ✓" : r.status === "ungradable" ? " – nicht beurteilbar" : " – offen");
    }
    const r = current(), choice = selected(r);
    for (const key of Object.keys(choices)) $("choose-" + key).setAttribute("aria-pressed", String(choice === key));
    $("selection").textContent = choice ? "Ihre Auswahl: " + wording[choice] : r.status === "ungradable" ? "Nicht beurteilbar gespeichert." : "Noch nicht bewertet.";
    $("ungradable").disabled = !r.notes.trim();
    $("previous").disabled = index === 0 || unsafe();
    $("jump").disabled = unsafe();
    $("next").disabled = r.status === "draft" || unsafe() || (index === packet.tasks.length - 1 && done === packet.task_count);
    $("next").textContent = index === packet.tasks.length - 1 && done < packet.task_count ? "Zum offenen Fall →" : "Weiter →";
  }
  function changed() {
    current().updated_at = new Date().toISOString(); revision++;
    const saved = persist(); progress();
    $("notice").textContent = saved ? "" : "Bitte Ergebnisse sichern, bevor Sie fortfahren.";
  }
  function choose(value) {
    const r = current();
    r.positions = Object.assign({}, choices[value]); r.rank_groups = groups(r.positions);
    r.status = "ranked"; r.cannot_assess = false;
    changed();
    if (!unsafe()) $("notice").textContent = "Gespeichert. Weiter führt zur nächsten Frage.";
  }
  function noteChanged() {
    const r = current(); r.notes = $("notes").value; r.reference_issue = $("reference-issue").checked;
    if (r.status === "ungradable" && !r.notes.trim()) r.status = "draft";
    changed();
  }
  function show() {
    const task = packet.tasks[index], r = current();
    $("case-position").textContent = `${index + 1} / ${packet.task_count}`;
    $("jump").value = String(index);
    $("case").innerHTML = `<h2 class="question">${esc(task.question)}</h2><section class="reference"><h3>Referenzantwort</h3><div class="text">${esc(task.gold)}</div></section><div class="answers">${labels.map(l => `<section class="answer" data-answer="${l}"><h3>Antwort ${l}</h3><div class="answer-text text">${esc(task.answers[l])}</div></section>`).join("")}</div>`;
    $("notes").value = r.notes; $("reference-issue").checked = r.reference_issue;
    $("extras").open = Boolean(r.notes || r.reference_issue || r.cannot_assess);
    $("assessment").hidden = false;
    progress();
  }
  function navigate(next) {
    if (unsafe() || next < 0 || next >= packet.tasks.length) { $("jump").value = String(index); return; }
    index = next; show(); $("case").focus(); $("notice").textContent = "";
    if (Object.values(records).filter(r => r.status !== "draft").length % 10 === 0 && revision > exportedRevision) $("notice").textContent = "Bitte regelmäßig Ergebnisse sichern – besonders vor einer Pause.";
  }
  function semantic(r) { return JSON.stringify([r.status,r.positions.A,r.positions.B,r.rank_groups,r.notes,r.reference_issue,r.material_difference,r.cannot_assess]); }
  function importData(value) {
    const incoming = validate(value), merged = {};
    for (const task of packet.tasks) {
      const id = task.task_id, old = records[id], next = incoming[id];
      if (semantic(old) === semantic(next) || semantic(old) === semantic(blank(id))) merged[id] = next;
      else if (semantic(next) === semantic(blank(id))) merged[id] = old;
      else throw new Error("Abweichende Bewertungen: Die aktuelle Sitzung wurde nicht überschrieben. Bitte beide Dateien aufbewahren und die Studienleitung kontaktieren.");
    }
    records = merged; revision = Math.max(revision, value.revision) + 1;
    persist();
    const next = packet.tasks.findIndex(t => records[t.task_id].status === "draft");
    index = next < 0 ? 0 : next; show();
    $("notice").textContent = "Sicherung geprüft und geladen.";
  }
  function download() {
    try {
      const value = exportData(); validate(value);
      const blob = new Blob([JSON.stringify(value, null, 2)], {type:"application/json;charset=utf-8"});
      const url = window.URL.createObjectURL(blob), a = document.createElement("a");
      a.href = url; a.download = `Bewertungen_${packet.reviewer_code}_${new Date().toISOString().replace(/[:.]/g,"-")}.json`;
      document.body.appendChild(a); a.click(); a.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
      exportedRevision = revision; progress();
      $("notice").textContent = "Download angefordert. Bitte im Download-Ordner prüfen. Am Ende die neueste JSON-Datei zurücksenden.";
      if (!storageReady) $("save-state").textContent = "Sicherung angefordert – bitte prüfen, dass die Datei gespeichert wurde.";
    } catch (error) { $("notice").textContent = "Sicherung fehlgeschlagen: " + error.message; }
  }
  function start() {
    try {
      packet = JSON.parse($("review-data").textContent);
      if (packet.schema_version !== 1 || !Array.isArray(packet.tasks) || !packet.tasks.length || packet.task_count !== packet.tasks.length || packet.question_count !== packet.task_count) throw new Error("Ungültiges Bewertungspaket.");
      const ids = new Set();
      for (const task of packet.tasks) {
        if (!keys(task, ["task_id","question","gold","answers"]) || !/^task-[0-9a-f]{24}$/.test(task.task_id) || ids.has(task.task_id) || !keys(task.answers, labels) || [task.question,task.gold,task.answers.A,task.answers.B].some(t => typeof t !== "string" || !t.trim())) throw new Error("Ungültiger oder doppelter Fall.");
        ids.add(task.task_id); records[task.task_id] = blank(task.task_id);
      }
      storageKey = "expert-pairwise-v1:" + packet.study_id + ":" + packet.reviewer_code;
      try {
        storedRaw = window.localStorage.getItem(storageKey);
        if (storedRaw !== null) { const saved = JSON.parse(storedRaw); records = validate(saved); revision = saved.revision; storedRevision = revision; }
        storageReady = true;
        persist(); // Probe writes and readback before any actual judgment.
      } catch (_) {
        warn("Browserdaten sind nicht verfügbar oder beschädigt. Vorhandene Daten wurden nicht überschrieben.");
        try {
          const earlier = window.localStorage.getItem(storageKey + ":previous");
          if (earlier !== null) {
            const value = JSON.parse(earlier); records = validate(value); revision = value.revision;
            $("storage-warning").textContent += " Die vorherige gültige Sicherung wurde geladen; bitte zuletzt bearbeitete Fälle prüfen.";
          }
        } catch (_) { /* Keep a blank form, never overwrite unreadable data. */ }
      }
      const firstOpen = packet.tasks.findIndex(t => records[t.task_id].status === "draft");
      index = firstOpen < 0 ? 0 : firstOpen;
      $("study-info").textContent = `${packet.question_count} Fragen · zwei Antworten pro Frage`;
      $("jump").innerHTML = packet.tasks.map((t, i) => `<option value="${i}">${i + 1}</option>`).join("");
      $("download").disabled = false; $("import").disabled = false;
      show();
      for (const key of Object.keys(choices)) $("choose-" + key).addEventListener("click", () => choose(key));
      $("notes").addEventListener("input", noteChanged);
      $("reference-issue").addEventListener("change", noteChanged);
      $("ungradable").addEventListener("click", () => {
        if (!current().notes.trim()) return;
        Object.assign(current(), {status:"ungradable",cannot_assess:true,positions:{A:null,B:null},rank_groups:null});
        changed();
      });
      $("previous").addEventListener("click", () => navigate(index - 1));
      $("next").addEventListener("click", () => {
        if ($("next").disabled) return;
        navigate(index + 1 < packet.tasks.length ? index + 1 : packet.tasks.findIndex(t => records[t.task_id].status === "draft"));
      });
      $("jump").addEventListener("change", () => navigate(Number($("jump").value)));
      $("download").addEventListener("click", download);
      $("import").addEventListener("change", () => {
        const file = $("import").files[0]; if (!file) return;
        if (file.size > 20000000) { $("notice").textContent = "Die Sicherung ist zu groß."; return; }
        const reader = new FileReader();
        reader.onload = () => { try { importData(JSON.parse(reader.result)); } catch (error) { $("notice").textContent = "Sicherung nicht geladen: " + error.message; } $("import").value = ""; };
        reader.onerror = () => { $("notice").textContent = "Sicherung konnte nicht gelesen werden."; };
        try { reader.readAsText(file); } catch (error) { $("notice").textContent = "Sicherung konnte nicht geöffnet werden: " + error.message; }
      });
      window.addEventListener("storage", event => {
        if ((event.key === storageKey && event.newValue !== storedRaw) || event.key === null) {
          storedRevision = -1; warn("Browserdaten wurden in einem anderen Tab verändert. Automatisches Überschreiben wurde verhindert."); progress();
        }
      });
      window.addEventListener("beforeunload", event => {
        if (revision > exportedRevision) { event.preventDefault(); event.returnValue = "Bitte vorher Ergebnisse sichern."; }
      });
    } catch (error) { $("error").hidden = false; $("error").textContent = "Das Bewertungspaket konnte nicht geladen werden: " + error.message; }
  }
  window.setTimeout(start, 0);
})();
