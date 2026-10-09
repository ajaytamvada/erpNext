const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
let route = [];
const context = { window: { frappe: { get_route: () => route }, location: { pathname: "/app/home" } } };
vm.createContext(context);
vm.runInContext(fs.readFileSync("pridict_app/pridict/public/js/ui/route_context.js", "utf8"), context);
const examples = [
	[["Workspaces", "Website"], "website", "workspace", "website"],
	[["workspaces", "Website"], "website", "workspace", "website"],
	[["List", "Workflow State", "List"], "administration", "list", "List/Workflow State/List"],
	[["list", "Workflow State", "List"], "administration", "list", "list/Workflow State/List"],
	[["List", "Sales Invoice", "List"], "sales", "list", "List/Sales Invoice/List"],
	[["Form", "Purchase Order", "PUR-ORD-2026-00001"], "procurement", "form", "Form/Purchase Order/PUR-ORD-2026-00001"],
	[["query-report", "General Ledger"], "finance", "report", "query-report/General Ledger"],
	[["process-intelligence"], "process-intelligence", "page", "process-intelligence"],
	[["purchasing-analysis"], "process-intelligence", "page", "purchasing-analysis"],
	[["schema-intelligence"], "governance", "page", "schema-intelligence"],
];
for (const [parts, module, surface, expectedRoute] of examples) {
	route = parts;
	const actual = context.window.pridict.routeContext.classify();
	assert.equal(actual.module, module);
	assert.equal(actual.surface, surface);
	assert.equal(actual.route, expectedRoute);
}
console.log(`PASS: ${examples.length} workspace, list, form, report, and analysis-page route classifications.`);
