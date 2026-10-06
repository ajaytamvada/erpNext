// Renderer/security checks using actual isolated-site API evidence. No browser is controlled.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const escape = (value) => String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const context = { frappe: { pages: { "process-intelligence": {} }, utils: { escape_html: escape } }, __: (s) => s };
vm.createContext(context);
vm.runInContext(fs.readFileSync("pridict_app/pridict/pridict/page/process_intelligence/process_intelligence.js", "utf8") + "\nglobalThis.Screen = PurchasingProcessIntelligence;", context);
const screen = Object.create(context.Screen.prototype);
screen.data = JSON.parse(fs.readFileSync("documentation/process-intelligence/evidence/analysis.json", "utf8"));
assert.equal(screen.connections().reduce((sum, edge) => sum + edge.count, 0), 10);
assert.equal((screen.graph().match(/class="pi-node-count"/g) || []).length, 7);
assert.match(screen.graphTable(), /payment allocation/);
for (const [id, document] of Object.entries(screen.data.documents)) {
	assert.match(screen.documentLink(id), new RegExp(document.name));
	assert.ok(screen.documentLink(id).includes(document.url));
}
assert.match(screen.documentLink("outside-scope"), /Outside visible scope/);
assert.doesNotMatch(screen.documentLink("outside-scope"), /href=/);
const evil = '<img src=x onerror="alert(1)">';
screen.data.documents["malicious"] = { name: evil, url: '/app/purchase-order/a" onclick="bad' };
const escaped = screen.documentLink("malicious");
assert.ok(!escaped.includes("<img"));
assert.ok(escaped.includes("&lt;img"));
assert.ok(!escaped.includes(' onclick="bad'));
assert.match(screen.history([]), /times remain unknown/);
assert.ok(!screen.history(screen.data.reconstruction.events).includes("CURRENT_DOCUMENT_STATE_OBSERVED"));
console.log("PASS: actual graph counts, seven supporting links, boundary links, HTML escaping, and missing-history semantics.");

const firstJourney = screen.data.reconstruction.instances[0];
screen.data.reconstruction.instances = Array.from({ length: 11 }, (_, index) => ({ ...firstJourney, instance_id: `test-journey-${index}` }));
const rendered = {};
screen.$results = { find: (selector) => ({ html: (value) => { rendered[selector] = value; }, on: () => {} }) };
screen.renderJourney = (journey) => { rendered.selected = journey?.instance_id; };
screen.search = "";
screen.journeyPage = 1;
screen.selected = "test-journey-0";
screen.renderJourneys();
assert.equal(rendered.selected, "test-journey-10");
assert.match(rendered[".pi-journeys"], /11–11 \/ 11/);
screen.journeyPage = 99;
screen.renderJourneys();
assert.equal(screen.journeyPage, 1);
screen.search = "no-matching-journeys";
screen.renderJourneys();
assert.equal(screen.journeyPage, 0);
assert.equal(rendered.selected, undefined);
assert.match(rendered[".pi-journeys"], /No matching journeys/);
console.log("PASS: pagination selects a visible journey, clamps invalid pages, and clears filtered details.");
