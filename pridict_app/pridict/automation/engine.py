"""Automation engine: compiles a spec into a LangGraph graph and runs it as an Agent Run.

A run executes as the automation's Run As user, without ignore_permissions. Each node
runs inside the Agent Studio RunContext, so it records an Agent Run Step (with node_id),
commits its own work and announces progress over realtime (agent_run_update), which the
canvas uses to colour nodes.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

import frappe
from frappe import _
from frappe.utils import now_datetime, time_diff_in_seconds

from pridict.agent_studio import runtime
from pridict.agent_studio.checkpointer import MariaDBSaver
from pridict.automation import expressions
from pridict.automation import nodes as catalog
from pridict.automation import spec as specs

QUEUE = "long"  # Phase 1 moves runs to a dedicated "automation" queue and worker.
MAX_RUNTIME_S = 300
MAX_CHAIN_DEPTH = 3

# Agent Run Step.node_kind has fixed options; map node categories onto them.
STEP_KIND = {"data": "tool", "logic": "router", "action": "tool", "human": "human", "ai": "llm"}


class State(TypedDict, total=False):
	trigger: dict
	run: dict
	nodes: Annotated[dict, operator.or_]
	vars: Annotated[dict, operator.or_]
	route: str | None


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

	trigger_id = spec["trigger"].get("id") or "trigger"
	edges = specs.outgoing(spec)
	graph = StateGraph(State)

	def target(node_id: str):
		return END if node_id == specs.END else node_id

	for node in spec["nodes"]:
		graph.add_node(node["id"], _wrap(node))

	first = edges[trigger_id][0]["to"]
	graph.add_edge(START, target(first))
	for node in spec["nodes"]:
		out = edges[node["id"]]
		if catalog.get(node["type"]).branches:
			mapping = {edge["branch"]: target(edge["to"]) for edge in out}
			graph.add_conditional_edges(node["id"], _route, mapping)
		else:
			graph.add_edge(node["id"], target(out[0]["to"]))
	return graph.compile(checkpointer=checkpointer)


def _route(state: dict) -> str:
	return state["route"]


def _wrap(node: dict):
	node_type = catalog.get(node["type"])
	kind = STEP_KIND.get(node_type.category, "tool")

	def run_node(state: dict) -> dict:
		ctx = runtime.current()
		ctx.check_runtime()
		ctx.begin_step()
		try:
			result = node_type.execute(ctx, node.get("config") or {}, expressions.scope_from_state(state))
			output = expressions.to_data(result.output)
		except Exception as error:
			ctx.end_step(node["id"], kind, "Failed", f"{node.get('label') or node['id']}: {error}")
			raise
		# The step keeps the branch taken so the canvas can draw the path.
		ctx.note(result.summary or node.get("label") or node["id"], {"output": output, "route": result.route})
		ctx.end_step(node["id"], kind, "Completed")
		return {"nodes": {node["id"]: output}, "route": result.route}

	return run_node


# ---------------------------------------------------------------------------
# Starting and executing runs


def start_run(
	automation: str,
	trigger: dict,
	*,
	chain: list[str] | None = None,
	is_test: bool = False,
	now: bool = False,
) -> str:
	"""Create a Queued Agent Run for an automation and enqueue it after the current commit.

	trigger: {"event", "doctype", "name"}; the document is loaded fresh when the run starts.
	"""
	automation_doc = frappe.get_doc("Automation", automation)
	run = frappe.get_doc(
		{
			"doctype": "Agent Run",
			"automation": automation,
			"status": "Queued",
			"requested_by": automation_doc.run_as,
			"request": _("{0}: {1} {2} ({3})").format(
				automation_doc.title, trigger.get("doctype"), trigger.get("name"), trigger.get("event")
			)[:4000],
			"trigger_doctype": trigger.get("doctype"),
			"trigger_name": trigger.get("name"),
			"trigger_event": trigger.get("event"),
			"is_test": 1 if is_test else 0,
			"result_json": runtime._json({"chain": chain or []}),
		}
	)
	run.insert(ignore_permissions=True)
	run.db_set("thread_id", run.name, update_modified=False)
	if now:
		execute(run.name)
	else:
		frappe.enqueue(
			"pridict.automation.engine.execute",
			queue=QUEUE,
			timeout=MAX_RUNTIME_S + 300,
			job_id=f"automation-run::{run.name}",
			deduplicate=True,
			enqueue_after_commit=True,
			run=run.name,
		)
	return run.name


def _trigger_state(run) -> dict:
	trigger = {"event": run.trigger_event, "doctype": run.trigger_doctype, "name": run.trigger_name}
	if run.trigger_doctype and run.trigger_name:
		if run.trigger_event == "on_trash":
			trigger["doc"] = {"doctype": run.trigger_doctype, "name": run.trigger_name}
		else:
			trigger["doc"] = frappe.get_doc(run.trigger_doctype, run.trigger_name).as_dict()
	return expressions.to_data(trigger)


def execute(run: str) -> str:
	"""Run an automation run to the end. Safe to call from a worker."""
	doc = frappe.get_doc("Agent Run", run)
	if doc.status in runtime.FINISHED:
		return doc.status
	automation = frappe.get_doc("Automation", doc.automation)
	spec = specs.load(automation.draft_spec)
	chain = (frappe.parse_json(doc.result_json) or {}).get("chain") or []

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
		saver=MariaDBSaver(),
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
			"trigger": _trigger_state(doc),
			"run": {"name": run, "is_test": bool(doc.is_test), "automation": automation.name},
			"nodes": {},
			"vars": {},
		}
		for _update in graph.stream(state, config, stream_mode="updates", durability="sync"):
			pass
		ctx.saver.flush()
		snapshot = graph.get_state(config)
		if snapshot.interrupts:
			# Approval, Ask and Wait nodes arrive in Phase 4.
			raise RuntimeError(_("This automation paused, but pausing is not supported yet."))
		status = _finish(doc, automation, snapshot.values)
	except Exception as error:
		status = "Failed"
		if not runtime.sandboxed():
			frappe.db.rollback()
		frappe.log_error(
			title=f"Automation run {run} failed", reference_doctype="Agent Run", reference_name=run
		)
		frappe.db.set_value(
			"Agent Run",
			run,
			{"status": "Failed", "error": str(error)[:2000], "ended_at": now_datetime()},
			update_modified=False,
		)
		ctx.saver.discard()
		ctx.saver.delete_thread(doc.thread_id or run)
		_record_last_run(automation.name, "Failed")
	finally:
		runtime._current.reset(token)
		frappe.flags.automation_chain = previous_chain
		frappe.set_user(previous_user)
	runtime._commit()
	runtime._publish(run, status)
	return status


def _finish(doc, automation, values: dict) -> str:
	started = frappe.db.get_value("Agent Run", doc.name, "started_at")
	steps = len(values.get("nodes") or {})
	frappe.db.set_value(
		"Agent Run",
		doc.name,
		{
			"status": "Completed",
			"outcome": _("Finished after {0} steps.").format(steps),
			"ended_at": now_datetime(),
			"duration_s": time_diff_in_seconds(now_datetime(), started) if started else 0,
			"result_json": runtime._json(
				{"nodes": values.get("nodes") or {}, "vars": values.get("vars") or {}}
			),
		},
		update_modified=False,
	)
	MariaDBSaver().delete_thread(doc.thread_id or doc.name)
	_record_last_run(automation.name, "Completed")
	return "Completed"


def _record_last_run(automation: str, status: str):
	frappe.db.set_value(
		"Automation",
		automation,
		{"last_run_at": now_datetime(), "last_run_status": status},
		update_modified=False,
	)
