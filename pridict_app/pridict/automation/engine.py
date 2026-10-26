"""Automation engine: compiles a spec into a LangGraph graph and runs it as an Agent Run.

A run executes as the automation's Run As user, without ignore_permissions. Each node
runs inside the Agent Studio RunContext, so it records an Agent Run Step (with node_id),
commits its own work and announces progress over realtime (agent_run_update), which the
canvas uses to colour nodes. Live runs use the automation's active version; test runs
use the draft.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

import frappe
from frappe import _
from frappe.utils import now_datetime, time_diff_in_seconds

from pridict.agent_studio import runtime
from pridict.agent_studio.checkpointer import MariaDBSaver
from pridict.automation import expressions, guards
from pridict.automation import nodes as catalog
from pridict.automation import spec as specs

QUEUE = "automation"
FALLBACK_QUEUE = "long"
MAX_RUNTIME_S = 600

# Agent Run Step.node_kind has fixed options; map node categories onto them.
STEP_KIND = {"data": "tool", "logic": "router", "action": "tool", "human": "human", "ai": "llm"}


def _merge(left: dict, right: dict) -> dict:
	"""Reducer for dict channels: later values win; None removes a key."""
	merged = dict(left or {})
	for key, value in (right or {}).items():
		if value is None:
			merged.pop(key, None)
		else:
			merged[key] = value
	return merged


class State(TypedDict, total=False):
	trigger: dict
	run: dict
	nodes: Annotated[dict, operator.or_]
	vars: Annotated[dict, operator.or_]
	loops: Annotated[dict, _merge]
	route: str | None
	stop: dict | None


def compile_spec(spec: dict, checkpointer=None):
	"""Turn a valid spec into a compiled LangGraph graph."""
	from langgraph.graph import END, START, StateGraph

	issues = specs.validate(spec)
	if specs.has_errors(issues):
		raise ValueError(
			_("The automation has errors: {0}").format(
				"; ".join(issue["message"] for issue in issues if issue["level"] == "error")
			)
		)

	edges = specs.outgoing(spec)
	on_error = spec["settings"]["on_error"]
	graph = StateGraph(State)

	def target(node_id: str):
		return END if node_id == specs.END else node_id

	for node in spec["nodes"]:
		graph.add_node(node["id"], _wrap(node, on_error))

	graph.add_edge(START, target(edges[specs.trigger_id(spec)][0]["to"]))
	for node in spec["nodes"]:
		node_type = catalog.get(node["type"])
		out = edges[node["id"]]
		if node_type.terminal:
			graph.add_edge(node["id"], END)
		elif node_type.branch_names(node.get("config") or {}):
			mapping = {edge["branch"]: target(edge["to"]) for edge in out}
			graph.add_conditional_edges(node["id"], _route, mapping)
		else:
			graph.add_edge(node["id"], target(out[0]["to"]))
	return graph.compile(checkpointer=checkpointer)


def _route(state: dict) -> str:
	return state["route"]


def _wrap(node: dict, on_error: str):
	node_type = catalog.get(node["type"])
	kind = STEP_KIND.get(node_type.category, "tool")
	branching = bool(node_type.branch_names(node.get("config") or {}))
	label = node.get("label") or node["id"]

	def run_node(state: dict) -> dict:
		ctx = runtime.current()
		ctx.check_runtime()
		ctx.begin_step()
		scope = expressions.scope_from_state(state) | {"node": {"id": node["id"]}}
		try:
			result = node_type.execute(ctx, node.get("config") or {}, scope)
			output = expressions.cap(expressions.to_data(result.output))
		except Exception as error:
			ctx.end_step(node["id"], kind, "Failed", f"{label}: {error}")
			if on_error == "continue" and not branching and not isinstance(error, guards.GuardError):
				# The failure is on the trace; carry on with the next step.
				return {"nodes": {node["id"]: {"error": str(error)[:2000]}}, "route": None}
			raise
		# The step keeps the branch taken so the canvas can draw the path.
		ctx.note(result.summary or label, {"output": output, "route": result.route})
		ctx.end_step(node["id"], kind, "Completed")
		update = {"nodes": {node["id"]: output}, "route": result.route}
		if result.vars:
			update["vars"] = expressions.to_data(result.vars)
		if result.loops:
			update["loops"] = expressions.to_data(result.loops)
		if result.stop:
			update["stop"] = result.stop
		return update

	return run_node


# ---------------------------------------------------------------------------
# Starting and executing runs


def queue() -> str:
	"""The dedicated automation queue when a worker serves it, else the long queue."""
	return QUEUE if QUEUE in (frappe.conf.get("workers") or {}) else FALLBACK_QUEUE


def start_run(
	automation: str,
	trigger: dict,
	*,
	chain: list[str] | None = None,
	is_test: bool = False,
	now: bool = False,
	requested_by: str | None = None,
) -> str:
	"""Create a Queued Agent Run for an automation and enqueue it after the current commit.

	trigger: {"event", "doctype"?, "name"?, "fired_at"?, "input"?}; a trigger document is
	loaded fresh when the run starts. Live runs use the active version, test runs the draft.
	"""
	automation_doc = frappe.get_doc("Automation", automation)
	version = None if is_test else automation_doc.active_version
	if not is_test and not version:
		frappe.throw(_("Automation {0} has no active version.").format(automation_doc.title))
	run = frappe.get_doc(
		{
			"doctype": "Agent Run",
			"automation": automation,
			"automation_version": version,
			"status": "Queued",
			"requested_by": requested_by or automation_doc.run_as,
			"request": _("{0}: {1}").format(automation_doc.title, _describe(trigger))[:4000],
			"trigger_doctype": trigger.get("doctype"),
			"trigger_name": trigger.get("name"),
			"trigger_event": trigger.get("event"),
			"is_test": 1 if is_test else 0,
			"result_json": runtime._json(
				{"chain": chain or [], "fired_at": trigger.get("fired_at"), "input": trigger.get("input")}
			),
		}
	)
	run.insert(ignore_permissions=True)
	run.db_set("thread_id", run.name, update_modified=False)
	if now:
		execute(run.name)
	else:
		frappe.enqueue(
			"pridict.automation.engine.execute",
			queue=queue(),
			timeout=MAX_RUNTIME_S + 300,
			job_id=f"automation-run::{run.name}",
			deduplicate=True,
			enqueue_after_commit=True,
			run=run.name,
		)
	return run.name


def _describe(trigger: dict) -> str:
	if trigger.get("doctype") and trigger.get("name"):
		return f"{trigger['doctype']} {trigger['name']} ({trigger.get('event')})"
	return str(trigger.get("event") or "")


def _trigger_state(run, extra: dict) -> dict:
	trigger = {"event": run.trigger_event, "doctype": run.trigger_doctype, "name": run.trigger_name}
	if extra.get("fired_at"):
		trigger["fired_at"] = extra["fired_at"]
	if extra.get("input") is not None:
		trigger["input"] = extra["input"]
	if run.trigger_doctype and run.trigger_name:
		if run.trigger_event == "on_trash":
			trigger["doc"] = {"doctype": run.trigger_doctype, "name": run.trigger_name}
		else:
			trigger["doc"] = frappe.get_doc(run.trigger_doctype, run.trigger_name).as_dict()
	return expressions.to_data(trigger)


def _spec_for(doc, automation) -> dict:
	if doc.automation_version:
		return specs.load(frappe.db.get_value("Automation Version", doc.automation_version, "spec"))
	return specs.load(automation.draft_spec or "{}")


def execute(run: str) -> str:
	"""Run an automation run to the end. Safe to call from a worker."""
	doc = frappe.get_doc("Agent Run", run)
	if doc.status in runtime.FINISHED:
		return doc.status
	automation = frappe.get_doc("Automation", doc.automation)
	if not doc.is_test and not guards.enabled():
		return _cancel(doc, _("Automations are switched off on this site."))
	if not doc.is_test and automation.status != "Active":
		return _cancel(doc, _("The automation is {0}.").format(_(automation.status).lower()))

	spec = _spec_for(doc, automation)
	extra = frappe.parse_json(doc.result_json) or {}
	chain = extra.get("chain") or []
	checkpoints = specs.needs_checkpoints(spec)

	previous_user = frappe.session.user
	previous_chain = frappe.flags.automation_chain
	frappe.set_user(automation.run_as)
	# Saves made by this run carry the chain, so triggers can stop loops (see triggers.py).
	frappe.flags.automation_chain = [*chain, automation.name]
	ctx = runtime.RunContext(
		run=run,
		agent=None,
		requested_by=automation.run_as,
		max_llm_calls=0,
		token_budget=0,
		max_runtime_s=MAX_RUNTIME_S,
		step_index=len(doc.steps),
		saver=MariaDBSaver() if checkpoints else None,
	)
	token = runtime._current.set(ctx)
	values = {"status": "Running"}
	if not doc.started_at:
		values["started_at"] = now_datetime()
	doc.db_set(values, update_modified=False)
	runtime._commit()
	runtime._publish(run, "Running")
	try:
		graph = compile_spec(spec, ctx.saver)
		config = {
			"configurable": {"thread_id": doc.thread_id or run},
			"recursion_limit": spec["settings"]["max_steps"] + 1,
		}
		state = {
			"trigger": _trigger_state(doc, extra),
			"run": {
				"name": run,
				"is_test": bool(doc.is_test),
				"automation": automation.name,
				"title": automation.title,
			},
			"nodes": {},
			"vars": {},
			"loops": {},
		}
		final = {}
		for update in graph.stream(state, config, stream_mode="values", **_durability(checkpoints)):
			final = update
		if ctx.saver:
			ctx.saver.flush()
			if graph.get_state(config).interrupts:
				# Approval, Ask and Wait nodes arrive in Phase 4.
				raise RuntimeError(_("This automation paused, but pausing is not supported yet."))
		status = _finish(doc, automation, final)
	except Exception as error:
		status = _fail(doc, automation, ctx, error)
	finally:
		runtime._current.reset(token)
		frappe.flags.automation_chain = previous_chain
		frappe.set_user(previous_user)
	runtime._commit()
	runtime._publish(run, status)
	return status


def _durability(checkpoints: bool) -> dict:
	# durability="sync": save each checkpoint before the next step. The default saves in a
	# background thread, which would share this job's single database connection.
	return {"durability": "sync"} if checkpoints else {}


def _finish(doc, automation, values: dict) -> str:
	stop = values.get("stop") or {}
	status = "Failed" if stop.get("status") == "Failed" else "Completed"
	started = frappe.db.get_value("Agent Run", doc.name, "started_at")
	steps = len(values.get("nodes") or {})
	frappe.db.set_value(
		"Agent Run",
		doc.name,
		{
			"status": status,
			"outcome": stop.get("message") or _("Finished after {0} steps.").format(steps),
			"error": stop.get("message") if status == "Failed" else None,
			"ended_at": now_datetime(),
			"duration_s": time_diff_in_seconds(now_datetime(), started) if started else 0,
			"result_json": runtime._json(
				{"nodes": values.get("nodes") or {}, "vars": values.get("vars") or {}}
			),
		},
		update_modified=False,
	)
	if specs.needs_checkpoints(_spec_for(doc, automation)):
		MariaDBSaver().delete_thread(doc.thread_id or doc.name)
	if not doc.is_test:
		guards.record_result(automation.name, status, stop.get("message"))
	return status


def _fail(doc, automation, ctx, error: Exception) -> str:
	if not runtime.sandboxed():
		frappe.db.rollback()
	if not isinstance(error, guards.GuardError | frappe.PermissionError | frappe.ValidationError):
		frappe.log_error(
			title=f"Automation run {doc.name} failed", reference_doctype="Agent Run", reference_name=doc.name
		)
	frappe.db.set_value(
		"Agent Run",
		doc.name,
		{"status": "Failed", "error": str(error)[:2000], "ended_at": now_datetime()},
		update_modified=False,
	)
	if ctx.saver:
		ctx.saver.discard()
		ctx.saver.delete_thread(doc.thread_id or doc.name)
	if not doc.is_test:
		paused = guards.record_result(automation.name, "Failed", str(error))
		if not paused and _spec_for(doc, automation)["settings"]["on_error"] == "stop_and_notify":
			guards.notify_owner(
				automation.name,
				_("Automation {0} failed (run {1}): {2}").format(
					automation.title, doc.name, str(error)[:300]
				),
			)
	return "Failed"


def _cancel(doc, reason: str) -> str:
	frappe.db.set_value(
		"Agent Run",
		doc.name,
		{"status": "Cancelled", "outcome": reason, "ended_at": now_datetime()},
		update_modified=False,
	)
	runtime._commit()
	runtime._publish(doc.name, "Cancelled")
	return "Cancelled"
