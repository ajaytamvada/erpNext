"""Whitelisted endpoints for the Automation Builder (canvas, chat and form all use these)."""

from __future__ import annotations

import json

import frappe
from frappe import _

from pridict.automation import guards
from pridict.automation import nodes as catalog
from pridict.automation import spec as specs

RECENT_RUNS = 15
UPDATE_EVENT = "automation_update"


def _automation(name: str, ptype: str = "read"):
	doc = frappe.get_doc("Automation", name)
	doc.check_permission(ptype)
	return doc


@frappe.whitelist()
def get_builder(name: str, run: str | None = None) -> dict:
	"""Everything the builder needs: spec, validation, catalog, versions, recent runs, one run's trace."""
	doc = _automation(name)
	spec = specs.load(doc.draft_spec or "{}")
	runs = frappe.get_all(
		"Agent Run",
		filters={"automation": name},
		fields=[
			"name",
			"status",
			"is_test",
			"trigger_doctype",
			"trigger_name",
			"started_at",
			"duration_s",
			"error",
		],
		order_by="creation desc",
		limit=RECENT_RUNS,
	)
	selected = run or (runs[0].name if runs else None)
	active_hash = doc.active_version and frappe.db.get_value(
		"Automation Version", doc.active_version, "spec_hash"
	)
	return {
		"automation": {
			"name": doc.name,
			"title": doc.title,
			"description": doc.description,
			"status": doc.status,
			"run_as": doc.run_as,
			"draft_revision": doc.draft_revision,
			"active_version": doc.active_version,
			"draft_matches_active": bool(active_hash) and active_hash == specs.spec_hash(spec),
			"paused_reason": doc.paused_reason,
			"last_run_at": doc.last_run_at,
			"last_run_status": doc.last_run_status,
			"can_edit": doc.has_permission("write"),
		},
		"site": {"enabled": guards.enabled()},
		"spec": spec,
		"validation": specs.validate(spec, live=True, run_as=doc.run_as),
		"catalog": {node["type"]: node for node in catalog.describe_all()},
		"runs": runs,
		"run": _run_trace(selected, name) if selected else None,
	}


@frappe.whitelist()
def get_catalog() -> list[dict]:
	return catalog.describe_all()


@frappe.whitelist(methods=["POST"])
def apply_ops(name: str, base_revision: int, ops, source: str = "canvas", summary: str | None = None) -> dict:
	"""Apply operations to the draft if nobody changed it since base_revision.

	Returns {ok, revision, spec, validation} or {ok: False, conflict: True, revision} when the
	editor must reload first.
	"""
	from pridict.pridict.doctype.automation.automation import log_change

	if source not in ("ai", "canvas", "api"):
		frappe.throw(_("Unknown source {0}.").format(source))
	ops = frappe.parse_json(ops)
	# Lock the row so two editors cannot both apply against the same revision.
	current = frappe.db.get_value("Automation", name, "draft_revision", for_update=True)
	if current is None:
		frappe.throw(_("Automation {0} not found.").format(name), frappe.DoesNotExistError)
	doc = _automation(name, "write")
	if int(base_revision) != int(doc.draft_revision or 0):
		return {"ok": False, "conflict": True, "revision": doc.draft_revision}
	try:
		new_spec = specs.apply_ops(specs.load(doc.draft_spec or "{}"), ops)
	except specs.OpError as error:
		return {"ok": False, "error": str(error), "revision": doc.draft_revision}
	doc.draft_spec = json.dumps(new_spec, indent=1, ensure_ascii=False)
	doc.title = new_spec.get("title") or doc.title
	doc.description = new_spec.get("description") or doc.description
	doc.flags.from_ops = True
	doc.save()
	log_change(doc, source, summary or specs.describe_ops(ops), ops)
	_announce(doc)
	return {
		"ok": True,
		"revision": doc.draft_revision,
		"spec": specs.load(doc.draft_spec),
		"validation": specs.validate(specs.load(doc.draft_spec), live=True, run_as=doc.run_as),
	}


@frappe.whitelist()
def validate(name: str) -> list[dict]:
	doc = _automation(name)
	return specs.validate(specs.load(doc.draft_spec or "{}"), live=True, run_as=doc.run_as)


@frappe.whitelist(methods=["POST"])
def activate(name: str, change_note: str | None = None) -> dict:
	doc = _automation(name, "write")
	version = doc.activate(change_note)
	_announce(doc)
	return {"status": doc.status, "active_version": version}


@frappe.whitelist(methods=["POST"])
def pause(name: str) -> dict:
	doc = _automation(name, "write")
	doc.pause()
	_announce(doc)
	return {"status": doc.status}


@frappe.whitelist(methods=["POST"])
def resume(name: str) -> dict:
	doc = _automation(name, "write")
	doc.resume()
	_announce(doc)
	return {"status": doc.status}


@frappe.whitelist(methods=["POST"])
def disable(name: str) -> dict:
	doc = _automation(name, "write")
	doc.disable()
	_announce(doc)
	return {"status": doc.status}


@frappe.whitelist()
def get_history(name: str, limit: int = 50) -> list[dict]:
	_automation(name)
	return frappe.get_all(
		"Automation Change",
		filters={"automation": name},
		fields=["name", "revision", "source", "summary", "owner", "creation"],
		order_by="creation desc",
		limit=min(int(limit), 200),
	)


@frappe.whitelist(methods=["POST"])
def restore(name: str, change: str) -> dict:
	"""Make an earlier revision the draft again (recorded as a new revision)."""
	from pridict.pridict.doctype.automation.automation import log_change

	doc = _automation(name, "write")
	row = frappe.db.get_value("Automation Change", change, ["automation", "revision", "spec"], as_dict=True)
	if not row or row.automation != name:
		frappe.throw(_("That change does not belong to this automation."))
	doc.draft_spec = row.spec
	doc.flags.from_ops = True
	doc.save()
	log_change(doc, "restore", _("Restored revision {0}").format(row.revision), None)
	_announce(doc)
	return {"revision": doc.draft_revision}


def _announce(doc):
	# Payload carries no spec; open editors re-fetch through get_builder.
	frappe.publish_realtime(
		UPDATE_EVENT,
		{"automation": doc.name, "revision": doc.draft_revision, "status": doc.status},
		doctype="Automation",
		docname=doc.name,
		after_commit=True,
	)


def _run_trace(run: str, automation: str) -> dict | None:
	doc = frappe.get_doc("Agent Run", run)
	if doc.automation != automation:
		return None
	steps = {}
	for step in doc.steps:
		if step.node_id:
			recorded = frappe.parse_json(step.output_json) if step.output_json else {}
			# A node can run more than once (loops); keep the latest and count the runs.
			steps[step.node_id] = {
				"status": step.status,
				"summary": step.summary,
				"duration_ms": step.duration_ms,
				"output": recorded.get("output"),
				"route": recorded.get("route"),
				"times": steps.get(step.node_id, {}).get("times", 0) + 1,
			}
	return {
		"name": doc.name,
		"status": doc.status,
		"is_test": doc.is_test,
		"trigger": {"doctype": doc.trigger_doctype, "name": doc.trigger_name, "event": doc.trigger_event},
		"started_at": doc.started_at,
		"duration_s": doc.duration_s,
		"error": doc.error,
		"outcome": doc.outcome,
		"steps": steps,
	}
