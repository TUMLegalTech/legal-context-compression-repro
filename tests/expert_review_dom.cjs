/* Exercise the offline expert app with synthetic clicks only; no service. */
"use strict";
const assert = require("assert");
const fs = require("fs");
const {JSDOM, VirtualConsole} = require("jsdom");
const html = fs.readFileSync(0, "utf8");
const packet = JSON.parse(html.split('<script id="review-data" type="application/json">')[1].split("</script>")[0]);
const storageKey = "expert-ranking-v1:" + packet.study_id + ":" + packet.reviewer_code;
const windows = [];
const wait = () => new Promise(resolve => setTimeout(resolve, 25));
const clone = value => JSON.parse(JSON.stringify(value));
async function app(options = {}) {
  const errors = [], downloads = [];
  const console = new VirtualConsole();
  console.on("jsdomError", error => errors.push(error.message));
  const dom = new JSDOM(html, {
    url: options.file ? "file:///portable-app/index.html" : "http://offline-test.invalid/",
    runScripts:"dangerously", pretendToBeVisual:true, virtualConsole:console,
    beforeParse(w) {
      if (options.saved !== undefined) w.localStorage.setItem(storageKey, options.saved);
      if (options.previous !== undefined) w.localStorage.setItem(storageKey + ":previous", options.previous);
      if (options.quota) w.Storage.prototype.setItem = () => { throw new Error("Test quota exceeded"); };
      if (options.silentWrite) w.Storage.prototype.setItem = () => {};
      w.URL.createObjectURL = blob => { downloads.push(blob); return "blob:offline-test"; };
      w.URL.revokeObjectURL = () => {};
      w.HTMLAnchorElement.prototype.click = function () {};
    }
  });
  windows.push(dom.window);
  const w = dom.window, $ = id => w.document.getElementById(id);
  const change = (id, value, event = "change") => {
    if (typeof value === "boolean") $(id).checked = value;
    else $(id).value = value;
    $(id).dispatchEvent(new w.Event(event, {bubbles:true}));
  };
  const read = blob => new Promise((resolve, reject) => {
    const reader = new w.FileReader();
    reader.onload = () => resolve(JSON.parse(reader.result));
    reader.onerror = reject;
    reader.readAsText(blob);
  });
  const download = async () => {
    const count = downloads.length;
    $("download").click();
    assert.strictEqual(downloads.length, count + 1, $("notice").textContent);
    return read(downloads[downloads.length - 1]);
  };
  const upload = async value => {
    Object.defineProperty($("import"), "files", {configurable:true,
      value:[new w.File([JSON.stringify(value)], "backup.json", {type:"application/json"})]});
    $("import").dispatchEvent(new w.Event("change", {bubbles:true}));
    await wait(); await wait();
  };
  const select = n => {
    const button = w.document.querySelector('[data-task="' + packet.tasks[n].task_id + '"]');
    assert(button, "Task navigation missing"); button.click();
  };
  await wait();
  assert.strictEqual($("error").hidden, true, $("error").textContent);
  assert.strictEqual(w.PWNED, undefined, "Reference text executed as code");
  return {w, $, change, select, download, upload, errors};
}

