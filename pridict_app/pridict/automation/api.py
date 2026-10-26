"""Whitelisted endpoints for the Automation Builder page."""

from __future__ import annotations

import frappe

from pridict.automation import nodes as catalog
from pridict.automation import spec as specs

RECENT_RUNS = 15


@frappe.whitelist()
def get_builder(name: str, run: str | None = None) -> dict:
	"""Everything the read-only canvas needs: spec, validation, catalog, recent runs, one run's trace."""
	doc = frappe.get_doc("Automation", name)
	doc.check_permission("read")
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
	return {
		"automation": {
			"name": doc.name,
			"title": doc.title,
			"description": doc.description,
			"status": doc.status,
			"run_as": doc.run_as,
			"draft_revision": doc.draft_revision,
			"last_run_at": doc.last_run_at,
			"last_run_status": doc.last_run_status,
		},
		"spec": spec,
		"validation": specs.validate(spec),
		"catalog": {node["type"]: node for node in catalog.describe_all()},
		"runs": runs,
		"run": _run_trace(selected, name) if selected else None,
	}


def _run_trace(run: str, automation: str) -> dict | None:
	doc = frappe.get_doc("Agent Run", run)
	if doc.automation != automation:
		return None
	steps = {}
	for step in doc.steps:
		if step.node_id:
			recorded = frappe.parse_json(step.output_json) if step.output_json else {}
			# A node can run more than once (loops, later phases); keep the latest.
			steps[step.node_id] = {
				"status": step.status,
				"summary": step.summary,
				"duration_ms": step.duration_ms,
				"output": recorded.get("output"),
				"route": recorded.get("route"),
			}
	return {
		"name": doc.name,
		"status": doc.status,
		"is_test": doc.is_test,
		"trigger": {"doctype": doc.trigger_doctype, "name": doc.trigger_name, "event": doc.trigger_event},
		"started_at": doc.started_at,
		"duration_s": doc.duration_s,
		"error": doc.error,
		"steps": steps,
	}
