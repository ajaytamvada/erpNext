"""Load test for automation triggers (design Section 14), run on a dev bench:

	bench --site <site> execute pridict.automation.loadtest.run

Creates 20 active document-event automations and 20 schedules inside a transaction, measures
the document hook and the per-minute dispatcher, then rolls everything back. Targets: trigger
overhead under 2 ms per save, dispatcher under 5 s.
"""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import frappe

from pridict.automation import engine, guards, triggers

DOCTYPES = ("Supplier", "Customer", "Item", "Purchase Order", "Sales Order")


def _spec(trigger: dict, title: str) -> dict:
	return {
		"schema": 1,
		"title": title,
		"trigger": {"id": "trigger", **trigger, "position": [0, 0]},
		"nodes": [{"id": "note", "type": "logic.set_variable", "config": {"name": "x", "value": "1"}}],
		"edges": [{"from": "trigger", "to": "note"}, {"from": "note", "to": "END"}],
		"settings": {"on_error": "stop_and_notify", "max_steps": 10},
	}


def _automation(spec: dict) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Automation",
			"title": spec["title"],
			"draft_spec": json.dumps(spec),
			"run_as": "Administrator",
		}
	).insert()
	doc.activate("load test", require_test=False)
	return doc.name


def _time(fn, repeat: int) -> float:
	started = time.perf_counter()
	for _ in range(repeat):
		fn()
	return (time.perf_counter() - started) / repeat * 1000


def run(repeat: int = 2000) -> dict:
	report = {}
	with patch.object(frappe.db, "commit"):
		try:
			frappe.db.set_single_value("Automation Settings", {"enabled": 1, "pause_all": 0})
			frappe.clear_document_cache(guards.SETTINGS, guards.SETTINGS)
			for i in range(20):
				doctype = DOCTYPES[i % len(DOCTYPES)]
				# Conditions that never hold, so the hook does its full check without starting runs.
				_automation(
					_spec(
						{
							"type": "trigger.document_event",
							"config": {
								"doctype": doctype,
								"event": "on_update",
								"condition": "doc.name == '__never__'",
							},
						},
						f"Load doc {i}",
					)
				)
				_automation(
					_spec(
						{"type": "trigger.schedule", "config": {"cron": f"{i} 3 * * *"}}, f"Load schedule {i}"
					)
				)
			triggers.clear_index()
			triggers.get_index()

			todo = frappe.get_doc({"doctype": "ToDo", "description": "load test"}).insert()
			supplier = frappe.get_doc("Supplier", frappe.get_all("Supplier", pluck="name", limit=1)[0])
			with patch.object(engine, "start_run") as start:
				report["hook_no_match_ms"] = round(
					_time(lambda: triggers.on_doc_event(todo, "on_update"), repeat), 4
				)
				report["hook_match_condition_false_ms"] = round(
					_time(lambda: triggers.on_doc_event(supplier, "on_update"), max(repeat // 10, 50)), 4
				)
				report["runs_started"] = start.call_count
				report["dispatcher_ms"] = round(_time(triggers.dispatch_schedules, 20), 2)
			saves = 200
			started = time.perf_counter()
			for _ in range(saves):
				todo.description = f"load test {time.perf_counter()}"
				todo.save()
			report["todo_save_ms_with_hook"] = round((time.perf_counter() - started) / saves * 1000, 2)
			report["active_doc_automations"] = 20
			report["active_schedules"] = 20
			report["meets_targets"] = (
				report["hook_match_condition_false_ms"] < 2 and report["dispatcher_ms"] < 5000
			)
		finally:
			frappe.db.rollback()
			triggers.clear_index()
			frappe.clear_document_cache(guards.SETTINGS, guards.SETTINGS)
	print(json.dumps(report, indent=1))
	return report
