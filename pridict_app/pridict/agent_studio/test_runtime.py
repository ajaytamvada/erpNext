"""End-to-end runtime tests: the real graph, tools and checkpointer, with the LLM mocked."""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from erpnext.buying.doctype.purchase_order.test_purchase_order import create_purchase_order
from erpnext.stock.doctype.item.test_item import make_item
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from pridict.agent_studio import gateway, registry, runtime
from pridict.agent_studio.setup import ensure_agent_studio_setup

ITEM = "_Test Agent Runtime Sheet"
WAREHOUSE = "_Test Warehouse - _TC"
AGENT = registry.PROCUREMENT_AGENT


class ScriptedLLM:
	"""Stands in for gateway.chat; answers by response schema title."""

	def __init__(self, requirements: list[dict]):
		self.requirements = list(requirements)
		self.calls: list[str] = []

	def __call__(self, config, messages, *, response_schema=None, max_tokens=None, **_):
		title = (response_schema or {}).get("title", "text")
		self.calls.append(title)
		if title == "requirement":
			payload = self.requirements.pop(0) if len(self.requirements) > 1 else self.requirements[0]
		elif title == "sourcing_analysis":
			names = response_schema["properties"]["recommended_supplier"]["enum"]
			payload = {
				"recommended_supplier": names[0],
				"supplier_notes": [{"supplier": n, "note": "ok"} for n in names],
				"rationale": "Best balance.",
			}
		elif title == "recommendation":
			# Deliberately wrong numbers and supplier: the node must overwrite them.
			payload = {
				"shortage_qty": 1,
				"recommended_action": "ask_buyer",
				"suppliers": [],
				"recommended_supplier": "Invented Supplier",
				"estimated_value": 1,
				"explanation": "Send the RFQ.",
			}
		else:
			payload = None
		return gateway.LLMResponse(
			content=json.dumps(payload) if payload is not None else "Stock already covers the need.",
			tool_calls=[],
			finish_reason="stop",
			usage=gateway.Usage(100, 20, 120),
			model_config=config,
			model="mock",
			latency_ms=5,
		)


def requirement(qty=500, warehouse=WAREHOUSE, need_by=None):
	return {
		"item_query": "Agent Runtime Sheet",
		"qty": qty,
		"uom": "",
		"warehouse": warehouse,
		"need_by": need_by or add_days(nowdate(), 10),
		"company": "",
	}


