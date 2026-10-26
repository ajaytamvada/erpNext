"""Phase 4: test runs (rolled back, simulated decisions), the activation gate, and waiting steps."""

from __future__ import annotations

import json

import frappe
from frappe.utils import add_to_date, now_datetime

from pridict.agent_studio import approvals
from pridict.automation import api, engine, triggers
from pridict.automation import spec as specs
from pridict.automation.test_helpers import (
	MANAGER,
	AutomationTestCase,
	install_example,
	make_item,
	make_purchase_order,
	make_supplier,
	manual_spec,
	spec_automation,
	step_list,
)


def run_test(automation: str, **trigger) -> str:
	"""Start a test run through the API and execute it (no worker in tests)."""
	run = api.test_run(automation, **trigger)["run"]
	engine.execute(run)
	return run


class TestTestRuns(AutomationTestCase):
	def test_test_run_rolls_back_and_unlocks_activation(self):
		automation = install_example("s3_supplier_onboarding", activate=False)
		supplier = make_supplier("_Test Gate Supplier", "gate@acme.example")
		with self.assertRaises(frappe.ValidationError):
			api.activate(automation)
		self.assertFalse(api.get_builder(automation)["automation"]["tested"])

		run = run_test(automation, docname=supplier)
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(doc.status, "Completed", doc.error)
		self.assertTrue(doc.is_test)
		self.assertEqual(step_list(run), ["has_email", "welcome_email", "assign_check"])
		# The assignment existed during the run and was rolled back afterwards.
		self.assertFalse(frappe.db.exists("ToDo", {"reference_type": "Supplier", "reference_name": supplier}))
		self.assertFalse(frappe.db.exists("Email Queue", {"reference_name": supplier}))
		self.assertTrue(api.get_builder(automation)["automation"]["tested"])

		result = api.activate(automation, "tested")
		version = frappe.get_doc("Automation Version", result["active_version"])
		self.assertEqual(version.test_run, run)

		# Any edit needs a new test before the next activation.
		revision = frappe.db.get_value("Automation", automation, "draft_revision")
		api.apply_ops(automation, revision, [{"op": "update_node", "id": "assign_check", "label": "Check"}])
		self.assertFalse(api.get_builder(automation)["automation"]["tested"])
		with self.assertRaises(frappe.ValidationError):
			api.activate(automation)

	def test_document_triggers_need_a_document(self):
		automation = install_example("s3_supplier_onboarding", activate=False)
		with self.assertRaises(frappe.ValidationError):
			api.test_run(automation)

	def test_failed_test_run_is_rolled_back_too(self):
		spec = manual_spec(
			[
				{
					"id": "note",
					"type": "action.add_comment",
					"config": {
						"doctype": "Supplier",
						"name": "{{ trigger.input.supplier }}",
						"comment": "Hello",
					},
				},
				{
					"id": "halt",
					"type": "logic.stop",
					"config": {"status": "Failed", "message": "Stopped on purpose"},
				},
			],
			[{"from": "trigger", "to": "note"}, {"from": "note", "to": "halt"}],
		)
		automation = spec_automation(spec, activate=False)
		supplier = make_supplier("_Test Rollback Supplier")
		run = run_test(automation, input=json.dumps({"supplier": supplier}))
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(doc.status, "Failed")
		self.assertIn("Stopped on purpose", doc.error)
		self.assertFalse(
			frappe.db.exists(
				"Comment", {"reference_doctype": "Supplier", "reference_name": supplier, "content": "Hello"}
			)
		)


