"""Whitelisted endpoints for the Automation Builder (canvas, chat and form all use these)."""

from __future__ import annotations

import json

import frappe
from frappe import _

from pridict.automation import expressions, guards
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
			"tested": bool(passing_test(doc.name, specs.spec_hash(spec))),
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
	old_spec = specs.load(doc.draft_spec or "{}")
	try:
		new_spec = specs.apply_ops(old_spec, ops)
	except specs.OpError as error:
		return {"ok": False, "error": str(error), "revision": doc.draft_revision}
	if specs.canonical(new_spec) == specs.canonical(old_spec):
		# Nothing changed (for example a step dropped where it already was): no new revision.
		return {
			"ok": True,
			"revision": doc.draft_revision,
			"spec": old_spec,
			"validation": specs.validate(old_spec, live=True, run_as=doc.run_as),
		}
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
def test_run(name: str, doctype: str | None = None, docname: str | None = None, input=None) -> dict:  # noqa: A002
	"""Run the draft as a test: real during the run, rolled back afterwards, emails captured."""
	from pridict.automation import engine

	doc = _automation(name, "write")
	spec = specs.load(doc.draft_spec or "{}")
	design = [i["message"] for i in specs.validate(spec) if i["level"] == "error"]
	if design:
		frappe.throw(_("Fix these problems before testing:") + "<br>" + "<br>".join(map(frappe.bold, design)))
	trigger = spec.get("trigger") or {}
	config = trigger.get("config") or {}
	event = {
		"trigger.document_event": config.get("event"),
		"trigger.schedule": "schedule",
		"trigger.manual": "manual",
	}.get(trigger.get("type"), "test")
	if docname:
		doctype = doctype or config.get("doctype")
		frappe.get_doc(doctype, docname).check_permission("read")
	elif trigger.get("type") == "trigger.document_event":
		frappe.throw(_("Choose a {0} to test with.").format(_(config.get("doctype") or "document")))
	run = engine.start_run(
		name,
		{
			"event": event,
			"doctype": doctype if docname else None,
			"name": docname,
			"input": frappe.parse_json(input),
		},
		is_test=True,
		requested_by=frappe.session.user,
	)
	return {"run": run}


@frappe.whitelist(methods=["POST"])
def simulate(run: str, node: str, decision: str, note: str = "") -> dict:
	"""Give a waiting test run the decision for a step (approve/reject/expire, an answer, skip)."""
	from pridict.automation import engine

	doc = frappe.get_doc("Agent Run", run)
	_automation(doc.automation, "write")
	pending = frappe.parse_json(doc.pending_json) or {}
	if not doc.is_test or doc.status != "Waiting" or pending.get("node") != node:
		frappe.throw(_("This test run is not waiting at that step."))
	if pending.get("type") == "approval":
		if decision not in ("approved", "rejected", "expired"):
			frappe.throw(_("Choose approved, rejected or expired."))
		value = {"decision": decision, "by": frappe.session.user, "note": note}
	elif pending.get("type") == "ask":
		value = {"answer": decision, "by": frappe.session.user}
	else:
		value = {"waited": True}
	return {"status": engine.simulate(run, node, value)}


@frappe.whitelist(methods=["POST"])
def answer(run: str, answer: str) -> dict:
	"""Answer the question a live run is waiting on (Ask step)."""
	from pridict.automation import engine
	from pridict.automation.nodes.human import can_answer

	doc = frappe.get_doc("Agent Run", run)
	pending = frappe.parse_json(doc.pending_json) or {}
	if not doc.automation or doc.is_test or doc.status != "Waiting" or pending.get("type") != "ask":
		frappe.throw(_("This run is not waiting for an answer."))
	if not can_answer(pending, frappe.session.user):
		frappe.throw(_("This question was asked to someone else."), frappe.PermissionError)
	answer = (answer or "").strip()
	if not answer:
		frappe.throw(_("Type an answer."))
	if pending.get("choices") and answer not in pending["choices"]:
		frappe.throw(_("Choose one of: {0}").format(", ".join(pending["choices"])))
	engine.resume(run, {"answer": answer[:2000], "by": frappe.session.user})
	return {"run": run}


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


