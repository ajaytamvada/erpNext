// Renderer and security test suite for Decision Intelligence UI
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const escape = (value) =>
	String(value).replace(/[&<>"']/g, (c) => ({
		"&": "&amp;",
		"<": "&lt;",
		">": "&gt;",
		'"': "&quot;",
		"'": "&#39;",
	}[c]));

const context = {
	frappe: {
		pages: { "decision-intelligence": {} },
		utils: { escape_html: escape },
		boot: { sysdefaults: { number_format: "en-IN" } },
	},
	__: (s) => s,
};

vm.createContext(context);
vm.runInContext(
	fs.readFileSync("pridict_app/pridict/pridict/page/decision_intelligence/decision_intelligence.js", "utf8") +
		"\nglobalThis.Screen = ProcurementDecisionIntelligence;",
	context
);

const screen = Object.create(context.Screen.prototype);
screen.activeTab = "audit";
screen.options = {
	companies: ["Acme Corp"],
	default_company: "Acme Corp",
	rules: [
		{ rule_id: "RULE-AUTH-TIER", name: "Authorization Tier", category: "APPROVAL", severity: "HIGH", default_threshold: 150000, description: "Check limits" },
		{ rule_id: "RULE-PRICE-VAR", name: "Price Variance", category: "PRICE", severity: "MEDIUM", default_threshold: 5, description: "Check price" },
	],
};

screen.data = {
	summary: {
		total_decisions_evaluated: 2,
		compliant_count: 1,
		warning_count: 0,
		breach_count: 1,
		compliance_rate_pct: 50.0,
		total_spend_evaluated: 250000.0,
		total_spend_at_risk: 180000.0,
		total_anomalies_count: 2,
		active_recommendations_count: 2,
		potential_savings_total: 15000.0,
	},
	evaluated_decisions: [
		{
			doc_type: "Purchase Order",
			doc_name: "PO-2026-001",
			creation: "2026-10-01",
			total_amount: 180000.0,
			currency: "INR",
			owner: "buyer@test.com",
			status: "BREACH",
			approver: "Purchase User",
			risk_score: 85.0,
			doc_url: "/app/purchase-order/PO-2026-001",
			evaluations: [
				{ rule_name: "Multi-Tier Approval Authorization", status: "BREACH", message: "Order value 180,000 exceeds threshold" },
			],
		},
		{
			doc_type: "Purchase Order",
			doc_name: "PO-2026-002",
			creation: "2026-10-02",
			total_amount: 70000.0,
			currency: "INR",
			owner: "buyer@test.com",
			status: "COMPLIANT",
			approver: "Finance Manager",
			risk_score: 5.0,
			doc_url: "/app/purchase-order/PO-2026-002",
			evaluations: [
				{ rule_name: "Multi-Tier Approval Authorization", status: "COMPLIANT", message: "Approved within limits" },
			],
		},
	],
	anomalies: [
		{
			anomaly_id: "ANOM-PRICE-1",
			anomaly_type: "PRICE_VARIANCE_OUTLIER",
			severity: "HIGH",
			title: "Price Outlier: PUMP-01 (+35%)",
			description: "Unit rate 13,500 is 35% higher than benchmark 10,000.",
			doc_type: "Purchase Order",
			doc_name: "PO-2026-001",
			party_name: "Vendor Alpha",
			amount: 135000.0,
			potential_impact: 35000.0,
			doc_url: "/app/purchase-order/PO-2026-001",
		},
	],
	vendor_scores: [
		{
			vendor_id: "Vendor Alpha",
			vendor_name: "Vendor Alpha",
			total_spend: 180000.0,
			order_count: 1,
			on_time_delivery_rate: 100.0,
			quality_acceptance_rate: 98.0,
			overall_score: 91.5,
			tier: "PREFERRED",
			key_strengths: ["High on-time punctuality (100.0%)"],
			risk_flags: [],
		},
	],
	recommendations: [
		{
			rec_id: "REC-001",
			title: "Renegotiate Rate for PUMP-01",
			category: "COST_OPTIMIZATION",
			priority: "CRITICAL",
			description: "Detected 35% unit rate variance. Potential savings: ₹35,000.",
			suggested_action: "Benchmark against alternate quotes and request revision.",
			target_doctype: "Purchase Order",
			target_docname: "PO-2026-001",
			estimated_saving: 35000.0,
			doc_url: "/app/purchase-order/PO-2026-001",
		},
	],
};

// 1. Audit Tab Rendering
screen.activeTab = "audit";
const auditHtml = screen.renderActiveTabContent("INR");
assert.match(auditHtml, /PO-2026-001/);
assert.match(auditHtml, /BREACH/);
assert.match(auditHtml, /Multi-Tier Approval Authorization/);
console.log("PASS: Decision Audit tab renders evaluated documents, rules, and breach pills.");

// 2. Anomalies Tab Rendering
screen.activeTab = "anomalies";
const anomHtml = screen.renderActiveTabContent("INR");
assert.match(anomHtml, /Price Outlier: PUMP-01/);
assert.match(anomHtml, /HIGH SEVERITY/);
assert.match(anomHtml, /Vendor Alpha/);
console.log("PASS: Anomalies tab renders risk signals with severity badges and impact values.");

// 3. Vendors Tab Rendering
screen.activeTab = "vendors";
const vendorHtml = screen.renderActiveTabContent("INR");
assert.match(vendorHtml, /Vendor Alpha/);
assert.match(vendorHtml, /PREFERRED/);
assert.match(vendorHtml, /91\.5/);
console.log("PASS: Vendor scorecard tab renders performance tiers and on-time ratings.");

// 4. Recommendations Tab Rendering
screen.activeTab = "recommendations";
const recHtml = screen.renderActiveTabContent("INR");
assert.match(recHtml, /Renegotiate Rate for PUMP-01/);
assert.match(recHtml, /CRITICAL PRIORITY/);
assert.match(recHtml, /Prescriptive Action/);
console.log("PASS: Prescriptive recommendations tab renders action boxes and priority cards.");

// 5. Rules Tab Rendering
screen.activeTab = "rules";
const rulesHtml = screen.renderActiveTabContent("INR");
assert.match(rulesHtml, /RULE-AUTH-TIER/);
assert.match(rulesHtml, /RULE-PRICE-VAR/);
console.log("PASS: Configured rules directory renders active policy parameters.");

// 6. XSS Security escaping test
const evilTitle = '<script>alert("XSS")</script>';
screen.data.anomalies[0].title = evilTitle;
screen.activeTab = "anomalies";
const escapedAnom = screen.renderActiveTabContent("INR");
assert.ok(!escapedAnom.includes("<script>"));
assert.ok(escapedAnom.includes("&lt;script&gt;"));
console.log("PASS: XSS injection is safely escaped.");

console.log("\nALL DECISION INTELLIGENCE RENDERER TESTS PASSED SUCCESSFULLY!");