(async () => {
  assert(packet.tasks.length >= 5, "Test needs at least five tasks");
  const ui = await app(), {$, change, select} = ui;
  assert.strictEqual(ui.w.document.querySelectorAll(".answer").length, 4);
  assert.strictEqual(ui.w.document.querySelectorAll(".case-button").length, packet.task_count);
  assert.strictEqual(ui.w.document.querySelector(".reference .text").textContent, packet.tasks[0].gold);
  for (const l of ["A","B","C","D"]) {
    assert.strictEqual($("rank-" + l).value, "");
    assert.strictEqual(ui.w.document.querySelector('[data-answer="' + l + '"] .answer-text').textContent, packet.tasks[0].answers[l]);
  }
  assert($("confirm").disabled);
  assert($("save-state").textContent.includes("✓ Im Browser gespeichert"));
  assert(JSON.parse(ui.w.localStorage.getItem(storageKey)).judgments.every(r => r.status === "draft"));
  const initial = await ui.download();
  assert(initial.judgments.every(r => r.status === "draft" && r.rank_groups === null && !r.cannot_assess));
  assert(initial.judgments.every(r => Object.values(r.positions).every(v => v === null)));
  change("rank-A", "1"); change("rank-B", "1"); change("rank-C", "2"); change("rank-D", "4");
  assert.deepStrictEqual(JSON.parse(ui.w.localStorage.getItem(storageKey)).judgments[0].positions, {A:1,B:1,C:2,D:4});
  assert(ui.w.localStorage.getItem(storageKey + ":previous"), "Keep the previous verified snapshot");
  assert.strictEqual($("rank-preview").textContent, "A = B → C → D");
  assert.strictEqual((await ui.download()).judgments[0].status, "draft", "Dropdowns must not auto-confirm");
  change("notes", '<img src=x onerror="window.PWNED=true"> Testnotiz', "input");
  change("reference-issue", true); change("material", "yes");
  $("confirm").click();
  $("confirm").click();
  assert($("case-position").textContent.includes("Fall 2 /"));
  assert.strictEqual(JSON.parse(ui.w.localStorage.getItem(storageKey)).judgments[1].status, "draft", "Double-click must not rank the next question");
  select(0);
  assert.strictEqual($("rank-B").value, "1");
  assert($("reference-issue").checked);
  assert.strictEqual($("material").value, "yes");
  assert.strictEqual(ui.w.PWNED, undefined);
  $("next").click();
  change("ungradable", true);
  assert($("confirm").disabled, "Abstention requires a reason");
  assert($("rank-A").disabled);
  change("notes", "Test: Ich kann diesen Fall nicht beurteilen.", "input");
  $("next").click(); $("previous").click();
  assert($("ungradable").checked, "Draft abstention intent must survive navigation");
  $("expand").click();
  assert($("ungradable").checked, "Expanding answers must not reset draft intent");
  const draftResume = await app({saved:ui.w.localStorage.getItem(storageKey)});
  assert(draftResume.$("ungradable").checked, "Draft abstention must survive reload");
  assert(!draftResume.$("confirm").disabled);
  $("confirm").click();
  $("all-tied").click();
  assert.strictEqual($("rank-preview").textContent, "A = B = C = D");
  assert.strictEqual((await ui.download()).judgments[2].status, "draft");
  $("confirm").click();
  const completed = await ui.download();
  assert.deepStrictEqual(completed.judgments[0].rank_groups, [["A","B"],["C"],["D"]]);
  assert.strictEqual(completed.judgments[1].status, "ungradable");
  assert.strictEqual(completed.judgments[1].rank_groups, null);
  assert.deepStrictEqual(completed.judgments[2].rank_groups, [["A","B","C","D"]]);
  assert.strictEqual($("progress-bar").value, 3);
  assert($("finished").hidden);
  change("filter", "ranked");
  assert.strictEqual(ui.w.document.querySelectorAll(".case-button").length, 2);
  change("filter", "ungradable");
  assert.strictEqual(ui.w.document.querySelectorAll(".case-button").length, 1);
  change("filter", "all");

  const restored = await app({saved:JSON.stringify(completed)});
  assert.deepStrictEqual((await restored.download()).judgments, completed.judgments);
  restored.select(0); restored.change("notes", "A revised synthetic note", "input");
  const revised = await restored.download();
  assert.strictEqual(revised.judgments[0].status, "draft", "Editing a grade requires renewed confirmation");
  assert.strictEqual(revised.judgments[0].rank_groups, null);
  assert.strictEqual(restored.$("progress-bar").value, 2);

  const imported = await app();
  await imported.upload(completed);
  assert(imported.$("notice").textContent.includes("Sicherung geprüft"), imported.$("notice").textContent + " / " + imported.errors.join("; "));
  assert.deepStrictEqual((await imported.download()).judgments, completed.judgments);
  await imported.upload(initial);
  assert.deepStrictEqual((await imported.download()).judgments, completed.judgments, "Blank backup must not erase completed work");
  for (const corruption of ["packet", "reviewer", "duplicate", "missing", "rank_groups"]) {
    const bad = clone(completed);
    if (corruption === "packet") bad.packet_sha256 = "wrong";
    if (corruption === "reviewer") bad.reviewer_code = "another-expert";
    if (corruption === "duplicate") bad.judgments.push(clone(bad.judgments[0]));
    if (corruption === "missing") bad.judgments.pop();
    if (corruption === "rank_groups") bad.judgments[0].rank_groups = [["A","B","C","D"]];
    await imported.upload(bad);
    assert(imported.$("notice").textContent.includes("Sicherung nicht geladen"));
    assert.deepStrictEqual((await imported.download()).judgments, completed.judgments);
  }
  imported.select(0); imported.change("notes", "Conflicting new synthetic note", "input");
  const beforeConflict = await imported.download();
  await imported.upload(completed);
  assert(imported.$("notice").textContent.includes("abweichende Bewertungen"));
  assert.deepStrictEqual((await imported.download()).judgments, beforeConflict.judgments);

  for (const options of [{file:true}, {quota:true}, {silentWrite:true}]) {
    const blocked = await app(options);
    blocked.$("all-tied").click(); blocked.$("confirm").click();
    assert.strictEqual(blocked.$("storage-warning").hidden, false);
    assert(blocked.$("next").disabled && blocked.$("filter").disabled);
    assert(blocked.$("case-position").textContent.includes("Fall 1 /"), "Failed save must not advance automatically");
    assert(Array.from(blocked.w.document.querySelectorAll(".case-button")).every(b => b.disabled));
    const file = await blocked.download();
    assert.strictEqual(file.judgments[0].status, "ranked", "Storage failure must still allow manual export");
    assert.strictEqual(file.judgments[1].status, "draft");
    assert(!blocked.$("next").disabled && !blocked.$("filter").disabled);
    blocked.$("confirm").click();
    assert(blocked.$("case-position").textContent.includes("Fall 2 /"), "A backup permits continuing without changing the grade");
  }
  const corrupt = await app({saved:"unparseable-original-test-data"});
  corrupt.$("all-tied").click(); corrupt.$("confirm").click();
  assert.strictEqual(corrupt.w.localStorage.getItem(storageKey), "unparseable-original-test-data");
  assert.strictEqual((await corrupt.download()).judgments[0].status, "ranked");

  const recovered = await app({saved:"broken-current-snapshot", previous:JSON.stringify(completed)});
  assert(recovered.$("storage-warning").textContent.includes("vorherige gültige Sicherung"));
  assert.deepStrictEqual((await recovered.download()).judgments, completed.judgments);
  assert.strictEqual(recovered.w.localStorage.getItem(storageKey), "broken-current-snapshot");

  const lateQuota = await app({saved:JSON.stringify(completed)});
  const lastVerified = lateQuota.w.localStorage.getItem(storageKey);
  lateQuota.w.Storage.prototype.setItem = () => { throw new Error("Test quota after progress"); };
  lateQuota.change("rank-A", "1");
  assert(!lateQuota.$("storage-warning").hidden && lateQuota.$("previous").disabled && lateQuota.$("next").disabled);
  assert.strictEqual(lateQuota.w.localStorage.getItem(storageKey), lastVerified);
  await lateQuota.download();
  assert(!lateQuota.$("previous").disabled);

  const conflict = await app();
  conflict.w.localStorage.setItem(storageKey, "another-tab-data");
  conflict.$("all-tied").click();
  assert(!conflict.$("storage-warning").hidden);
  assert.strictEqual(conflict.w.localStorage.getItem(storageKey), "another-tab-data");
  assert.strictEqual((await conflict.download()).judgments[0].status, "draft");

  const cleared = await app({saved:JSON.stringify(completed)});
  cleared.w.localStorage.clear();
  cleared.w.dispatchEvent(new cleared.w.StorageEvent("storage", {key:null}));
  assert(!cleared.$("storage-warning").hidden && cleared.$("next").disabled);
  assert.deepStrictEqual((await cleared.download()).judgments, completed.judgments);
  assert(!cleared.$("next").disabled);

  // Completion and empty-filter states use a separate synthetic browser session.
  const finishFile = clone(initial);
  finishFile.judgments.forEach(r => {
    r.status = "ranked"; r.positions = {A:1,B:1,C:1,D:1}; r.rank_groups = [["A","B","C","D"]];
  });
  const finish = await app({saved:JSON.stringify(finishFile)});
  assert.strictEqual(finish.$("finished").hidden, false);
  finish.change("filter", "open");
  assert.strictEqual(finish.w.document.querySelectorAll(".answer").length, 0);
  assert(finish.$("previous").disabled && finish.$("next").disabled);
  for (const instance of [ui, draftResume, restored, imported, corrupt, recovered, lateQuota, conflict, cleared, finish]) assert.deepStrictEqual(instance.errors, []);
  windows.forEach(w => w.close());
  console.log(JSON.stringify({status:"passed", questions:packet.question_count, checks:[
    "initially blank", "exact anonymous text and Gold", "tie preview and explicit confirmation",
    "draft abstention persistence", "confirmed abstention has no rank", "all-tie option", "filtering",
    "downloaded backup schema", "saved-session restore", "edits need confirmation", "backup import",
    "strict and conflict-safe merge", "disabled storage fallback", "quota failure", "corrupt storage preserved",
    "concurrent storage protection", "no executable evidence text", "completion and empty filter",
    "read-verified autosave", "double-click protection", "silent write failure", "navigation blocked until backup",
    "previous snapshot recovery", "quota failure after progress", "browser storage deletion warning"
  ], synthetic_export:completed}));
})().catch(error => {
  console.error(error); windows.forEach(w => w.close()); process.exitCode = 1;
});
