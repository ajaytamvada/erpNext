"""Start automation runs from ERPNext events, schedules and manual clicks.

hooks.py sends every document event here. A cached index of active automations keyed by
(doctype, event) keeps non-matching saves to one dictionary lookup. Matching automations
get a Queued Agent Run inside the same transaction and a job enqueued after commit, so a
save that rolls back never starts a run. The scheduler calls dispatch_schedules() every
minute.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

from pridict.automation import engine, expressions, guards
from pridict.automation import spec as specs

INDEX_CACHE_KEY = "pridict_automation_trigger_index"

# Internal DocTypes whose saves never trigger automations (runs write to most of them).
IGNORED_DOCTYPES = frozenset(
	{
		"Automation",
		"Automation Version",
		"Automation Change",
		"Automation Settings",
		"Agent Run",
		"Agent Run Step",
		"Agent Chat Message",
		"Agent Checkpoint",
		"Agent Checkpoint Blob",
		"Agent Checkpoint Write",
		"Error Log",
		"Scheduled Job Log",
		"Version",
		"Access Log",
		"Activity Log",
		"Route History",
		"Email Queue",
		"Email Queue Recipient",
		"Notification Log",
	}
)


def _build_index() -> dict[str, list[str]]:
	index: dict[str, list[str]] = {}
	for row in frappe.get_all(
		"Automation",
		filters={"status": "Active", "trigger_type": "trigger.document_event"},
		fields=["name", "trigger_doctype", "trigger_event"],
		order_by="name",
	):
		index.setdefault(f"{row.trigger_doctype}::{row.trigger_event}", []).append(row.name)
	return index


def get_index() -> dict[str, list[str]]:
	return frappe.cache().get_value(INDEX_CACHE_KEY, generator=_build_index)


def clear_index():
	frappe.cache().delete_value(INDEX_CACHE_KEY)


# ---------------------------------------------------------------------------
# Document events


def on_doc_event(doc, method: str):
	if doc.doctype in IGNORED_DOCTYPES:
		return
	flags = frappe.flags
	if flags.in_install or flags.in_migrate or flags.in_patch or flags.in_import or flags.in_uninstall:
		return
	names = get_index().get(f"{doc.doctype}::{method}")
	if not names or not guards.enabled():
		return
	chain = list(flags.automation_chain or [])
	for name in names:
		# A run never re-triggers its own automation, and chains of automations stay short.
		if name in chain or len(chain) >= guards.max_chain_depth():
			continue
		version = _active_version(name)
		if not version or not _condition_holds(name, version, doc):
			continue
		if not guards.allow_run(name):
			continue
		engine.start_run(name, {"event": method, "doctype": doc.doctype, "name": doc.name}, chain=chain)


def _active_version(automation: str) -> str | None:
	# The cached index is not transactional, so re-check the automation is still active.
	row = frappe.db.get_value("Automation", automation, ["status", "active_version"], as_dict=True)
	return row.active_version if row and row.status == "Active" else None


def _condition_holds(automation: str, version: str, doc) -> bool:
	spec = specs.load(frappe.db.get_value("Automation Version", version, "spec") or "{}")
	condition = ((spec.get("trigger") or {}).get("config") or {}).get("condition")
	if not condition:
		return True
	scope = {"doc": expressions.attr_dicts(expressions.to_data(doc.as_dict()))}
	try:
		return bool(expressions.evaluate(condition, scope))
	except Exception:
		frappe.log_error(title=f"Automation {automation}: trigger condition failed")
		return False


# ---------------------------------------------------------------------------
# Schedules


def dispatch_schedules():
	"""Scheduler entry (every minute): start every schedule automation that is due."""
	if not guards.enabled():
		return
	now = now_datetime()
	for row in frappe.get_all(
		"Automation",
		filters={"status": "Active", "trigger_type": "trigger.schedule", "trigger_cron": ["is", "set"]},
		fields=["name", "trigger_cron", "last_fired_at", "modified"],
	):
		if is_due(row.trigger_cron, row.last_fired_at or row.modified, now):
			_fire_schedule(row.name, now)


def is_due(cron: str, since, now) -> bool:
	"""True if the cron schedule has a fire time in (since, now]."""
	from croniter import croniter

	since = get_datetime(since)
	# Never catch up more than a day of missed runs after downtime; fire once instead.
	since = max(since, add_to_date(now, days=-1))
	return croniter(cron, since).get_next(type(now)) <= now


def _fire_schedule(automation: str, now):
	# Record the slot before starting, so a failed start is not retried every minute.
	frappe.db.set_value("Automation", automation, "last_fired_at", now, update_modified=False)
	try:
		if guards.allow_run(automation):
			engine.start_run(automation, {"event": "schedule", "fired_at": str(now)})
	except Exception:
		frappe.log_error(title=f"Automation {automation}: scheduled start failed")
	frappe.db.commit()


# ---------------------------------------------------------------------------
# Manual runs


@frappe.whitelist(methods=["POST"])
def run_now(automation: str, doctype: str | None = None, name: str | None = None, input=None) -> dict:  # noqa: A002
	"""Start an active automation by hand, optionally on one document."""
	doc = frappe.get_doc("Automation", automation)
	doc.check_permission("write")
	if not guards.enabled():
		frappe.throw(_("Automations are switched off on this site."))
	if doc.status != "Active":
		frappe.throw(_("Activate the automation before running it."))
	if doctype or name:
		if not (doctype and name):
			frappe.throw(_("Choose both the DocType and the document."))
		frappe.get_doc(doctype, name).check_permission("read")
	trigger = {"event": "manual", "doctype": doctype, "name": name, "input": frappe.parse_json(input)}
	run = engine.start_run(automation, trigger, requested_by=frappe.session.user)
	return {"run": run}