@frappe.whitelist()
def list_automations() -> list[dict]:
	"""Rows for the Automations list page, with run counts for the last 24 hours."""
	from frappe.utils import add_to_date, now_datetime

	if not frappe.has_permission("Automation", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	rows = frappe.get_list(
		"Automation",
		fields=[
			"name",
			"title",
			"status",
			"trigger_type",
			"trigger_doctype",
			"trigger_event",
			"trigger_cron",
			"active_version",
			"last_run_at",
			"last_run_status",
			"paused_reason",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=500,
	)
	since = add_to_date(now_datetime(), hours=-24)
	counts = frappe.get_all(
		"Agent Run",
		filters={
			"automation": ["in", [row.name for row in rows] or [""]],
			"creation": [">", since],
			"is_test": 0,
		},
		fields=["automation", "status", "count(*) as runs"],
		group_by="automation, status",
	)
	for row in rows:
		mine = [c for c in counts if c.automation == row.name]
		row.runs_24h = sum(c.runs for c in mine)
		row.failures_24h = sum(c.runs for c in mine if c.status == "Failed")
		row.version = (
			frappe.db.get_value("Automation Version", row.active_version, "version")
			if row.active_version
			else None
		)
	return rows


def _new_spec(title: str, trigger_type: str, trigger_config: dict | None = None) -> dict:
	node_type = catalog.get(trigger_type)
	if not node_type or node_type.category != "trigger":
		frappe.throw(_("Unknown trigger type {0}.").format(trigger_type))
	return {
		"schema": specs.SCHEMA_VERSION,
		"title": title,
		"trigger": {
			"id": "trigger",
			"type": trigger_type,
			"label": node_type.label,
			"config": trigger_config or {},
			"position": [0, 0],
		},
		"nodes": [],
		"edges": [],
		"settings": dict(specs.DEFAULT_SETTINGS),
	}


def _insert(title: str, spec: dict) -> str:
	if not frappe.has_permission("Automation", "create"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	doc = frappe.get_doc(
		{
			"doctype": "Automation",
			"title": title,
			"description": spec.get("description"),
			"draft_spec": json.dumps(spec, indent=1, ensure_ascii=False),
		}
	).insert()
	return doc.name


@frappe.whitelist(methods=["POST"])
def create_automation(title: str, trigger_type: str = "trigger.document_event", trigger_config=None) -> dict:
	title = (title or "").strip()
	if not title:
		frappe.throw(_("Give the automation a title."))
	spec = _new_spec(title, trigger_type, frappe.parse_json(trigger_config) if trigger_config else None)
	return {"name": _insert(title, spec)}


@frappe.whitelist(methods=["POST"])
def duplicate(name: str) -> dict:
	doc = _automation(name)
	spec = specs.load(doc.draft_spec or "{}")
	title = _("{0} (copy)").format(doc.title)
	spec["title"] = title
	return {"name": _insert(title, spec)}


@frappe.whitelist()
def export_spec(name: str) -> dict:
	doc = _automation(name)
	return specs.load(doc.draft_spec or "{}")


@frappe.whitelist(methods=["POST"])
def import_spec(spec) -> dict:
	"""Create a draft from an exported spec. Structure is checked; live checks run on activation."""
	spec = specs.load(frappe.parse_json(spec))
	issues = [i for i in specs.validate(spec) if i["level"] == "error" and "Unsupported spec" in i["message"]]
	if issues or not spec.get("trigger"):
		frappe.throw(_("This file is not an automation export."))
	title = (spec.get("title") or _("Imported automation")).strip()
	return {"name": _insert(title, spec)}


@frappe.whitelist()
def get_references(name: str, node_id: str) -> list[dict]:
	"""Values a step can use in its templates: trigger fields, earlier steps' outputs, variables."""
	doc = _automation(name)
	spec = specs.load(doc.draft_spec or "{}")
	nodes = specs.all_nodes(spec)
	start = specs.trigger_id(spec)
	edges = specs.outgoing(spec)
	reachable = specs._reachable(start, edges)
	before = specs._dominators(start, edges, reachable).get(node_id, set()) - {start}

	refs: list[dict] = []

	def add(group, value, label=None):
		refs.append({"group": group, "value": value, "label": label or value})

	trigger = spec.get("trigger") or {}
	trigger_config = trigger.get("config") or {}
	if trigger.get("type") in ("trigger.document_event", "trigger.manual") and trigger_config.get("doctype"):
		add(_("Trigger"), "trigger.doc.name", _("{0} name").format(trigger_config["doctype"]))
		for value, label in _field_refs("trigger.doc", trigger_config["doctype"]):
			add(_("Trigger"), value, label)
	if trigger.get("type") == "trigger.schedule":
		add(_("Trigger"), "trigger.fired_at")
	if trigger.get("type") == "trigger.manual":
		add(_("Trigger"), "trigger.input")

	order = [n["id"] for n in spec.get("nodes", []) if n["id"] in before]
	for ref_id in order:
		node = nodes[ref_id]
		config = node.get("config") or {}
		group = node.get("label") or ref_id
		node_type = node.get("type")
		if node_type in (
			"data.get_document",
			"action.create_document",
			"action.update_document",
			"action.submit_document",
		):
			doctype = config.get("doctype")
			add(group, f"nodes.{ref_id}.doc.name")
			if doctype and not str(doctype).startswith("{"):
				for value, label in _field_refs(f"nodes.{ref_id}.doc", doctype):
					add(group, value, label)
		elif node_type in ("data.find_documents", "data.aggregate", "data.run_report"):
			add(group, f"nodes.{ref_id}.rows")
			add(
				group,
				f"nodes.{ref_id}.count" if node_type == "data.find_documents" else f"nodes.{ref_id}.value",
			)
		elif node_type == "logic.loop":
			add(group, f"nodes.{ref_id}.item")
			add(group, f"nodes.{ref_id}.index")
			source = expressions.references(config.get("items"))
			for src in source:
				for field in (nodes.get(src, {}).get("config") or {}).get("fields") or []:
					add(group, f"nodes.{ref_id}.item.{field}")
		elif node_type == "logic.set_variable" and config.get("name"):
			add(_("Variables"), f"vars.{config['name']}")
		else:
			for output in catalog.get(node_type).outputs if catalog.get(node_type) else ():
				add(group, f"nodes.{ref_id}.{output}")
	add(_("Run"), "today")
	add(_("Run"), "now")
	add(_("Run"), "run.name")
	return refs


def _field_refs(prefix: str, doctype: str) -> list[tuple[str, str]]:
	if not frappe.db.exists("DocType", doctype):
		return []
	from frappe.model import no_value_fields

	out = []
	for field in frappe.get_meta(doctype).fields:
		if field.fieldtype in no_value_fields and field.fieldtype != "Table":
			continue
		key = (
			f"{prefix}['{field.fieldname}']"
			if field.fieldname in ("items", "values", "keys")
			else f"{prefix}.{field.fieldname}"
		)
		out.append((key, f"{field.label or field.fieldname} ({field.fieldname})"))
	return out


def _announce(doc):
	# Payload carries no spec; open editors re-fetch through get_builder.
	frappe.publish_realtime(
		UPDATE_EVENT,
		{"automation": doc.name, "revision": doc.draft_revision, "status": doc.status},
		doctype="Automation",
		docname=doc.name,
		after_commit=True,
	)


def passing_test(automation: str, spec_hash: str) -> str | None:
	from pridict.pridict.doctype.automation.automation import passing_test as find

	return find(automation, spec_hash)


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
		"pending": frappe.parse_json(doc.pending_json) if doc.pending_json else None,
		"spec_hash": doc.spec_hash,
		"approval": frappe.db.get_value("Agent Approval", {"run": doc.name, "status": "Pending"}, "name"),
		"steps": steps,
	}
