/* Read HTML from stdin; exercise offline DOM interactions without a server. */
"use strict";
const assert = require("assert");
const fs = require("fs");
const {JSDOM, VirtualConsole} = require("jsdom");
const html = fs.readFileSync(0, "utf8");
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", error => errors.push(error.message));
const dom = new JSDOM(html, {
  url: "file:///home/prioma/code/ma_contextcompression_minimal/review/full526/index.html",
  runScripts: "dangerously", pretendToBeVisual: true, virtualConsole,
});
const window = dom.window;
const document = window.document;
const $ = id => document.getElementById(id);
const wait = () => new Promise(resolve => setTimeout(resolve, 25));
const change = (id, value, event = "change") => {
  $(id).value = value;
  $(id).dispatchEvent(new window.Event(event, {bubbles: true}));
};
const cards = () => Array.from(document.querySelectorAll(".answer-card"));
const formatRank = value => Number.isInteger(value) ? String(value) : value.toFixed(1);
function checkCard(row, id, comparison) {
  const card = cards().find(c => c.dataset.condition === id);
  assert(card, "Answer card missing: " + id);
  const condition = row.conditions[id];
  assert.strictEqual(card.querySelector(".answer-text").textContent, condition.answer);
  assert.strictEqual(card.querySelector(".context-text").textContent, data.contexts[condition.context] || "(empty)");
  const compressed = data.candidates.includes(id);
  const rank = row.rankings[compressed ? id : comparison];
  const role = compressed ? "matching_compressed" : id;
  assert.strictEqual(card.querySelector(".rank-badge").textContent, "Rank " + formatRank(rank.midranks[role]));
  for (const metric of Object.keys(condition.scores[0].dimensions)) {
    assert.strictEqual(card.querySelector(`.score-grid [data-metric="${metric}"] .metric-value`).textContent,
      condition.scores[0].dimensions[metric].toFixed(2));
  }
}
const data = JSON.parse($("review-data").textContent);
(async () => {
  await wait();
  assert.strictEqual($("error").hidden, true, $("error").textContent);
  assert($("coverage").textContent.includes(String(data.meta.questions) + " questions"));
  assert.strictEqual(document.querySelectorAll(".question-link").length, data.rows.length);
  assert.strictEqual(cards().length, 4);
  const first = data.rows[0];
  const firstCandidate = data.candidates[0];
  ["raw", firstCandidate, "oracle_bgb_paragraph_ids", "no_context"].forEach(id => checkCard(first, id, firstCandidate));
  assert.strictEqual(document.querySelectorAll(".comparison-table tbody tr").length, 15);
  assert.strictEqual(document.querySelector(".reference .text").textContent, first.gold);

  change("method", "dac_native_tokens");
  change("ratio", "r2p0");
  const dac = "dac_native_tokens-r2p0";
  ["raw", dac, "oracle_bgb_paragraph_ids", "no_context"].forEach(id => checkCard(first, id, dac));
  change("view", "all");
  assert.strictEqual(cards().length, 18);
  Object.keys(first.conditions).forEach(id => checkCard(first, id, dac));
  assert(!Array.from(document.querySelectorAll(".answer-card h3")).some(h => /_v2| V2/i.test(h.textContent)));

  const comparison = "german_legal_selector_v2-r1p1";
  document.querySelector(`[data-comparison="${comparison}"]`).click();
  assert.strictEqual($("view").value, "four");
  assert.strictEqual(cards().length, 4);
  checkCard(first, comparison, comparison);
  change("relation", "worse");
  const expectedWorse = data.rows.filter(row => {
    const r = row.rankings[comparison].midranks;
    return r.matching_compressed > r.raw;
  }).length;
  assert.strictEqual(document.querySelectorAll(".question-link").length, expectedWorse);
  change("relation", "any");

  const last = data.rows[data.rows.length - 1];
  change("search", last.id, "input");
  assert.strictEqual(document.querySelectorAll(".question-link").length, 1);
  assert(document.querySelector(".row-id").textContent.includes(last.id));
  checkCard(last, comparison, comparison);
  change("search", "A_NO_MATCH_SENTINEL_90c0eacb", "input");
  assert.strictEqual(cards().length, 0);
  assert.strictEqual($("previous").disabled, true);
  assert.strictEqual($("next").disabled, true);
  assert($("detail").textContent.includes("No questions match"));
  change("search", "", "input");

  const repeatRow = data.rows.find(row => Object.values(row.rankings).some(r => r.retest));
  const repeatCandidate = data.candidates.find(id => repeatRow.rankings[id].retest);
  window.location.hash = new window.URLSearchParams({row:repeatRow.id, comparison:repeatCandidate, view:"four"}).toString();
  await wait();
  assert(document.querySelector(".row-id").textContent.includes(repeatRow.id));
  assert(document.querySelector(".ranking-repeat"));
  checkCard(repeatRow, repeatCandidate, repeatCandidate);

  const scoreRow = data.rows.find(row => row.conditions.raw.scores.length === 2);
  window.location.hash = new window.URLSearchParams({row:scoreRow.id, comparison:firstCandidate, view:"four"}).toString();
  await wait();
  assert(document.querySelector('[data-condition="raw"] .score-repeat'));
  checkCard(scoreRow, "raw", firstCandidate);
  $("expand").click();
  assert(document.querySelector(".cards").classList.contains("expanded"));
  const position = data.rows.findIndex(row => row.id === scoreRow.id);
  if (position + 1 < data.rows.length) {
    $("next").click();
    assert(document.querySelector(".row-id").textContent.includes(data.rows[position + 1].id));
    document.body.dispatchEvent(new window.KeyboardEvent("keydown", {key:"ArrowLeft", bubbles:true}));
    assert(document.querySelector(".row-id").textContent.includes(scoreRow.id));
  }
  assert.strictEqual(window.PWNED, undefined, "Evidence text executed as script");
  assert.deepStrictEqual(errors, []);
  console.log(JSON.stringify({status:"passed", questions:data.meta.questions, checks:[
    "initial four-way view", "exact answer and context text", "primary scores", "midranks and ties",
    "method and target switching", "all 18 answers", "all 15 comparisons", "unversioned labels",
    "ranking filter", "search", "empty state", "deep links", "separate score and rank repeats",
    "expanded text", "previous/next and keyboard navigation", "no runtime errors"
  ]}));
  window.close();
})().catch(error => { console.error(error); window.close(); process.exitCode = 1; });
