"""Hourly housekeeping for Agent Studio runs and approvals."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, now_datetime

from pridict.agent_studio.checkpointer import MariaDBSaver
from pridict.agent_studio.runtime import post_message

STALE_REQUEST_DAYS = 14
ORPHAN_HOURS = 2


def _idle_since(statuses: list[str], cutoff) -> list[str]:
	"""Runs in these statuses whose last recorded step (or creation) is older than cutoff."""
	idle = []
	for run in frappe.get_all(
		"Agent Run",
		filters={"status": ["in", statuses], "creation": ["<", cutoff]},
		fields=["name", "creation"],
	):
		last_step = frappe.db.get_value(
			"Agent Run Step", {"parent": run.name, "parenttype": "Agent Run"}, "max(started_at)"
		)
		if (last_step or run.creation) < cutoff:
			idle.append(run.name)
	return idle


def hourly():
	fail_orphaned_runs()
	expire_stale_requests()
	release_stuck_conversations()


def fail_orphaned_runs():
	"""Runs still Queued/Running long after any job timeout: the worker died or was restarted."""
	for name in _idle_since(["Queued", "Running"], add_to_date(now_datetime(), hours=-ORPHAN_HOURS)):
		frappe.db.set_value(
			"Agent Run",
			name,
			{
				"status": "Failed",
				"error": _("The background worker stopped before the run finished."),
				"ended_at": now_datetime(),
			},
		)
		post_message(
			name,
			"assistant",
			_("Sorry, I was interrupted before I could finish this request. Please start it again."),
			"error",
		)
		MariaDBSaver().delete_thread(name)
	frappe.db.commit()


def expire_stale_requests():
	"""Questions and approvals nobody answered within STALE_REQUEST_DAYS: close them."""
	stale = _idle_since(
		["Waiting for buyer", "Awaiting approval"], add_days(now_datetime(), -STALE_REQUEST_DAYS)
	)
	for name in stale:
		for approval in frappe.get_all(
			"Agent Approval", filters={"run": name, "status": "Pending"}, pluck="name"
		):
			frappe.db.set_value(
				"Agent Approval",
				approval,
				{
					"status": "Expired",
					"decision_note": _("No decision within {0} days").format(STALE_REQUEST_DAYS),
				},
			)
		frappe.db.set_value(
			"Agent Run",
			name,
			{
				"status": "Cancelled",
				"pending_question": None,
				"ended_at": now_datetime(),
				"outcome": _("Closed automatically: nobody responded within {0} days.").format(
					STALE_REQUEST_DAYS
				),
			},
		)
		post_message(
			name,
			"assistant",
			_("I closed this request because nobody responded within {0} days.").format(STALE_REQUEST_DAYS),
			"notice",
		)
		MariaDBSaver().delete_thread(name)
	frappe.db.commit()


def release_stuck_conversations():
	"""Conversations still marked working long after any job timeout: the worker stopped mid-reply."""
	cutoff = add_to_date(now_datetime(), hours=-ORPHAN_HOURS)
	for name in frappe.get_all(
		"Assistant Conversation", filters={"working": 1, "last_activity": ["<", cutoff]}, pluck="name"
	):
		frappe.db.set_value("Assistant Conversation", name, "working", 0, update_modified=False)
		post_message(
			name,
			"assistant",
			_("Sorry, I was interrupted before I could answer. Please ask again."),
			"error",
			parenttype="Assistant Conversation",
		)
	frappe.db.commit()
