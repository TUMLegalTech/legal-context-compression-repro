/* CPU-only browser DOM checks; all annotations below are synthetic test data. */
"use strict";
const assert = require("assert"), fs = require("fs");
const {JSDOM, VirtualConsole} = require("jsdom");
const html = fs.readFileSync(0, "utf8");
const packet = JSON.parse(html.split('<script id="review-data" type="application/json">')[1].split("</script>")[0]);
const storageKey = "expert-pairwise-v1:" + packet.study_id + ":" + packet.reviewer_code;
const windows = [], errors = [];
const wait = () => new Promise(resolve => setTimeout(resolve, 25));
const clone = value => JSON.parse(JSON.stringify(value));
async function app(options = {}) {
  const blobs = [], virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", error => errors.push(error.message));
  const dom = new JSDOM(html, {
    url:options.file ? "file:///portable/index.html" : "http://offline-test.invalid/",
    runScripts:"dangerously", pretendToBeVisual:true, virtualConsole,
    beforeParse(w) {
      if (options.saved !== undefined) w.localStorage.setItem(storageKey, options.saved);
      if (options.previous !== undefined) w.localStorage.setItem(storageKey + ":previous", options.previous);
      if (options.quota) w.Storage.prototype.setItem = () => { throw new Error("Synthetic quota failure"); };
      if (options.dropWrites) w.Storage.prototype.setItem = () => {};
      w.URL.createObjectURL = blob => { blobs.push(blob); return "blob:offline-test"; };
      w.URL.revokeObjectURL = () => {};
      w.HTMLAnchorElement.prototype.click = function () {};
    }
  });
  const w = dom.window, $ = id => w.document.getElementById(id); windows.push(w);
  const change = (id, value, type = "change") => {
    if (typeof value === "boolean") $(id).checked = value; else $(id).value = value;
    $(id).dispatchEvent(new w.Event(type, {bubbles:true}));
  };
  const download = async () => {
    const count = blobs.length; $("download").click();
    assert.strictEqual(blobs.length, count + 1, $("notice").textContent);
    return new Promise((resolve, reject) => {
      const reader = new w.FileReader(); reader.onload = () => resolve(JSON.parse(reader.result)); reader.onerror = reject;
      reader.readAsText(blobs[blobs.length - 1]);
    });
  };
  const upload = async value => {
    Object.defineProperty($("import"), "files", {configurable:true,
      value:[new w.File([JSON.stringify(value)], "test-backup.json", {type:"application/json"})]});
    $("import").dispatchEvent(new w.Event("change", {bubbles:true}));
    await wait(); await wait();
  };
  await wait();
  assert.strictEqual($("error").hidden, true, $("error").textContent);
  return {w,$,change,download,upload};
}
(async () => {
  assert(packet.task_count >= 5);
  const ui = await app(), {$,change} = ui;
  assert.strictEqual(ui.w.document.querySelectorAll(".answer").length, 2);
  assert.strictEqual(ui.w.document.querySelectorAll(".choices button").length, 3);
  assert.strictEqual(ui.w.document.querySelector(".reference .text").textContent, packet.tasks[0].gold);
  for (const l of ["A","B"]) assert.strictEqual(ui.w.document.querySelector('[data-answer="' + l + '"] .answer-text').textContent, packet.tasks[0].answers[l]);
  assert($("next").disabled);
  assert(!$("extras").open);
  const initial = await ui.download();
  assert(initial.judgments.every(r => r.status === "draft" && r.rank_groups === null && r.positions.A === null && r.positions.B === null));
  $("choose-A").click();
  assert.strictEqual($("choose-A").getAttribute("aria-pressed"), "true");
  assert.strictEqual($("case-position").textContent, "1 / " + packet.task_count);
  assert.strictEqual(JSON.parse(ui.w.localStorage.getItem(storageKey)).judgments[0].status, "ranked");
  assert($("save-state").textContent.includes("Im Browser gespeichert"));
  $("choose-A").click(); // A double click must not grade a new question.
  assert.strictEqual($("progress-bar").value, 1);
  assert.strictEqual($("case-position").textContent, "1 / " + packet.task_count);
  change("notes", '<img src=x onerror="window.PWNED=true"> Synthetic note', "input");
  change("reference-issue", true);
  assert.strictEqual(JSON.parse(ui.w.localStorage.getItem(storageKey)).judgments[0].status, "ranked");
  assert.strictEqual(ui.w.PWNED, undefined);
  $("next").click(); $("choose-tie").click();
  assert.deepStrictEqual((await ui.download()).judgments[1].rank_groups, [["A","B"]]);
  $("next").click();
  assert($("ungradable").disabled);
  change("notes", "Synthetic abstention reason", "input"); $("ungradable").click();
  const completed = await ui.download();
  assert.strictEqual($("progress-bar").value, 3);
  assert.strictEqual(completed.judgments[2].status, "ungradable");
  assert.strictEqual(completed.judgments[2].rank_groups, null);
  assert(completed.judgments[2].cannot_assess);
  assert(ui.w.localStorage.getItem(storageKey + ":previous"), "Previous snapshot missing");
  const restored = await app({saved:ui.w.localStorage.getItem(storageKey)});
  assert.strictEqual(restored.$("case-position").textContent, "4 / " + packet.task_count);
  assert.deepStrictEqual((await restored.download()).judgments, completed.judgments);
  restored.change("jump", "0"); restored.$("choose-B").click();
  const changed = await restored.download();
  assert.deepStrictEqual(changed.judgments[0].rank_groups, [["B"],["A"]]);
  assert.strictEqual(restored.$("progress-bar").value, 3);
  restored.change("jump", "2"); restored.change("notes", "", "input");
  assert.strictEqual((await restored.download()).judgments[2].status, "draft");
  assert(restored.$("next").disabled);

  const imported = await app(); await imported.upload(completed);
  assert(imported.$("notice").textContent.includes("Sicherung geprüft"), imported.$("notice").textContent);
  assert.deepStrictEqual((await imported.download()).judgments, completed.judgments);
  await imported.upload(initial);
  assert.deepStrictEqual((await imported.download()).judgments, completed.judgments);
  for (const corruption of ["study","packet","four_answers","duplicate","missing","groups","abstention"]) {
    const bad = clone(completed);
    if (corruption === "study") bad.study_id = "wrong";
    if (corruption === "packet") bad.packet_sha256 = "wrong";
    if (corruption === "four_answers") bad.judgments[0].positions = {A:1,B:2,C:3,D:4};
    if (corruption === "duplicate") bad.judgments.push(clone(bad.judgments[0]));
    if (corruption === "missing") bad.judgments.pop();
    if (corruption === "groups") bad.judgments[0].rank_groups = [["A","B"]];
    if (corruption === "abstention") bad.judgments[2].notes = "";
    await imported.upload(bad);
    assert(imported.$("notice").textContent.includes("Sicherung nicht geladen"));
    assert.deepStrictEqual((await imported.download()).judgments, completed.judgments);
  }
  imported.change("jump", "0"); imported.$("choose-B").click();
  const beforeConflict = await imported.download(); await imported.upload(completed);
  assert(imported.$("notice").textContent.includes("Abweichende Bewertungen"));
  assert.deepStrictEqual((await imported.download()).judgments, beforeConflict.judgments);

  for (const options of [{file:true},{quota:true},{dropWrites:true}]) {
    const unavailable = await app(options);
    assert(!unavailable.$("storage-warning").hidden);
    unavailable.$("choose-A").click();
    assert(unavailable.$("next").disabled && unavailable.$("jump").disabled);
    assert.strictEqual((await unavailable.download()).judgments[0].status, "ranked");
    assert(!unavailable.$("next").disabled);
    unavailable.$("next").click();
    assert.strictEqual(unavailable.$("case-position").textContent, "2 / " + packet.task_count);
  }
  const corrupt = await app({saved:"unreadable test data",previous:JSON.stringify(completed)});
  assert.strictEqual(corrupt.w.localStorage.getItem(storageKey), "unreadable test data");
  assert(corrupt.$("storage-warning").textContent.includes("vorherige gültige Sicherung"));
  assert.deepStrictEqual((await corrupt.download()).judgments, completed.judgments);
  const conflict = await app(); conflict.$("choose-A").click();
  conflict.w.localStorage.setItem(storageKey, "another-tab-test-data");
  conflict.$("choose-B").click();
  assert.strictEqual(conflict.w.localStorage.getItem(storageKey), "another-tab-test-data");
  assert(conflict.$("next").disabled && !conflict.$("storage-warning").hidden);
  assert.deepStrictEqual((await conflict.download()).judgments[0].rank_groups, [["B"],["A"]]);

  const finishFile = clone(initial);
  finishFile.judgments.forEach(r => { r.status="ranked"; r.positions={A:1,B:1}; r.rank_groups=[["A","B"]]; });
  const finished = await app({saved:JSON.stringify(finishFile)});
  assert.strictEqual(finished.$("finished").hidden, false);
  assert.strictEqual(finished.$("progress-bar").value, packet.task_count);
  assert.deepStrictEqual(errors, []);
  windows.forEach(w => w.close());
  console.log(JSON.stringify({status:"passed",questions:packet.question_count,checks:[
    "only two exact answers and Gold","three choices with no prefilled grade","immediate read-verified autosave",
    "double click does not grade next question","ties","notes","abstention requires reason","same-session resume",
    "editing previous choices","backup import and export","strict identity checks","no conflicting overwrite",
    "blocked navigation on save failure","previous-snapshot recovery","quota and silent-write failure",
    "concurrent-tab protection","completion state","no script injection"
  ],synthetic_export:completed}));
})().catch(error => { console.error(error); windows.forEach(w => w.close()); process.exitCode=1; });
