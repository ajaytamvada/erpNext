"""Engine tests: specs compiled to LangGraph and run against real records."""

from __future__ import annotations

import json

import frappe

from pridict.automation import engine, guards
from pridict.automation.examples import load_example
from pridict.automation.test_helpers import (
	MANAGER,
	AutomationTestCase,
	install_example,
	make_supplier,
	manual_spec,
	spec_automation,
	step_list,
	steps,
)


def supplier_trigger(name: str) -> dict:
	return {"event": "after_insert", "doctype": "Supplier", "name": name}


class TestS3Runs(AutomationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.automation = install_example("s3_supplier_onboarding")

	def test_runs_email_branch(self):
		supplier = make_supplier("_Test Automation Supplier A", "accounts@acme.example")
		run = engine.start_run(self.automation, supplier_trigger(supplier), now=True)
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(doc.status, "Completed", doc.error)
		self.assertEqual(
			doc.automation_version, frappe.db.get_value("Automation", self.automation, "active_version")
		)
		self.assertEqual(step_list(run), ["has_email", "welcome_email", "assign_check"])
		self.assertEqual(json.loads(steps(run)["has_email"].output_json)["route"], "true")
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
		run = engine.start_run(self.automation, supplier_trigger(supplier), now=True)
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Completed")
		self.assertEqual(step_list(run), ["has_email", "assign_check"])
		todo = frappe.get_all(
			"ToDo", filters={"reference_type": "Supplier", "reference_name": supplier}, pluck="description"
		)
		self.assertTrue(todo and "no email address" in todo[0])

	def test_test_run_uses_draft_and_does_not_send(self):
		supplier = make_supplier("_Test Automation Supplier C", "sales@acme.example")
		run = engine.start_run(self.automation, supplier_trigger(supplier), is_test=True, now=True)
		self.assertFalse(frappe.db.get_value("Agent Run", run, "automation_version"))
		output = json.loads(steps(run)["welcome_email"].output_json)["output"]
		self.assertFalse(output["sent"])
		self.assertIn("Dear _Test Automation Supplier C", output["message"])
		self.assertFalse(
			frappe.db.exists("Email Queue", {"reference_doctype": "Supplier", "reference_name": supplier})
		)

	def test_live_runs_need_an_active_version(self):
		draft = frappe.get_doc(
			{
				"doctype": "Automation",
				"title": "Never activated",
				"draft_spec": json.dumps(load_example("s3_supplier_onboarding")),
			}
		).insert()
		with self.assertRaises(frappe.ValidationError):
			engine.start_run(draft.name, supplier_trigger("x"))

	def test_switched_off_site_cancels_queued_runs(self):
		supplier = make_supplier("_Test Automation Supplier K")
		run = engine.start_run(self.automation, supplier_trigger(supplier))
		frappe.db.set_single_value("Automation Settings", "pause_all", 1)
		frappe.clear_document_cache(guards.SETTINGS, guards.SETTINGS)
		try:
			self.assertEqual(engine.execute(run), "Cancelled")
		finally:
			frappe.db.set_single_value("Automation Settings", "pause_all", 0)
			frappe.clear_document_cache(guards.SETTINGS, guards.SETTINGS)


class TestFailures(AutomationTestCase):
	def broken_automation(self, **settings) -> str:
		spec = load_example("s3_supplier_onboarding")
		spec["title"] = "Broken onboarding"
		spec["nodes"][2]["config"]["role"] = "Guest"  # no enabled system user has it
		spec["settings"].update(settings)
		return spec_automation(spec)

	def test_failed_node_fails_run_and_notifies_owner(self):
		automation = self.broken_automation()
		supplier = make_supplier("_Test Automation Supplier D")
		run = engine.start_run(automation, supplier_trigger(supplier), now=True)
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(doc.status, "Failed")
		self.assertIn("Nobody to assign to", doc.error)
		self.assertEqual(steps(run)["assign_check"].status, "Failed")
		self.assertEqual(frappe.db.get_value("Automation", automation, "consecutive_failures"), 1)
		self.assertTrue(
			frappe.db.exists("Notification Log", {"document_type": "Automation", "document_name": automation})
		)

	def test_auto_pause_after_repeated_failures(self):
		frappe.db.set_single_value("Automation Settings", "max_failures_before_pause", 2)
		frappe.clear_document_cache(guards.SETTINGS, guards.SETTINGS)
		automation = self.broken_automation()
		supplier = make_supplier("_Test Automation Supplier E")
		for _attempt in range(2):
			engine.start_run(automation, supplier_trigger(supplier), now=True)
		doc = frappe.get_doc("Automation", automation)
		self.assertEqual(doc.status, "Paused")
		self.assertIn("2 failed runs", doc.paused_reason)
		frappe.db.set_single_value("Automation Settings", "max_failures_before_pause", 5)
		frappe.clear_document_cache(guards.SETTINGS, guards.SETTINGS)

	def test_success_resets_failures(self):
		automation = install_example("s3_supplier_onboarding")
		frappe.db.set_value("Automation", automation, "consecutive_failures", 3)
		engine.start_run(automation, supplier_trigger(make_supplier("_Test Automation Supplier F")), now=True)
		self.assertEqual(frappe.db.get_value("Automation", automation, "consecutive_failures"), 0)

	def test_on_error_continue(self):
		automation = self.broken_automation(on_error="continue")
		supplier = make_supplier("_Test Automation Supplier G")
		run = engine.start_run(automation, supplier_trigger(supplier), now=True)
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Completed")
		self.assertEqual(steps(run)["assign_check"].status, "Failed")


class TestLogicNodes(AutomationTestCase):
	def run_manual(self, spec: dict, **trigger) -> str:
		automation = spec_automation(spec)
		return engine.start_run(automation, {"event": "manual", **trigger}, now=True)

	def test_set_variable_switch_and_stop(self):
		spec = manual_spec(
			[
				{
					"id": "total",
					"type": "logic.set_variable",
					"config": {"name": "total", "value": "{{ 40 + 2 }}"},
				},
				{
					"id": "size",
					"type": "logic.switch",
					"config": {
						"cases": [
							{"name": "big", "condition": "vars.total > 100"},
							{"name": "medium", "condition": "vars.total > 10"},
						]
					},
				},
				{
					"id": "halt",
					"type": "logic.stop",
					"config": {"status": "Failed", "message": "Too {{ vars.total }}"},
				},
			],
			[
				{"from": "trigger", "to": "total"},
				{"from": "total", "to": "size"},
				{"from": "size", "to": "END", "branch": "big"},
				{"from": "size", "to": "halt", "branch": "medium"},
				{"from": "size", "to": "END", "branch": "default"},
			],
		)
		run = self.run_manual(spec)
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(step_list(run), ["total", "size", "halt"])
		self.assertEqual(doc.status, "Failed")
		self.assertEqual(doc.error, "Too 42")
		result = json.loads(doc.result_json)
		self.assertEqual(result["vars"], {"total": 42})

	def test_loop_runs_body_per_item(self):
		spec = manual_spec(
			[
				{
					"id": "names",
					"type": "logic.set_variable",
					"config": {"name": "names", "value": "{{ ['a', 'b', 'c'] }}"},
				},
				{"id": "each", "type": "logic.loop", "config": {"items": "{{ vars.names }}"}},
				{
					"id": "seen",
					"type": "logic.set_variable",
					"config": {"name": "last", "value": "{{ nodes.each.item }}-{{ nodes.each.index }}"},
				},
			],
			[
				{"from": "trigger", "to": "names"},
				{"from": "names", "to": "each"},
				{"from": "each", "to": "seen", "branch": "body"},
				{"from": "each", "to": "END", "branch": "done"},
				{"from": "seen", "to": "each"},
			],
		)
		run = self.run_manual(spec)
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Completed")
		self.assertEqual(step_list(run), ["names", "each", "seen", "each", "seen", "each", "seen", "each"])
		self.assertEqual(
			json.loads(frappe.db.get_value("Agent Run", run, "result_json"))["vars"]["last"], "c-2"
		)

	def test_max_steps_stops_runaway_loops(self):
		spec = manual_spec(
			[
				{
					"id": "names",
					"type": "logic.set_variable",
					"config": {"name": "n", "value": "{{ range(50) | list }}"},
				},
				{"id": "each", "type": "logic.loop", "config": {"items": "{{ vars.n }}"}},
				{
					"id": "seen",
					"type": "logic.set_variable",
					"config": {"name": "x", "value": "{{ nodes.each.item }}"},
				},
			],
			[
				{"from": "trigger", "to": "names"},
				{"from": "names", "to": "each"},
				{"from": "each", "to": "seen", "branch": "body"},
				{"from": "each", "to": "END", "branch": "done"},
				{"from": "seen", "to": "each"},
			],
			max_steps=20,
		)
		run = self.run_manual(spec)
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Failed")


class TestEmailCap(AutomationTestCase):
	def test_per_automation_email_cap(self):
		automation = install_example("s3_supplier_onboarding")
		frappe.db.set_value("Automation", automation, "max_emails_per_day", 1)
		first = engine.start_run(
			automation,
			supplier_trigger(make_supplier("_Test Automation Supplier H", "h@acme.example")),
			now=True,
		)
		second = engine.start_run(
			automation,
			supplier_trigger(make_supplier("_Test Automation Supplier I", "i@acme.example")),
			now=True,
		)
		self.assertEqual(frappe.db.get_value("Agent Run", first, "status"), "Completed")
		doc = frappe.get_doc("Agent Run", second)
		self.assertEqual(doc.status, "Failed")
		self.assertIn("limit of 1 emails per day", doc.error)
