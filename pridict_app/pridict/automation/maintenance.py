"""Housekeeping for automations: run retention, re-validation after upgrades, health figures."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, now_datetime

from pridict.agent_studio.checkpointer import MariaDBSaver
from pridict.automation import guards
from pridict.automation import spec as specs

PURGE_BATCH = 500
TEST_RUN_DAYS = 7


def daily():
	"""Scheduler entry: delete old automation runs."""
	purge_old_runs()


def purge_old_runs() -> int:
	"""Delete finished automation runs past the retention period (traces, messages, checkpoints)."""
	settings = guards.settings()
	keep = {
		"Completed": settings.run_retention_days or 30,
		"Cancelled": settings.run_retention_days or 30,
		"Failed": settings.failed_run_retention_days or 90,
	}
	removed = 0
	for status, days in keep.items():
		cutoff = add_days(now_datetime(), -int(days))
		removed += _purge({"status": status, "is_test": 0, "ended_at": ["<", cutoff]})
	# Test runs are only useful while their draft is being worked on.
	removed += _purge({"is_test": 1, "creation": ["<", add_days(now_datetime(), -TEST_RUN_DAYS)]})
	frappe.db.commit()
	return removed


def _purge(filters: dict) -> int:
	used = set(frappe.get_all("Automation Version", filters={"test_run": ["is", "set"]}, pluck="test_run"))
	runs = [
		name
		for name in frappe.get_all(
			"Agent Run", filters={"automation": ["is", "set"], **filters}, pluck="name", limit=PURGE_BATCH
		)
		# Keep the test runs that unlocked a version: they are the audit trail of activation.
		if name not in used
	]
	saver = MariaDBSaver()
	for run in runs:
		for child in ("Agent Run Step", "Agent Chat Message"):
			frappe.db.delete(child, {"parent": run, "parenttype": "Agent Run"})
		saver.delete_thread(run)
		frappe.db.delete("Agent Run", {"name": run})
	return len(runs)


def revalidate_active() -> list[str]:
	"""After an upgrade, check active automations against the site; pause any that broke.

	ERPNext updates can rename or remove fields an automation uses (design Section 16). Setup
	problems (permissions, email accounts) do not pause: only design errors do.
	"""
	if not frappe.db.exists("DocType", "Automation"):
		return []
	paused = []
	for row in frappe.get_all(
		"Automation", filters={"status": "Active"}, fields=["name", "run_as", "active_version"]
	):
		spec_json = (
			frappe.db.get_value("Automation Version", row.active_version, "spec")
			if row.active_version
			else None
		)
		if not spec_json:
			continue
		issues = specs.validate(specs.load(spec_json), live=True, run_as=row.run_as)
		errors = [i["message"] for i in issues if i["level"] == "error" and i.get("kind") != "setup"]
		if not errors:
			continue
		reason = _("Paused after a system update: {0}").format("; ".join(errors)[:900])
		frappe.db.set_value(
			"Automation", row.name, {"status": "Paused", "paused_reason": reason}, update_modified=False
		)
		guards.notify_owner(row.name, reason)
		paused.append(row.name)
	if paused:
		from pridict.automation import triggers

		triggers.clear_index()
	return paused


@frappe.whitelist()
def health() -> dict:
	"""Figures for the Automations page: last 24 hours, guardrail pauses, waiting work, queue."""
	if not frappe.has_permission("Automation", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	since = add_to_date(now_datetime(), hours=-24)
	counts = dict(
		frappe.get_all(
			"Agent Run",
			filters={"automation": ["is", "set"], "is_test": 0, "creation": [">", since]},
			fields=["status", "count(*) as runs"],
			group_by="status",
			as_list=True,
		)
	)
	total = sum(counts.values())
	failed = counts.get("Failed", 0)
	return {
		"enabled": guards.enabled(),
		"runs_24h": total,
		"failed_24h": failed,
		"failure_rate": round(100 * failed / total, 1) if total else 0,
		"waiting": counts.get("Waiting", 0) + counts.get("Awaiting approval", 0),
		"paused": frappe.db.count("Automation", {"status": "Paused"}),
		"active": frappe.db.count("Automation", {"status": "Active"}),
		"queued": _queue_length(),
		"emails_today": _emails_today(),
	}


def _queue_length() -> int | None:
	try:
		from frappe.utils.background_jobs import get_queue

		from pridict.automation import engine

		return len(get_queue(engine.queue()))
	except Exception:
		return None


def _emails_today() -> int:
	cache = frappe.cache()
	value = cache.get(
		cache.make_key(f"{guards.COUNTER_PREFIX}:emails:site:{now_datetime().strftime('%Y%m%d')}")
	)
	return int(value or 0)
