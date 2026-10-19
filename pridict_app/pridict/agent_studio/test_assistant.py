"""Procurement Assistant: conversation messages and creating missing items and suppliers."""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from erpnext.stock.doctype.item.test_item import make_item
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from pridict.agent_studio import assistant, registry, runtime, tools
from pridict.agent_studio.evals import ScriptedLLM
from pridict.agent_studio.setup import ensure_agent_studio_setup

WAREHOUSE = "_Test Warehouse - _TC"
AGENT = registry.PROCUREMENT_AGENT
NEW_ITEM = "Assistant Quantum Gizmo"
NEW_SUPPLIER = "_Test Assistant New Supplier"
KNOWN_SUPPLIER = "_Test Assistant Known Supplier"
CHAIR = "_Test Assistant Chair"


def requirement(item_query: str, qty: float = 2) -> dict:
	return {
		"item_query": item_query,
		"qty": qty,
		"uom": "",
		"warehouse": WAREHOUSE,
		"need_by": add_days(nowdate(), 10),
		"company": "",
	}


def item_proposal(name: str = NEW_ITEM) -> dict:
	return {
		"item_name": name,
		"item_group": "_Test Item Group",
		"stock_uom": "Nos",
		"is_stock_item": True,
		"description": "",
	}


class TestProcurementAssistant(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_agent_studio_setup()
		if not frappe.db.exists("LLM Provider", "_Test Assistant Provider"):
			frappe.get_doc(
				{
					"doctype": "LLM Provider",
					"provider_name": "_Test Assistant Provider",
					"provider_type": "OpenAI-compatible",
					"endpoint": "http://llm.local/v1",
				}
			).insert()
		if not frappe.db.exists("LLM Model Config", "_assistant-test"):
			frappe.get_doc(
				{
					"doctype": "LLM Model Config",
					"config_name": "_assistant-test",
					"provider": "_Test Assistant Provider",
					"model_id": "mock",
					"status": "Active",
				}
			).insert()
		frappe.db.set_value("Agent Definition", AGENT, {"model_config": "_assistant-test", "max_steps": 16})
		if not frappe.db.exists("Supplier", KNOWN_SUPPLIER):
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": KNOWN_SUPPLIER,
					"supplier_group": "_Test Supplier Group",
				}
			).insert()
		make_item(CHAIR, {"item_name": "Assistant Office Chair", "is_stock_item": 1})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.clear_document_cache("Agent Definition", AGENT)

	def run_agent(self, llm, run=None, request="Please source this", answer=None):
		with patch("pridict.agent_studio.gateway.chat", llm):
			if run is None:
				run = runtime.start_run(AGENT, request)["run"]
				runtime.execute(run)
			else:
				runtime.answer_run(run, answer)
				runtime.execute(run, {"answer": answer, "by": frappe.session.user})
		return frappe.get_doc("Agent Run", run)

	def messages(self, run: str) -> list[dict]:
		return assistant.get_conversation(run)["messages"]

	def test_creates_missing_item_and_supplier_then_waits_for_approval(self):
		llm = ScriptedLLM(
			[requirement(NEW_ITEM)],
			{
				"item_proposal": [item_proposal()],
				"supplier_answer": [
					{"action": "use", "suppliers": [{"name": NEW_SUPPLIER, "email": "sales@assistant.test"}]}
				],
			},
		)
		run = self.run_agent(llm, request=f"I need 2 {NEW_ITEM} by next week for Stores")
		self.assertEqual(run.status, "Waiting for buyer", run.error)
		question = self.messages(run.name)[-1]
		self.assertEqual(question["kind"], "question")
		self.assertIn(NEW_ITEM, question["content"])
		self.assertEqual(question["card"]["title"], "New item")
		self.assertIn("Yes, create it", question["choices"])
		self.assertFalse(frappe.db.exists("Item", {"item_name": NEW_ITEM}))

		# Clicking the quick reply creates the item without another LLM call.
		run = self.run_agent(llm, run=run.name, answer="Yes, create it")
		self.assertEqual(run.status, "Waiting for buyer", run.error)
		item = frappe.db.get_value(
			"Item", {"item_name": NEW_ITEM}, ["name", "item_group", "stock_uom"], as_dict=True
		)
		self.assertEqual((item.item_group, item.stock_uom), ("_Test Item Group", "Nos"))
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "Item",
					"reference_name": item.name,
					"content": ["like", f"%{run.name}%"],
				},
			)
		)
		self.assertNotIn("item_answer", llm.calls)
		self.assertIn("supplier", run.pending_question.lower())

		run = self.run_agent(llm, run=run.name, answer=f"{NEW_SUPPLIER}, sales@assistant.test")
		self.assertEqual(run.status, "Waiting for buyer", run.error)
		confirm = self.messages(run.name)[-1]
		self.assertEqual(confirm["choices"][0], "Yes, go ahead")
		self.assertIn("New supplier", json.dumps(confirm["card"]))
		self.assertFalse(frappe.db.exists("Supplier", NEW_SUPPLIER))

		run = self.run_agent(llm, run=run.name, answer="Yes, go ahead")
		self.assertEqual(run.status, "Awaiting approval", run.error)
		self.assertTrue(frappe.db.exists("Supplier", NEW_SUPPLIER))
		self.assertTrue(frappe.db.exists("Item Supplier", {"parent": item.name, "supplier": NEW_SUPPLIER}))
		contact = frappe.db.get_value("Supplier", NEW_SUPPLIER, "supplier_primary_contact")
		self.assertEqual(frappe.db.get_value("Contact", contact, "email_id"), "sales@assistant.test")

		approval = frappe.get_doc("Agent Approval", {"run": run.name})
		self.assertEqual(json.loads(approval.proposal_json)["rfq_suppliers"], [NEW_SUPPLIER])
		kinds = [(m["role"], m["kind"]) for m in self.messages(run.name)]
		self.assertEqual(kinds[0], ("user", "text"))
		self.assertIn(("assistant", "notice"), kinds)
		self.assertEqual(kinds[-1], ("assistant", "approval"))
		last = self.messages(run.name)[-1]
		self.assertEqual(last["choices"], [])
		self.assertIn("approval", last["content"])

	def test_existing_supplier_is_linked_without_extra_confirmation(self):
		llm = ScriptedLLM(
			[requirement(CHAIR)],
			{"supplier_answer": [{"action": "use", "suppliers": [{"name": KNOWN_SUPPLIER, "email": ""}]}]},
		)
		run = self.run_agent(llm)
		self.assertEqual(run.status, "Waiting for buyer", run.error)
		run = self.run_agent(llm, run=run.name, answer=f"Use {KNOWN_SUPPLIER}")
		self.assertEqual(run.status, "Awaiting approval", run.error)
		self.assertTrue(frappe.db.exists("Item Supplier", {"parent": CHAIR, "supplier": KNOWN_SUPPLIER}))

	def test_buyer_can_stop_instead_of_creating_the_item(self):
		llm = ScriptedLLM([requirement("Assistant Imaginary Thing")])
		run = self.run_agent(llm)
		run = self.run_agent(llm, run=run.name, answer="Cancel request")
		self.assertEqual(run.status, "Cancelled", run.error)
		self.assertFalse(frappe.db.exists("Item", {"item_name": "Scripted Item"}))
		last = self.messages(run.name)[-1]
		self.assertEqual(last["kind"], "result")
		self.assertIn("stopped", last["content"])

	def test_buyer_can_change_the_proposed_item(self):
		changed = {**item_proposal("Assistant Gizmo Pro"), "action": "unclear", "existing_item": ""}
		created = {**changed, "action": "create"}
		llm = ScriptedLLM(
			[requirement("Assistant Gizmo Pro")],
			{"item_proposal": [item_proposal("Assistant Gizmo")], "item_answer": [changed, created]},
		)
		run = self.run_agent(llm)
		run = self.run_agent(llm, run=run.name, answer="Call it Assistant Gizmo Pro")
		self.assertEqual(run.status, "Waiting for buyer", run.error)
		card = self.messages(run.name)[-1]["card"]
		self.assertIn("Assistant Gizmo Pro", json.dumps(card))
		run = self.run_agent(llm, run=run.name, answer="ok now create it")
		self.assertTrue(frappe.db.exists("Item", {"item_name": "Assistant Gizmo Pro"}))

	def test_without_policy_the_agent_asks_for_an_item_code(self):
		policy = frappe.db.get_value("Agent Policy", {"rule_key": "create_missing_master_data"})
		frappe.db.set_value("Agent Policy", policy, "enabled", 0)
		self.addCleanup(frappe.db.set_value, "Agent Policy", policy, "enabled", 1)
		run = self.run_agent(ScriptedLLM([requirement("Assistant Nonexistent Part")]))
		self.assertEqual(run.status, "Waiting for buyer", run.error)
		self.assertIn("item code", run.pending_question)

	def test_master_data_tools_need_a_confirmation(self):
		outcome = tools.run_tool("create_supplier", {"supplier_name": "_Test Unconfirmed Supplier"})
		self.assertFalse(outcome["ok"])
		self.assertIn("confirmation", outcome["error"])
		self.assertFalse(frappe.db.exists("Supplier", "_Test Unconfirmed Supplier"))

	def test_send_message_starts_then_answers_a_conversation(self):
		llm = ScriptedLLM([{**requirement(CHAIR), "warehouse": "", "company": "_Test Company"}])
		with patch("pridict.agent_studio.gateway.chat", llm):
			run = assistant.send_message("I need 2 office chairs")["conversation"]
			runtime.execute(run)
			detail = assistant.get_conversation(run)
			self.assertTrue(detail["can_reply"])
			self.assertTrue(detail["messages"][-1]["choices"])
			self.assertEqual(assistant.send_message(WAREHOUSE, run)["conversation"], run)
			self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Queued")
		self.assertEqual(
			[m["role"] for m in assistant.get_conversation(run)["messages"]], ["user", "assistant", "user"]
		)
		self.assertIn(run, [c.name for c in assistant.get_conversations()])

	def test_other_users_cannot_read_a_conversation(self):
		run = self.run_agent(ScriptedLLM([requirement(CHAIR, qty=0)]))
		frappe.set_user("test1@example.com")
		with self.assertRaises(frappe.PermissionError):
			assistant.get_conversation(run.name)

	def test_existing_item_with_the_proposed_name_is_offered_first(self):
		make_item("_Test Assistant Widget", {"item_name": "Assistant Duplicate Widget", "is_stock_item": 1})
		llm = ScriptedLLM(
			[requirement("Assistant Duplicate Widgets")],
			{"item_proposal": [item_proposal("Assistant Duplicate Widget")]},
		)
		run = self.run_agent(llm)
		question = self.messages(run.name)[-1]
		self.assertIn("already have an item called", question["content"])
		self.assertEqual(question["choices"][:2], ["_Test Assistant Widget", "Create a separate new item"])
		run = self.run_agent(llm, run=run.name, answer="_Test Assistant Widget")
		self.assertEqual(run.status, "Waiting for buyer", run.error)
		self.assertIn("supplier", run.pending_question.lower())
		self.assertEqual(frappe.db.count("Item", {"item_name": "Assistant Duplicate Widget"}), 1)
