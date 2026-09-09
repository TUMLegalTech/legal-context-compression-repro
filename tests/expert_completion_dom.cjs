/* Synthetic offline workflows; nothing is sent or written to participant files. */
"use strict";
const assert = require("assert"), fs = require("fs");
const {JSDOM, VirtualConsole} = require("jsdom");
const inputs = JSON.parse(fs.readFileSync(0,"utf8")), windows = [];
const wait = () => new Promise(resolve => setTimeout(resolve,25));
const clone = x => JSON.parse(JSON.stringify(x));
const getPacket = html => JSON.parse(html.split('<script id="review-data" type="application/json">')[1].split("</script>")[0]);
async function launch(html, options = {}) {
  const packet = getPacket(html), downloads = [], errors = [], virtual = new VirtualConsole();
  virtual.on("jsdomError", e => errors.push(e.message));
  const key = packet.study_id ? "expert-ranking-v1:" + packet.study_id + ":" + packet.reviewer_code : null;
  const dom = new JSDOM(html, {url:"http://offline-test.invalid/", runScripts:"dangerously", pretendToBeVisual:true, virtualConsole:virtual,
    beforeParse(w) {
      if (options.saved !== undefined) w.localStorage.setItem(key,options.saved);
      if (options.final !== undefined) w.localStorage.setItem(key+":final",options.final);
      if (options.quota) w.Storage.prototype.setItem = () => { throw new Error("Synthetic storage quota"); };
      if (options.silent) w.Storage.prototype.setItem = () => {};
      w.confirm = () => true;
      w.HTMLElement.prototype.scrollIntoView = function () {};
      w.URL.createObjectURL = blob => { downloads.push({blob,name:null}); return "blob:synthetic"; };
      w.URL.revokeObjectURL = () => {};
      w.HTMLAnchorElement.prototype.click = function () { downloads[downloads.length-1].name = this.download; };
    }});
  const w = dom.window, $ = id => w.document.getElementById(id);
  windows.push(w);
  await wait();
  if ($("error")) assert($("error").hidden, $("error").textContent);
  const read = blob => new Promise((resolve,reject) => {
    const r = new w.FileReader(); r.onload = () => resolve(JSON.parse(r.result)); r.onerror = reject; r.readAsText(blob);
  });
  const download = async (id="download") => {
    const n = downloads.length; $(id).click(); assert.strictEqual(downloads.length,n+1);
    return read(downloads[downloads.length-1].blob);
  };
  const upload = async (values, id="import") => {
    const list = Array.isArray(values) ? values : [values];
    Object.defineProperty($(id),"files",{configurable:true,value:list.map((v,i)=>new w.File([JSON.stringify(v)],`test-${i}.json`,{type:"application/json"}))});
    $(id).dispatchEvent(new w.Event("change",{bubbles:true}));
    await wait(); await wait();
  };
  const change = (id,value,event="change") => {
    if (typeof value === "boolean") $(id).checked = value; else $(id).value = value;
    $(id).dispatchEvent(new w.Event(event,{bubbles:true}));
  };
  return {w,$,key,packet,downloads,errors,download,upload,change,read};
}
async function fill(ui, version) {
  for (let i=0;i<ui.packet.tasks.length;i++) {
    const task = ui.packet.tasks[i];
    const button = ui.w.document.querySelector(`[data-task="${task.task_id}"]`);
    if (button.disabled) await ui.download();
    button.click();
    if (version === 1 && i === 1) {
      ui.change("ungradable",true);
      assert(ui.$("confirm").disabled);
      ui.change("notes","Synthetischer Test: nicht beurteilbar.","input");
    } else {
      ui.$("all-tied").click();
      if (i === 0) {
        const [target,baseline] = ui.packet.completion_feedback[task.task_id].focus_pair;
        ui.change("rank-"+target,version===1 ? "4" : "1");
        ui.change("rank-"+baseline,version===1 ? "1" : "4");
        let place=2;
        for (const label of ["A","B","C","D"]) if (![target,baseline].includes(label)) ui.change("rank-"+label,String(place++));
        ui.change("notes",`Synthetische Begründung ${version} <script>window.PWNED=true</script>`,"input");
      }
    }
    ui.$("confirm").click();
  }
  assert.strictEqual(ui.$("progress-bar").value,ui.packet.task_count);
  assert(!ui.$("submission").hidden);
  assert(ui.$("agreement").hidden);
  assert.strictEqual(ui.$("agreement-body").innerHTML,"");
}
(async () => {
  const h1 = inputs.participants.annotator_1, h2 = inputs.participants.annotator_2;
  const ui1 = await launch(h1), ui2 = await launch(h2);
  assert.strictEqual(ui1.packet.schema_version,2);
  assert(ui1.$("submission").hidden && ui1.$("agreement").hidden);
  ui1.$("finalize").click();
  assert(ui1.$("agreement").hidden, "No premature finalization");
  const initial = await ui1.download();
  assert.strictEqual(initial.agreement,null);
  assert.strictEqual(initial.response.finalized_at,null);
  assert.strictEqual(initial.packet.tasks.length,ui1.packet.task_count);
  assert(initial.response.judgments.every(r=>r.status==="draft"));
  assert.throws(()=>ui1.w.ExpertAgreement.participantSummary(ui1.packet,initial.response));
  await fill(ui1,1); await fill(ui2,2);
  const beforeFinal = await ui1.download();
  ui1.w.confirm = () => false; ui1.$("finalize").click();
  assert(ui1.$("agreement").hidden, "Cancelled finalization must not expose feedback");
  ui1.w.confirm = () => true;
  ui1.$("finalize").click(); ui2.$("finalize").click();
  const returns = {annotator_1:await ui1.download(),annotator_2:await ui2.download()};
  for (const ui of [ui1,ui2]) {
    assert(!ui.$("agreement").hidden && ui.$("submission").hidden);
    assert(ui.$("rank-A").disabled && ui.$("notes").disabled && ui.$("confirm").disabled);
    assert(ui.downloads[ui.downloads.length-1].name.startsWith("FINAL_"));
    assert(ui.w.localStorage.getItem(ui.key+":final"));
    assert.strictEqual(ui.w.PWNED,undefined);
  }
  assert.deepStrictEqual(returns.annotator_1.response.judgments,beforeFinal.response.judgments);
  ui1.change("notes","Attempted post-feedback edit","input");
  ui1.$("all-tied").click(); ui1.$("confirm").click();
  assert.deepStrictEqual((await ui1.download()).response.judgments,returns.annotator_1.response.judgments);
  await ui1.upload(beforeFinal);
  assert(ui1.$("notice").textContent.includes("gesperrt"));
  const restored = await launch(h1,{saved:ui1.w.localStorage.getItem(ui1.key)});
  assert(!restored.$("agreement").hidden && restored.$("notes").disabled);
  assert.deepStrictEqual((await restored.download()).response.judgments,returns.annotator_1.response.judgments);
  const recovered = await launch(h1,{saved:"broken-test-main",final:ui1.w.localStorage.getItem(ui1.key+":final")});
  assert(!recovered.$("agreement").hidden && recovered.$("notes").disabled);
  assert.strictEqual(recovered.w.localStorage.getItem(recovered.key),"broken-test-main");
  assert.deepStrictEqual((await recovered.download()).response.judgments,returns.annotator_1.response.judgments);
  const imported = await launch(h1);
  await imported.upload(returns.annotator_1);
  assert(!imported.$("agreement").hidden && imported.$("notes").disabled);
  const wrong = await launch(h1);
  await wrong.upload(returns.annotator_2);
  assert(wrong.$("notice").textContent.includes("Sicherung nicht geladen"));
  assert(wrong.$("agreement").hidden);
  const tampered = clone(returns.annotator_1); tampered.packet.tasks[0].gold = "Altered test reference";
  await wrong.upload(tampered);
  assert(wrong.$("notice").textContent.includes("Sicherung nicht geladen"));

  // Manual backups retain completion when browser autosave is unavailable.
  const quota = await launch(h1,{quota:true});
  await fill(quota,1); quota.$("finalize").click();
  assert(!quota.$("storage-warning").hidden && !quota.$("agreement").hidden);
  assert((await quota.download()).response.finalized_at);
  const silent = await launch(h1,{silent:true});
  silent.$("all-tied").click();
  assert(!silent.$("storage-warning").hidden && silent.$("next").disabled && silent.$("agreement").hidden);

  const organizer = await launch(inputs.organizer);
  assert(organizer.$("overview").hidden && organizer.$("download-combined").disabled);
  await organizer.upload(initial,"returns");
  assert(!organizer.$("error").hidden && organizer.$("overview").hidden);
  const cachedTamper = clone(returns.annotator_1); cachedTamper.agreement = {invented:999};
  await organizer.upload([cachedTamper,returns.annotator_2],"returns");
  assert(organizer.$("error").hidden,organizer.$("error").textContent);
  assert(!organizer.$("overview").hidden && !organizer.$("download-combined").disabled);
  assert.strictEqual(organizer.w.document.querySelectorAll(".organizer-case").length,ui1.packet.question_count);
  const combined = await organizer.download("download-combined");
  assert.strictEqual(combined.question_count,ui1.packet.question_count);
  const hh = combined.agreement.annotator_1_vs_annotator_2;
  assert.strictEqual(hh.compared_questions,ui1.packet.question_count-1);
  assert.strictEqual(hh.excluded_questions,1);
  assert.strictEqual(hh.focus_preference_reversal_rate,1/(ui1.packet.question_count-1));
  assert.strictEqual(combined.agreement.annotator_1_vs_llm.compared_questions,ui1.packet.question_count-1);
  assert.strictEqual(combined.agreement.annotator_2_vs_llm.compared_questions,ui1.packet.question_count);
  assert(combined.cases.every(c=>Object.keys(c.answers).length===4 && c.question && c.gold));
  assert(organizer.$("summaries").textContent.includes("Annotator 1 ↔ Annotator 2"));
  assert.strictEqual(organizer.w.PWNED,undefined);
  organizer.change("case-filter","different");
  assert(organizer.w.document.querySelectorAll(".organizer-case").length > 0);
  for (const ui of [ui1,ui2,restored,recovered,imported,wrong,quota,silent,organizer]) assert.deepStrictEqual(ui.errors,[]);
  windows.forEach(w=>w.close());
  console.log(JSON.stringify({status:"passed",checks:["no premature feedback","all 100 statuses retained","cancel submission","final submission freezes original ratings","self-contained FINAL download","read-only after feedback","no reopening with a draft backup","resume final state","recover frozen snapshot","import final return","cross-person rejection","changed-answer rejection","quota fallback","silent write failure","no executable evidence","organizer requires final returns","two-person answer-identity join","human-human preference reversal","abstention denominators","cached summaries recomputed","all questions and answers visible"],returns,combined}));
})().catch(e=>{console.error(e);windows.forEach(w=>w.close());process.exitCode=1;});
