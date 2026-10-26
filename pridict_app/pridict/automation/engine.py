"""Automation engine: compiles a spec into a LangGraph graph and runs it as an Agent Run.

A run executes as the automation's Run As user, without ignore_permissions. Each node
runs inside the Agent Studio RunContext, so it records an Agent Run Step (with node_id),
commits its own work and announces progress over realtime (agent_run_update), which the
canvas uses to colour nodes. Live runs use the automation's active version; test runs
use the draft.
"""

from __future__ import annotations

import json
import operator
from typing import Annotated, TypedDict

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime, time_diff_in_seconds
from langgraph.errors import GraphInterrupt

from pridict.agent_studio import runtime
from pridict.agent_studio.checkpointer import MariaDBSaver
from pridict.automation import expressions, guards
from pridict.automation import nodes as catalog
from pridict.automation import spec as specs
from pridict.automation.nodes.human import SimulationNeeded

TEST_SAVEPOINT = "automation_test_run"

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
		except (GraphInterrupt, SimulationNeeded):
			# The step waits (live) or needs a simulated decision (test); not a failure.
			ctx.end_step(node["id"], kind, "Interrupted", f"{label}: waiting")
			raise
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
	if run.trigger_event == "inbound_email" and trigger.get("doc"):
		trigger["email"] = _email(trigger["doc"])
	if run.trigger_event == "webhook":
		trigger["body"] = (extra.get("input") or {}).get("body")
		trigger["headers"] = (extra.get("input") or {}).get("headers") or {}
	return expressions.to_data(trigger)


def _email(communication: dict) -> dict:
	"""The parts of a received email that steps use (trigger.email)."""
	from frappe.utils import strip_html

	files = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Communication", "attached_to_name": communication.get("name")},
		fields=["file_name", "file_url"],
	)
	return {
		"from": communication.get("sender"),
		"from_name": communication.get("sender_full_name"),
		"subject": communication.get("subject"),
		"body": communication.get("text_content") or strip_html(communication.get("content") or ""),
		"attachments": files,
	}


def _spec_for(doc, automation) -> dict:
	if doc.automation_version:
		return specs.load(frappe.db.get_value("Automation Version", doc.automation_version, "spec"))
	return specs.load(automation.draft_spec or "{}")


def _state(doc, automation, extra: dict, decisions: dict | None = None) -> dict:
	run = {
		"name": doc.name,
		"is_test": bool(doc.is_test),
		"automation": automation.name,
		"title": automation.title,
	}
	if decisions is not None:
		run["decisions"] = decisions
	return {"trigger": _trigger_state(doc, extra), "run": run, "nodes": {}, "vars": {}, "loops": {}}


def execute(run: str, resume=None) -> str:
	"""Run (or resume) an automation run until it ends or waits. Safe to call from a worker."""
	from langgraph.types import Command

	doc = frappe.get_doc("Agent Run", run)
	if doc.status in runtime.FINISHED:
		return doc.status
	automation = frappe.get_doc("Automation", doc.automation)
	if doc.is_test:
		return _execute_test(doc, automation)
	if not guards.enabled():
		return _cancel(doc, _("Automations are switched off on this site."))
	if automation.status != "Active":
		return _cancel(doc, _("The automation is {0}.").format(_(automation.status).lower()))

	spec = _spec_for(doc, automation)
	extra = frappe.parse_json(doc.result_json) or {}
	checkpoints = specs.needs_checkpoints(spec)
	previous_user, previous_chain = frappe.session.user, frappe.flags.automation_chain
	frappe.set_user(automation.run_as)
	# Saves made by this run carry the chain, so triggers can stop loops (see triggers.py).
	frappe.flags.automation_chain = [*(extra.get("chain") or []), automation.name]
	ctx = _context(doc, automation, MariaDBSaver() if checkpoints else None)
	token = runtime._current.set(ctx)
	values = {"status": "Running", "pending_question": None, "pending_json": None, "resume_at": None}
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
		payload = Command(resume=resume) if resume is not None else _state(doc, automation, extra)
		final = {}
		for update in graph.stream(payload, config, stream_mode="values", **_durability(checkpoints)):
			final = update
		snapshot = None
		if ctx.saver:
			ctx.saver.flush()
			snapshot = graph.get_state(config)
		if snapshot and snapshot.interrupts:
			status = _pause(doc, automation, snapshot.interrupts[0].value or {})
		else:
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


