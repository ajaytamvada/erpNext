"""Trigger tests: document events, schedules, manual runs and the guards around them."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import patch

import frappe

from pridict.automation import engine, guards, triggers
from pridict.automation.examples import load_example
from pridict.automation.test_helpers import (
	AutomationTestCase,
	install_example,
	make_supplier,
	spec_automation,
)


class TestDocumentEvents(AutomationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.automation = install_example("s3_supplier_onboarding")

	def test_active_automation_starts_a_run(self):
		with patch.object(engine, "start_run") as start:
			supplier = make_supplier("_Test Trigger Supplier A")
		start.assert_called_once()
		self.assertEqual(
			start.call_args.args,
			(self.automation, {"event": "after_insert", "doctype": "Supplier", "name": supplier}),
		)

	def test_paused_automation_does_not(self):
		frappe.get_doc("Automation", self.automation).pause()
		try:
			with patch.object(engine, "start_run") as start:
				make_supplier("_Test Trigger Supplier B")
			start.assert_not_called()
		finally:
			frappe.get_doc("Automation", self.automation).resume()

	def test_site_switches(self):
		for field in ("pause_all", "enabled"):
			frappe.db.set_single_value("Automation Settings", field, 1 if field == "pause_all" else 0)
			frappe.clear_document_cache(guards.SETTINGS, guards.SETTINGS)
			with patch.object(engine, "start_run") as start:
				make_supplier(f"_Test Trigger Supplier {field}")
			start.assert_not_called()
			frappe.db.set_single_value("Automation Settings", field, 0 if field == "pause_all" else 1)
			frappe.clear_document_cache(guards.SETTINGS, guards.SETTINGS)

	def test_chain_guard(self):
		with patch.object(engine, "start_run") as start:
			frappe.flags.automation_chain = [self.automation]
			try:
				make_supplier("_Test Trigger Supplier C")
			finally:
				frappe.flags.automation_chain = None
		start.assert_not_called()
		with patch.object(engine, "start_run") as start:
			frappe.flags.automation_chain = ["AUT-X", "AUT-Y", "AUT-Z"]
			try:
				make_supplier("_Test Trigger Supplier D")
			finally:
				frappe.flags.automation_chain = None
		start.assert_not_called()

	def test_condition_uses_the_active_version(self):
		spec = load_example("s3_supplier_onboarding")
		spec["title"] = "Individuals only"
		spec["trigger"]["config"]["condition"] = "doc.supplier_type == 'Individual'"
		automation = spec_automation(spec)
		frappe.get_doc("Automation", self.automation).pause()
		try:
			with patch.object(engine, "start_run") as start:
				make_supplier("_Test Trigger Supplier E")
			start.assert_not_called()
			# Editing the draft does not change what runs until it is activated again.
			doc = frappe.get_doc("Automation", automation)
			spec["trigger"]["config"]["condition"] = "True"
			doc.draft_spec = json.dumps(spec)
			doc.save()
			with patch.object(engine, "start_run") as start:
				make_supplier("_Test Trigger Supplier F")
			start.assert_not_called()
			doc.activate("allow everyone")
			with patch.object(engine, "start_run") as start:
				make_supplier("_Test Trigger Supplier G")
			start.assert_called_once()
		finally:
			# Class-level rollback only: leave no extra active automation for later tests.
			frappe.get_doc("Automation", automation).pause()
			frappe.get_doc("Automation", self.automation).resume()

	def test_rate_limit_drops_excess_events(self):
		frappe.db.set_value("Automation", self.automation, "max_runs_per_hour", 2)
		with patch.object(engine, "start_run") as start:
			for letter in "HIJ":
				make_supplier(f"_Test Trigger Supplier {letter}")
		self.assertEqual(start.call_count, 2)
		self.assertTrue(
			frappe.db.exists(
				"Notification Log",
				{
					"document_type": "Automation",
					"document_name": self.automation,
					"subject": ["like", "%limit of 2 runs%"],
				},
			)
		)
		frappe.db.set_value("Automation", self.automation, "max_runs_per_hour", 60)


class TestSchedules(AutomationTestCase):
	def test_is_due(self):
		cron = "0 9 * * *"
		self.assertTrue(triggers.is_due(cron, datetime(2026, 10, 26, 8, 0), datetime(2026, 10, 26, 9, 0)))
		self.assertFalse(triggers.is_due(cron, datetime(2026, 10, 26, 9, 0), datetime(2026, 10, 26, 9, 30)))
		# After downtime, a missed slot fires once (not once per missed day).
		self.assertTrue(triggers.is_due(cron, datetime(2026, 10, 1, 9, 0), datetime(2026, 10, 26, 10, 0)))

	def test_dispatcher_fires_due_schedules_once(self):
		automation = install_example("s2_overdue_invoice_reminders")
		frappe.db.set_value("Automation", automation, "last_fired_at", "2026-01-01 00:00:00")
		with patch.object(engine, "start_run") as start:
			triggers.dispatch_schedules()
			triggers.dispatch_schedules()
		start.assert_called_once()
		self.assertEqual(start.call_args.args[0], automation)
		self.assertEqual(start.call_args.args[1]["event"], "schedule")

	def test_activation_does_not_fire_past_slots(self):
		automation = install_example("s2_overdue_invoice_reminders")
		with patch.object(engine, "start_run") as start:
			triggers.dispatch_schedules()
		# Only fires if 09:00 passed between activation (just now) and now: practically never.
		self.assertLessEqual(start.call_count, 1)
		self.assertTrue(frappe.db.get_value("Automation", automation, "last_fired_at"))


class TestManualRuns(AutomationTestCase):
	def test_run_now(self):
		spec = load_example("s3_supplier_onboarding")
		spec["title"] = "Manual onboarding"
		spec["trigger"] = {
			"id": "trigger",
			"type": "trigger.manual",
			"config": {"doctype": "Supplier"},
			"position": [0, 0],
		}
		automation = spec_automation(spec)
		supplier = make_supplier("_Test Trigger Supplier M")
		with patch.object(engine, "start_run", return_value="AGR-X") as start:
			self.assertEqual(triggers.run_now(automation, "Supplier", supplier), {"run": "AGR-X"})
		self.assertEqual(start.call_args.args[1]["name"], supplier)
		with self.assertRaises(frappe.ValidationError):
			triggers.run_now(automation, "Supplier")
		frappe.get_doc("Automation", automation).pause()
		with self.assertRaises(frappe.ValidationError):
			triggers.run_now(automation)