class TestApprovals(AutomationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.automation = install_example("s4_po_approval")
		cls.supplier = make_supplier("_Test Approval Supplier")
		cls.item = make_item("_Test Approval Sheet")

	def big_po(self) -> str:
		# Created while no run is wanted: start runs explicitly below.
		frappe.flags.automation_chain = [self.automation]
		try:
			return make_purchase_order(self.supplier, self.item, rate=600000)
		finally:
			frappe.flags.automation_chain = None

	def start(self, po: str) -> str:
		return engine.start_run(
			self.automation, {"event": "on_update", "doctype": "Purchase Order", "name": po}, now=True
		)

	def decide(self, run: str, decision: str, note: str = ""):
		approval = frappe.db.get_value("Agent Approval", {"run": run, "status": "Pending"}, "name")
		self.assertTrue(approval)
		frappe.set_user(MANAGER)
		try:
			approvals.decide(approval, decision, note)
		finally:
			frappe.set_user("Administrator")

	def test_approved_po_is_submitted(self):
		po = self.big_po()
		run = self.start(po)
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(doc.status, "Awaiting approval")
		pending = json.loads(doc.pending_json)
		self.assertEqual((pending["type"], pending["roles"]), ("approval", ["Purchase Manager"]))
		self.assertTrue(doc.resume_at)
		approval = frappe.get_doc("Agent Approval", pending["approval"])
		self.assertEqual(approval.action, "automation:approve")
		self.assertIn(po, approval.summary)

		self.decide(run, "approve")
		doc.reload()
		self.assertEqual(doc.status, "Completed", doc.error)
		self.assertEqual(frappe.db.get_value("Purchase Order", po, "docstatus"), 1)
		self.assertEqual(step_list(run), ["approve", "approve", "submit"])
		self.assertEqual(doc.steps[0].status, "Interrupted")

	def test_rejected_po_gets_the_reason(self):
		po = self.big_po()
		run = self.start(po)
		self.decide(run, "reject", "Too expensive this quarter")
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Completed")
		self.assertEqual(frappe.db.get_value("Purchase Order", po, "docstatus"), 0)
		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Purchase Order", "reference_name": po, "comment_type": "Comment"},
			pluck="content",
		)
		self.assertTrue(any("Too expensive this quarter" in c and MANAGER in c for c in comments))

	def test_no_decision_in_time_expires(self):
		po = self.big_po()
		run = self.start(po)
		frappe.db.set_value("Agent Run", run, "resume_at", add_to_date(now_datetime(), minutes=-1))
		triggers.resume_due()
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Completed")
		self.assertEqual(frappe.db.get_value("Agent Approval", {"run": run}, "status"), "Expired")
		self.assertIn("expired_note", step_list(run))

	def test_simulated_test_run_drives_each_branch_without_side_effects(self):
		po = self.big_po()
		run = run_test(self.automation, docname=po)
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(doc.status, "Waiting")
		pending = json.loads(doc.pending_json)
		self.assertEqual((pending["node"], pending["simulate"]), ("approve", True))
		self.assertFalse(frappe.db.exists("Agent Approval", {"run": run}))

		api.simulate(run, "approve", "approved")
		doc.reload()
		self.assertEqual(doc.status, "Completed", doc.error)
		self.assertEqual(step_list(run), ["approve", "submit"])
		# The PO was submitted during the test and rolled back afterwards.
		self.assertEqual(frappe.db.get_value("Purchase Order", po, "docstatus"), 0)

		second = run_test(self.automation, docname=po)
		api.simulate(second, "approve", "rejected", "No budget")
		self.assertEqual(step_list(second), ["approve", "rejected_note"])
		self.assertFalse(
			frappe.db.exists("Comment", {"reference_name": po, "content": ["like", "%No budget%"]})
		)


class TestAskAndWait(AutomationTestCase):
	def test_ask_waits_for_the_named_user(self):
		spec = manual_spec(
			[
				{
					"id": "ask",
					"type": "human.ask",
					"config": {
						"users": MANAGER,
						"question": "Which warehouse?",
						"choices": ["Stores", "Main"],
					},
				},
				{
					"id": "keep",
					"type": "logic.set_variable",
					"config": {"name": "warehouse", "value": "{{ nodes.ask.answer }}"},
				},
			],
			[{"from": "trigger", "to": "ask"}, {"from": "ask", "to": "keep"}, {"from": "keep", "to": "END"}],
		)
		automation = spec_automation(spec)
		run = engine.start_run(automation, {"event": "manual"}, now=True)
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Waiting")
		self.assertTrue(
			frappe.db.exists(
				"Notification Log", {"document_type": "Agent Run", "document_name": run, "for_user": MANAGER}
			)
		)

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				api.answer(run, "Main")
		finally:
			frappe.set_user("Administrator")
		with self.assertRaises(frappe.ValidationError):
			api.answer(run, "Garage")
		api.answer(run, "Main")
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(doc.status, "Completed", doc.error)
		self.assertEqual(json.loads(doc.result_json)["vars"], {"warehouse": "Main"})

	def test_wait_resumes_when_due(self):
		spec = manual_spec(
			[{"id": "pause", "type": "logic.wait", "config": {"minutes": 30}}],
			[{"from": "trigger", "to": "pause"}, {"from": "pause", "to": "END"}],
		)
		automation = spec_automation(spec)
		run = engine.start_run(automation, {"event": "manual"}, now=True)
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Waiting")
		triggers.resume_due()
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Waiting")
		frappe.db.set_value("Agent Run", run, "resume_at", add_to_date(now_datetime(), minutes=-1))
		triggers.resume_due()
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Completed")

	def test_waiting_steps_need_checkpoints_and_validate(self):
		spec = manual_spec(
			[{"id": "pause", "type": "logic.wait", "config": {"minutes": 5, "until": "{{ today }}"}}],
			[{"from": "trigger", "to": "pause"}, {"from": "pause", "to": "END"}],
		)
		self.assertTrue(specs.needs_checkpoints(spec))
		self.assertTrue(any("not both" in i["message"] for i in specs.validate(spec)))
