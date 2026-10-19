"""Approval decisions end to end: decide -> resume -> revalidate -> draft RFQ -> verify."""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from erpnext.buying.doctype.purchase_order.test_purchase_order import create_purchase_order
from erpnext.stock.doctype.item.test_item import make_item
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
from frappe.tests.utils import FrappeTestCase

from pridict.agent_studio import approvals, registry, runtime, tools
from pridict.agent_studio.setup import ensure_agent_studio_setup
from pridict.agent_studio.test_runtime import ScriptedLLM, requirement

ITEM = "_Test Agent Runtime Sheet"
WAREHOUSE = "_Test Warehouse - _TC"
AGENT = registry.PROCUREMENT_AGENT
BUYER = "agent-buyer@example.com"
PM = "agent-pm@example.com"
AM = "agent-am@example.com"


def make_user(email, roles):
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
		)
		user.insert()
		user.add_roles(*roles)


class TestAgentApprovals(FrappeTestCase):
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
		frappe.db.set_value(
			"Agent Definition", AGENT, {"model_config": "_runtime-test", "max_steps": 8, "status": "Active"}
		)
		item = make_item(
			ITEM, {"item_name": "Agent Runtime Sheet 2mm", "is_stock_item": 1, "lead_time_days": 10}
		)
		item.set("supplier_items", [{"supplier": "_Test Supplier"}, {"supplier": "_Test Supplier 1"}])
		item.save()
		make_stock_entry(item_code=ITEM, target=WAREHOUSE, qty=100, basic_rate=240)
		create_purchase_order(
			item_code=ITEM, warehouse=WAREHOUSE, qty=150, rate=250, supplier="_Test Supplier"
		)
		make_user(BUYER, ["Purchase User", "Stock User"])
		make_user(PM, ["Purchase Manager"])
		make_user(AM, ["Accounts Manager"])

	def setUp(self):
		self.llm = ScriptedLLM([requirement()])
		# Run background jobs inline so each decision resumes the real graph immediately.
		for target, value in (
			("pridict.agent_studio.runtime._enqueue", lambda run, resume=None: runtime.execute(run, resume)),
			("pridict.agent_studio.gateway.chat", self.llm),
		):
			patcher = patch(target, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.clear_document_cache("Agent Definition", AGENT)

	def start(self, qty=500):
		self.llm.requirements = [requirement(qty=qty)]
		frappe.set_user(BUYER)
		run = runtime.start_run(AGENT, "Source the sheet")["run"]
		frappe.set_user("Administrator")
		self.assertEqual(
			frappe.db.get_value("Agent Run", run, "status"),
			"Awaiting approval",
			frappe.db.get_value("Agent Run", run, "error"),
		)
		return run, frappe.db.get_value("Agent Approval", {"run": run, "status": "Pending"})

	def decide(self, user, approval, decision, note=""):
		frappe.set_user(user)
		try:
			return approvals.decide(approval, decision, note)
		finally:
			frappe.set_user("Administrator")

	def test_approval_creates_verified_draft_rfq(self):
		run, approval = self.start()
		self.assertEqual(self.decide(PM, approval, "approve")["status"], "Approved")

		run_doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(run_doc.status, "Completed", run_doc.error)
		rfq_name = frappe.db.get_value("Agent Approval", approval, "created_docname")
		self.assertIn(rfq_name, run_doc.outcome)
		rfq = frappe.get_doc("Request for Quotation", rfq_name)
		self.assertEqual(rfq.docstatus, 0)
		self.assertEqual(rfq.owner, BUYER)
		self.assertEqual(rfq.items[0].qty, 250)
		self.assertEqual({s.supplier for s in rfq.suppliers}, {"_Test Supplier", "_Test Supplier 1"})
		self.assertEqual(
			[s.node_id for s in run_doc.steps][-3:], ["revalidate", "create_draft", "verify_audit"]
		)
		# The buyer is told in the conversation, with a link to the draft.
		last = run_doc.messages[-1]
		self.assertEqual((last.role, last.kind), ("assistant", "result"))
		self.assertIn(rfq_name, last.content)
		self.assertEqual(
			json.loads(last.card_json)["link"], {"doctype": "Request for Quotation", "name": rfq_name}
		)

	def test_used_or_altered_approval_cannot_create_another_rfq(self):
		run, approval = self.start()
		self.decide(PM, approval, "approve")
		doc = frappe.get_doc("Agent Approval", approval)
		proposal = json.loads(doc.proposal_json)
		arguments = {
			"item_code": ITEM,
			"qty": proposal["shortage_qty"],
			"schedule_date": proposal["need_by"],
			"suppliers": proposal["rfq_suppliers"],
			"approval_id": approval,
		}
		self.assertIn("already used", tools.run_tool("create_draft_rfq", arguments, approval=doc)["error"])
		doc.created_docname = None
		altered = tools.run_tool("create_draft_rfq", {**arguments, "qty": 9999}, approval=doc)
		self.assertIn("quantity", altered["error"])

	def test_buyer_sees_only_own_runs_and_can_start(self):
		from pridict.agent_studio import api

		run, _approval = self.start()
		other = frappe.get_doc(
			{
				"doctype": "Agent Run",
				"agent": AGENT,
				"status": "Completed",
				"requested_by": PM,
				"request": "someone else's",
			}
		)
		other.flags.ignore_permissions = True
		other.insert()
		frappe.set_user(BUYER)
		data = api.get_runs()
		self.assertIn(run, [r.name for r in data["runs"]])
		self.assertEqual({r.requested_by for r in data["runs"]}, {BUYER})  # never another user's run
		self.assertEqual([a.name for a in data["agents"]], [AGENT])
		self.assertIsNone(data["evaluation"])
		self.assertTrue(api.get_run(run)["can_act"])
		with self.assertRaises(frappe.PermissionError):
			api.get_run(other.name)

	def test_requester_cannot_approve_own_run(self):
		_run, approval = self.start()
		# Give the buyer the approving role too, so only the self-approval rule can refuse them.
		frappe.get_doc("User", BUYER).add_roles("Purchase Manager")
		reasons = " ".join(approvals.blockers(frappe.get_doc("Agent Approval", approval), BUYER))
		self.assertIn("started this run", reasons)
		self.assertNotIn("role", reasons)
		with self.assertRaises(frappe.PermissionError):
			self.decide(BUYER, approval, "approve")

	def test_user_without_approving_role_is_refused(self):
		_run, approval = self.start()
		with self.assertRaises(frappe.PermissionError):
			self.decide(AM, approval, "approve")  # single approval needs a Purchase Manager

	def test_rejection_needs_a_reason_and_ends_run(self):
		run, approval = self.start()
		with self.assertRaises(frappe.ValidationError):
			self.decide(PM, approval, "reject")
		self.decide(PM, approval, "reject", "Supplier list too short")
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Rejected")
		last = frappe.get_doc("Agent Run", run).messages[-1]
		self.assertIn("decided not to go ahead", last.content)
		self.assertIn("Supplier list too short", last.content)
		self.assertFalse(frappe.db.get_value("Agent Approval", approval, "created_docname"))

	def test_dual_approval_needs_both_roles(self):
		# 4250 needed - 250 covered = 4000 short x 250 = 10,00,000: between the single and hard limits.
		run, approval = self.start(qty=4250)
		self.assertEqual(
			json.loads(frappe.db.get_value("Agent Approval", approval, "required_roles")),
			["Purchase Manager", "Accounts Manager"],
		)
		first = self.decide(PM, approval, "approve")
		self.assertEqual(first, {"status": "Pending", "remaining": ["Accounts Manager"]})
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Awaiting approval")
		notice = frappe.get_doc("Agent Run", run).messages[-1]
		self.assertEqual(notice.kind, "notice")
		self.assertIn("Still waiting for: Accounts Manager", notice.content)
		with self.assertRaises(frappe.PermissionError):
			self.decide(PM, approval, "approve")  # same person twice
		self.assertEqual(self.decide(AM, approval, "approve")["status"], "Approved")
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Completed")

	def test_stock_change_while_waiting_sends_proposal_back_for_review(self):
		run, approval = self.start()
		make_stock_entry(item_code=ITEM, target=WAREHOUSE, qty=50, basic_rate=240)
		self.decide(PM, approval, "approve")
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Awaiting approval")
		new = frappe.get_all("Agent Approval", filters={"run": run, "status": "Pending"}, pluck="name")
		self.assertEqual(len(new), 1)
		self.assertNotEqual(new[0], approval)
		self.assertEqual(
			json.loads(frappe.db.get_value("Agent Approval", new[0], "proposal_json"))["shortage_qty"], 200
		)
		self.assertFalse(frappe.db.get_value("Agent Approval", approval, "created_docname"))