class TestAgentRuntime(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_agent_studio_setup()
		if not frappe.db.exists("LLM Provider", "_Test Runtime Provider"):
			frappe.get_doc(
				{
					"doctype": "LLM Provider",
					"provider_name": "_Test Runtime Provider",
					"provider_type": "OpenAI-compatible",
					"endpoint": "http://llm.local/v1",
				}
			).insert()
		if not frappe.db.exists("LLM Model Config", "_runtime-test"):
			frappe.get_doc(
				{
					"doctype": "LLM Model Config",
					"config_name": "_runtime-test",
					"provider": "_Test Runtime Provider",
					"model_id": "mock",
					"status": "Active",
				}
			).insert()
		frappe.db.set_value("Agent Definition", AGENT, {"model_config": "_runtime-test", "max_steps": 8})
		item = make_item(
			ITEM, {"item_name": "Agent Runtime Sheet 2mm", "is_stock_item": 1, "lead_time_days": 10}
		)
		item.set("supplier_items", [{"supplier": "_Test Supplier"}, {"supplier": "_Test Supplier 1"}])
		item.save()
		make_stock_entry(item_code=ITEM, target=WAREHOUSE, qty=100, basic_rate=240)
		create_purchase_order(
			item_code=ITEM, warehouse=WAREHOUSE, qty=150, rate=250, supplier="_Test Supplier"
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.clear_document_cache("Agent Definition", AGENT)

	def run_agent(self, llm: ScriptedLLM, request="Source the sheet", resume=None, run=None):
		with patch("pridict.agent_studio.gateway.chat", llm):
			if run is None:
				run = runtime.start_run(AGENT, request)["run"]
			runtime.execute(run, resume)
		return frappe.get_doc("Agent Run", run)

	def test_shortage_pauses_for_approval_with_computed_numbers(self):
		llm = ScriptedLLM([requirement()])
		run = self.run_agent(llm)
		self.assertEqual(run.status, "Awaiting approval", run.error)
		self.assertEqual(llm.calls, ["requirement", "sourcing_analysis", "recommendation"])
		self.assertEqual(run.llm_calls, 3)
		self.assertEqual(run.total_tokens, 360)

		approval = frappe.get_doc("Agent Approval", {"run": run.name})
		proposal = json.loads(approval.proposal_json)
		self.assertEqual(proposal["shortage_qty"], 250)  # 500 - 100 in stock - 150 on order
		self.assertEqual(proposal["recommended_supplier"], "_Test Supplier")
		self.assertEqual(approval.estimated_value, 62500)  # 250 x 250 last purchase rate
		self.assertEqual(approval.status, "Pending")
		results = {r["rule"]: r["result"] for r in json.loads(approval.policy_results_json)}
		self.assertEqual(results["Hard ceiling"], "PASS")

		nodes = [s.node_id for s in run.steps]
		self.assertEqual(nodes[0], "parse_requirement")
		self.assertEqual(run.steps[-1].node_id, "human_review")
		self.assertEqual(run.steps[-1].status, "Interrupted")
		self.assertIn(
			"get_open_purchase_orders", next(s.tool_calls for s in run.steps if s.node_id == "read_supply")
		)
		self.assertTrue(frappe.db.exists("Agent Checkpoint", {"thread_id": run.name}))

	def test_rejection_resumes_from_checkpoint_and_ends_run(self):
		llm = ScriptedLLM([requirement()])
		run = self.run_agent(llm)
		approval = frappe.get_doc("Agent Approval", {"run": run.name})
		approval.db_set({"status": "Rejected", "decided_by": "Administrator", "decision_note": "Too early"})
		run = self.run_agent(
			llm, run=run.name, resume={"decision": "rejected", "by": "Administrator", "note": "Too early"}
		)
		self.assertEqual(run.status, "Rejected", run.error)
		self.assertIn("Too early", run.outcome)
		# Only the approval from the first pass exists; resuming did not create another.
		self.assertEqual(frappe.db.count("Agent Approval", {"run": run.name}), 1)
		self.assertEqual(llm.calls.count("recommendation"), 1)

	def test_no_shortage_completes_without_approval(self):
		run = self.run_agent(ScriptedLLM([requirement(qty=50)]))
		self.assertEqual(run.status, "Completed", run.error)
		self.assertIn("No purchase needed", run.outcome)
		self.assertFalse(frappe.db.exists("Agent Approval", {"run": run.name}))

	def test_missing_warehouse_asks_buyer_then_continues(self):
		llm = ScriptedLLM([requirement(warehouse=""), requirement()])
		run = self.run_agent(llm)
		self.assertEqual(run.status, "Waiting for buyer", run.error)
		self.assertIn("warehouse", run.pending_question.lower())
		run = self.run_agent(
			llm, run=run.name, resume={"answer": "Use _Test Warehouse - _TC", "by": "Administrator"}
		)
		self.assertEqual(run.status, "Awaiting approval", run.error)
		self.assertEqual(llm.calls[:2], ["requirement", "requirement"])

	def test_value_above_ceiling_is_blocked_before_recommendation(self):
		llm = ScriptedLLM([requirement(qty=20000)])
		run = self.run_agent(llm)
		self.assertEqual(run.status, "Completed", run.error)
		self.assertIn("Blocked by policy", run.outcome)
		self.assertNotIn("recommendation", llm.calls)
		self.assertFalse(frappe.db.exists("Agent Approval", {"run": run.name}))

	def test_unknown_price_is_not_treated_as_zero(self):
		with patch("pridict.agent_studio.tools._stock_rates", return_value=[]):
			run = self.run_agent(ScriptedLLM([requirement()]))
		approval = frappe.get_doc("Agent Approval", {"run": run.name})
		self.assertEqual(approval.risk, "High")
		self.assertEqual(approval.required_approvals, 2)
		results = {r["rule"]: r["result"] for r in json.loads(approval.policy_results_json)}
		self.assertEqual(results["Value unknown"], "WARN")

	def test_llm_call_limit_stops_the_run(self):
		frappe.db.set_value("Agent Definition", AGENT, "max_steps", 1)
		frappe.clear_document_cache("Agent Definition", AGENT)
		run = self.run_agent(ScriptedLLM([requirement()]))
		self.assertEqual(run.status, "Failed")
		self.assertIn("limit of 1 LLM calls", run.error)
		frappe.db.set_value("Agent Definition", AGENT, "max_steps", 8)

	def test_cancel_expires_approval_and_deletes_checkpoints(self):
		run = self.run_agent(ScriptedLLM([requirement()]))
		runtime.cancel_run(run.name)
		self.assertEqual(frappe.db.get_value("Agent Run", run.name, "status"), "Cancelled")
		self.assertEqual(frappe.db.get_value("Agent Approval", {"run": run.name}, "status"), "Expired")
		self.assertFalse(frappe.db.exists("Agent Checkpoint", {"thread_id": run.name}))

	def test_graph_compiles_for_every_registered_workflow(self):
		for key in runtime.WORKFLOW_MODULES:
			self.assertIsNotNone(runtime.build_graph(key))
