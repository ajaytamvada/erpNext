"""Engine and trigger tests: the S3 example compiled to LangGraph and run against real records."""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.automation import engine, triggers
from pridict.automation.examples import install, load_example

MANAGER = "_test_automation_pm@example.com"


def make_supplier(name: str, email: str | None = None) -> str:
	if frappe.db.exists("Supplier", name):
		frappe.delete_doc("Supplier", name, force=True)
	supplier = frappe.get_doc(
		{"doctype": "Supplier", "supplier_name": name, "supplier_group": "All Supplier Groups"}
	)
	supplier.insert()
	if email:
		# email_id is normally filled from the primary contact; set it directly for the test.
		supplier.db_set("email_id", email)
	return supplier.name


class TestAutomationEngine(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# In tests Frappe sends assignment notification emails at once, and the Email Queue
		# commits its status. Block commits so everything here is rolled back.
		commit = patch.object(frappe.db, "commit")
		commit.start()
		cls.addClassCleanup(commit.stop)
		if not frappe.db.exists("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}):
			# Emails need a default outgoing account to queue (SMTP is not contacted in tests).
			frappe.get_doc(
				{
					"doctype": "Email Account",
					"email_account_name": "_Test Automation Outgoing",
					"email_id": "automation-test@example.com",
					"enable_outgoing": 1,
					"default_outgoing": 1,
					"smtp_server": "smtp.example.com",
					"password": "password",
				}
			).insert()
		if not frappe.db.exists("User", MANAGER):
			user = frappe.get_doc(
				{"doctype": "User", "email": MANAGER, "first_name": "Automation PM", "send_welcome_email": 0}
			).insert()
			user.add_roles("Purchase Manager")
		cls.automation = install(run_as="Administrator")

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		# The trigger index lives in Redis and survives the test rollback.
		triggers.clear_index()

	def steps(self, run):
		return {step.node_id: step for step in frappe.get_doc("Agent Run", run).steps}

	def test_runs_email_branch(self):
		supplier = make_supplier("_Test Automation Supplier A", "accounts@acme.example")
		run = engine.start_run(
			self.automation, {"event": "after_insert", "doctype": "Supplier", "name": supplier}, now=True
		)
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(doc.status, "Completed", doc.error)
		steps = self.steps(run)
		self.assertEqual(list(steps), ["has_email", "welcome_email", "assign_check"])
		self.assertEqual(json.loads(steps["has_email"].output_json)["route"], "true")
		self.assertTrue(
			frappe.db.exists("Email Queue", {"reference_doctype": "Supplier", "reference_name": supplier})
		)
		todo = frappe.get_all(
			"ToDo",
			filters={"reference_type": "Supplier", "reference_name": supplier, "allocated_to": MANAGER},
			pluck="description",
		)
		self.assertEqual(len(todo), 1)
		self.assertNotIn("no email address", todo[0])
		self.assertEqual(frappe.db.get_value("Automation", self.automation, "last_run_status"), "Completed")

	def test_runs_no_email_branch(self):
		supplier = make_supplier("_Test Automation Supplier B")
		run = engine.start_run(
			self.automation, {"event": "after_insert", "doctype": "Supplier", "name": supplier}, now=True
		)
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Completed")
		self.assertEqual(list(self.steps(run)), ["has_email", "assign_check"])
		todo = frappe.get_all(
			"ToDo", filters={"reference_type": "Supplier", "reference_name": supplier}, pluck="description"
		)
		self.assertTrue(todo and "no email address" in todo[0])

	def test_test_run_does_not_send_email(self):
		supplier = make_supplier("_Test Automation Supplier C", "sales@acme.example")
		run = engine.start_run(
			self.automation,
			{"event": "after_insert", "doctype": "Supplier", "name": supplier},
			is_test=True,
			now=True,
		)
		output = json.loads(self.steps(run)["welcome_email"].output_json)["output"]
		self.assertFalse(output["sent"])
		self.assertIn("Dear _Test Automation Supplier C", output["message"])
		self.assertFalse(
			frappe.db.exists("Email Queue", {"reference_doctype": "Supplier", "reference_name": supplier})
		)

	def test_failed_node_fails_run(self):
		spec = load_example("s3_supplier_onboarding")
		spec["nodes"][2]["config"]["role"] = "_Role Nobody Has"
		frappe.db.set_value("Automation", self.automation, "draft_spec", json.dumps(spec))
		supplier = make_supplier("_Test Automation Supplier D")
		run = engine.start_run(
			self.automation, {"event": "after_insert", "doctype": "Supplier", "name": supplier}, now=True
		)
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(doc.status, "Failed")
		self.assertIn("Nobody to assign to", doc.error)
		self.assertEqual(self.steps(run)["assign_check"].status, "Failed")
		install(run_as="Administrator")

	def test_trigger_starts_run_only_when_active(self):
		frappe.db.set_value("Automation", self.automation, "status", "Draft")
		triggers.clear_index()
		with patch.object(engine, "start_run") as start:
			make_supplier("_Test Automation Supplier E")
			start.assert_not_called()

		install(activate=True, run_as="Administrator")
		with patch.object(engine, "start_run") as start:
			supplier = make_supplier("_Test Automation Supplier F")
			start.assert_called_once()
			self.assertEqual(
				start.call_args.args[1], {"event": "after_insert", "doctype": "Supplier", "name": supplier}
			)

	def test_trigger_skips_own_chain_and_condition(self):
		install(activate=True, run_as="Administrator")
		with patch.object(engine, "start_run") as start:
			frappe.flags.automation_chain = [self.automation]
			try:
				make_supplier("_Test Automation Supplier G")
			finally:
				frappe.flags.automation_chain = None
			start.assert_not_called()

		spec = load_example("s3_supplier_onboarding")
		spec["trigger"]["config"]["condition"] = "doc.supplier_type == 'Individual'"
		automation = frappe.get_doc("Automation", self.automation)
		automation.draft_spec = json.dumps(spec)
		automation.save()
		with patch.object(engine, "start_run") as start:
			make_supplier("_Test Automation Supplier H")
			start.assert_not_called()
		install(run_as="Administrator")
