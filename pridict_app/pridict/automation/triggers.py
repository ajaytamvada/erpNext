"""Start automation runs from ERPNext events.

hooks.py sends every document event here. A cached index of active automations keyed by
(doctype, event) keeps non-matching saves to one dictionary lookup. Matching automations
get a Queued Agent Run inside the same transaction and a job enqueued after commit, so a
save that rolls back never starts a run.
"""

from __future__ import annotations

import frappe

from pridict.automation import engine, expressions
from pridict.automation import spec as specs

INDEX_CACHE_KEY = "pridict_automation_trigger_index"

# Internal DocTypes whose saves never trigger automations (runs write to most of them).
IGNORED_DOCTYPES = frozenset(
	{
		"Automation",
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


def on_doc_event(doc, method: str):
	if doc.doctype in IGNORED_DOCTYPES:
		return
	flags = frappe.flags
	if flags.in_install or flags.in_migrate or flags.in_patch or flags.in_import or flags.in_uninstall:
		return
	names = get_index().get(f"{doc.doctype}::{method}")
	if not names:
		return
	chain = list(flags.automation_chain or [])
	for name in names:
		# A run never re-triggers its own automation, and chains of automations stay short.
		if name in chain or len(chain) >= engine.MAX_CHAIN_DEPTH:
			continue
		if not _should_start(name, doc):
			continue
		engine.start_run(name, {"event": method, "doctype": doc.doctype, "name": doc.name}, chain=chain)


def _should_start(automation: str, doc) -> bool:
	# The cached index is not transactional, so re-check the automation is still active.
	row = frappe.db.get_value("Automation", automation, ["status", "draft_spec"], as_dict=True)
	if not row or row.status != "Active":
		return False
	spec = specs.load(row.draft_spec or "{}")
	condition = ((spec.get("trigger") or {}).get("config") or {}).get("condition")
	if not condition:
		return True
	scope = {"doc": expressions.attr_dicts(expressions.to_data(doc.as_dict()))}
	try:
		return bool(expressions.evaluate(condition, scope))
	except Exception:
		frappe.log_error(title=f"Automation {automation}: trigger condition failed")
		return False