def _context(doc, automation, saver=None, step_index=None):
	return runtime.RunContext(
		run=doc.name,
		agent=None,
		requested_by=automation.run_as,
		max_llm_calls=0,
		token_budget=0,
		max_runtime_s=MAX_RUNTIME_S,
		step_index=len(doc.steps) if step_index is None else step_index,
		saver=saver,
	)


def _pause(doc, automation, pause: dict) -> str:
	"""Record what a live run waits for: an approval, an answer, or a time."""
	kind = pause.get("type")
	status = "Awaiting approval" if kind == "approval" else "Waiting"
	resume_at = None
	if kind == "wait":
		resume_at = pause.get("resume_at")
	elif kind == "approval":
		if pause.get("timeout_hours"):
			resume_at = add_to_date(now_datetime(), hours=int(pause["timeout_hours"]))
		pause["approval"] = _create_approval(doc, pause)
	elif kind == "ask":
		_notify_ask(doc, automation, pause)
	frappe.db.set_value(
		"Agent Run",
		doc.name,
		{
			"status": status,
			"pending_question": pause.get("message") or "",
			"pending_json": runtime._json(pause),
			"resume_at": resume_at,
		},
		update_modified=False,
	)
	return status


def _create_approval(doc, pause: dict) -> str:
	from pridict.agent_studio import approvals

	approval = frappe.get_doc(
		{
			"doctype": "Agent Approval",
			"run": doc.name,
			"requested_by": doc.requested_by,
			"status": "Pending",
			"action": f"automation:{pause.get('node')}",
			"required_roles": json.dumps(pause.get("roles") or []),
			"required_approvals": len(pause.get("roles") or []) or 1,
			"summary": (pause.get("message") or "")[:1000],
			"proposal_json": runtime._json(pause),
		}
	).insert(ignore_permissions=True)
	approvals.notify_approvers(approval)
	return approval.name


def _notify_ask(doc, automation, pause: dict):
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	emails = frappe.get_all(
		"User", filters={"name": ["in", pause.get("users") or [""]], "enabled": 1}, pluck="email"
	)
	if emails:
		enqueue_create_notification(
			emails,
			{
				"type": "Alert",
				"subject": _("{0} asks: {1}").format(automation.title, pause.get("question") or "")[:140],
				"email_content": pause.get("question"),
				"document_type": "Agent Run",
				"document_name": doc.name,
				"from_user": guards.settings().default_run_as or "Administrator",
			},
		)


def resume(run: str, value: dict):
	"""Continue a paused live run with a decision, an answer, or after a wait."""
	frappe.db.set_value(
		"Agent Run",
		run,
		{"status": "Queued", "pending_question": None, "pending_json": None, "resume_at": None},
		update_modified=False,
	)
	if frappe.flags.in_test:
		execute(run, value)
		return
	frappe.enqueue(
		"pridict.automation.engine.execute",
		queue=queue(),
		timeout=MAX_RUNTIME_S + 300,
		job_id=f"automation-run::{run}",
		deduplicate=True,
		enqueue_after_commit=True,
		run=run,
		resume=value,
	)


# ---------------------------------------------------------------------------
# Test runs


STEP_FIELDS = [
	"name",
	"idx",
	"node_id",
	"node_kind",
	"status",
	"started_at",
	"duration_ms",
	"tokens",
	"tool_calls",
	"summary",
	"input_json",
	"output_json",
]


def _execute_test(doc, automation) -> str:
	"""Run the draft for real inside a savepoint, then roll everything back.

	Documents, comments and assignments exist during the run and are gone afterwards; emails
	are captured by the email step. Waiting steps use the decisions simulated so far; the first
	one without a decision stops the test so the builder can offer Simulate buttons. Every
	attempt replays from the start, so nothing has to stay open between clicks.
	"""
	run = doc.name
	spec = specs.load(automation.draft_spec or "{}")
	extra = frappe.parse_json(doc.result_json) or {}
	decisions = extra.get("decisions") or {}
	frappe.db.delete("Agent Run Step", {"parent": run, "parenttype": "Agent Run"})
	started = now_datetime()
	doc.db_set(
		{
			"status": "Running",
			"started_at": started,
			"error": None,
			"pending_question": None,
			"pending_json": None,
		},
		update_modified=False,
	)
	runtime._commit()
	runtime._publish(run, "Running")

	real_commit = frappe.db.commit
	blocked = []
	callbacks = (len(frappe.db.before_commit._functions), len(frappe.db.after_commit._functions))
	previous_user, previous_eval = frappe.session.user, frappe.flags.agent_eval
	outcome: dict = {}
	frappe.db.savepoint(TEST_SAVEPOINT)
	# Nothing in a test may save for good: block commits (Frappe internals included).
	frappe.db.commit = lambda *args, **kwargs: blocked.append(1)
	frappe.flags.agent_eval = True  # our own per-step commits become no-ops
	frappe.flags.automation_test_run = True  # saves in the test do not start other automations
	frappe.set_user(automation.run_as)
	ctx = _context(doc, automation, None, step_index=0)
	token = runtime._current.set(ctx)
	try:
		graph = compile_spec(spec)
		config = {"configurable": {"thread_id": run}, "recursion_limit": spec["settings"]["max_steps"] + 1}
		final = {}
		for update in graph.stream(_state(doc, automation, extra, decisions), config, stream_mode="values"):
			final = update
		stop = final.get("stop") or {}
		outcome = {
			"status": "Failed" if stop.get("status") == "Failed" else "Completed",
			"message": stop.get("message"),
			"values": final,
		}
	except SimulationNeeded as waiting:
		outcome = {"status": "Waiting", "pause": {**waiting.pause, "simulate": True}}
	except Exception as error:
		outcome = {"status": "Failed", "error": str(error)}
	finally:
		steps = frappe.get_all(
			"Agent Run Step",
			filters={"parent": run, "parenttype": "Agent Run"},
			fields=STEP_FIELDS,
			order_by="idx",
		)
		frappe.db.rollback(save_point=TEST_SAVEPOINT)
		# Jobs and realtime messages queued during the test must not fire on the next commit.
		for queue_, keep in zip((frappe.db.before_commit, frappe.db.after_commit), callbacks, strict=True):
			while len(queue_._functions) > keep:
				queue_._functions.pop()
		frappe.db.commit = real_commit
		frappe.flags.agent_eval = previous_eval
		frappe.flags.automation_test_run = False
		runtime._current.reset(token)
		frappe.set_user(previous_user)

	for row in steps:
		step = frappe.new_doc("Agent Run Step")
		step.update({**row, "parent": run, "parenttype": "Agent Run", "parentfield": "steps"})
		step.db_insert()
	values = outcome.get("values") or {}
	result = {
		**{k: extra.get(k) for k in ("decisions", "input", "chain") if extra.get(k) is not None},
		"nodes": values.get("nodes") or {},
		"vars": values.get("vars") or {},
		"blocked_commits": len(blocked),
	}
	status = outcome["status"]
	pause = outcome.get("pause")
	frappe.db.set_value(
		"Agent Run",
		run,
		{
			"status": status,
			"spec_hash": specs.spec_hash(spec),
			"ended_at": None if status == "Waiting" else now_datetime(),
			"duration_s": time_diff_in_seconds(now_datetime(), started),
			"error": outcome.get("error") or (outcome.get("message") if status == "Failed" else None),
			"outcome": _test_outcome(status, outcome, len(blocked)),
			"pending_question": (pause or {}).get("message"),
			"pending_json": runtime._json(pause) if pause else None,
			"result_json": runtime._json(result),
		},
		update_modified=False,
	)
	runtime._commit()
	runtime._publish(run, status)
	return status


def _test_outcome(status: str, outcome: dict, blocked: int) -> str:
	text = {
		"Completed": _("Test passed. Everything it changed was rolled back."),
		"Waiting": _("Waiting at a step that needs a decision. Simulate one to continue."),
		"Failed": _("Test failed. Everything it changed was rolled back."),
	}[status]
	if outcome.get("message"):
		text += " " + outcome["message"]
	if blocked:
		text += " " + _(
			"Something tried to save permanently {0} time(s) during the test; it was blocked."
		).format(blocked)
	return text


def simulate(run: str, node: str, decision) -> str:
	"""Record a simulated decision for a waiting test run and replay it."""
	doc = frappe.get_doc("Agent Run", run)
	extra = frappe.parse_json(doc.result_json) or {}
	extra.setdefault("decisions", {})[node] = decision
	doc.db_set({"status": "Queued", "result_json": runtime._json(extra)}, update_modified=False)
	if frappe.flags.in_test:
		return execute(run)
	frappe.enqueue(
		"pridict.automation.engine.execute",
		queue=queue(),
		timeout=MAX_RUNTIME_S + 300,
		job_id=f"automation-run::{run}",
		deduplicate=True,
		enqueue_after_commit=True,
		run=run,
	)
	return "Queued"


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
