"""Agent Studio runtime: compiles workflow graphs and executes runs as background jobs.

A run is one Agent Run document. execute() loads the agent, compiles its workflow
from registry.WORKFLOWS with node functions from the workflow's module, and streams
the LangGraph graph with the MariaDB checkpointer (thread_id = run name). Each node
executes inside a RunContext that enforces the agent's limits, records an Agent Run
Step, commits, and announces progress over realtime.

Human pauses use LangGraph interrupts. The interrupt payload decides the run status
("question" -> Waiting for buyer, "approval" -> Awaiting approval); resume_run()
continues from the checkpoint with the person's answer or decision.

Each run is also a conversation: post_message() appends Agent Chat Message rows that
the Procurement Assistant page shows to the buyer. Steps are for administrators;
messages are the only thing the buyer sees.
"""

from __future__ import annotations

import contextvars
import json
import time
from dataclasses import dataclass, field
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime, time_diff_in_seconds

from pridict.agent_studio import gateway, registry, tools
from pridict.agent_studio.checkpointer import MariaDBSaver

RUN_EVENT = "agent_run_update"
RECURSION_LIMIT = 80
STARTER_ROLES = {"System Manager", "Purchase Manager", "Purchase User"}
MAX_ACTIVE_RUNS_PER_USER = 3
WAITING = ("Waiting for buyer", "Awaiting approval")
FINISHED = ("Completed", "Failed", "Rejected", "Cancelled")

# Which module implements the nodes of each workflow.
WORKFLOW_MODULES = {registry.PROCUREMENT_WORKFLOW: "pridict.agent_studio.procurement"}

_current: contextvars.ContextVar[RunContext | None] = contextvars.ContextVar(
	"agent_run_context", default=None
)


class BudgetExceeded(Exception):
	pass


def _json(value) -> str:
	return json.dumps(value, indent=1, default=str, ensure_ascii=False)


def sandboxed() -> bool:
	"""Tests and evaluations run inside one transaction that is rolled back afterwards."""
	return bool(frappe.flags.in_test or frappe.flags.agent_eval)


def _commit():
	if not sandboxed():
		frappe.db.commit()


def post_message(
	run: str,
	role: str,
	content: str,
	kind: str = "text",
	card: dict | None = None,
	choices: list[str] | None = None,
	parenttype: str = "Agent Run",
):
	"""Append one chat message to a run or an Assistant Conversation (bypasses document save)."""
	idx = frappe.db.count("Agent Chat Message", {"parent": run, "parenttype": parenttype}) + 1
	message = frappe.new_doc("Agent Chat Message")
	message.update(
		{
			"parent": run,
			"parenttype": parenttype,
			"parentfield": "messages",
			"idx": idx,
			"role": role,
			"kind": kind,
			"posted_at": now_datetime(),
			"content": content or "",
			"card_json": _json(card) if card else None,
			"choices_json": _json(choices) if choices else None,
		}
	)
	message.name = frappe.generate_hash(length=20)
	message.db_insert()


def _friendly_error(error: Exception) -> str:
	if isinstance(error, gateway.LLMError):
		return _("I can't reach the AI model right now, so I had to stop. Please try again in a few minutes.")
	if isinstance(error, (BudgetExceeded, tools.ToolError)):
		return _("Sorry, I couldn't finish this request: {0}").format(str(error))
	return _(
		"Sorry, something went wrong on my side and I had to stop. Your administrator can see the details. Please start a new request."
	)


CONVERSATION_EVENT = "assistant_update"


def _publish(run: str, status: str, node: str | None = None):
	# Payload carries no business data; pages re-fetch through permission-checked APIs.
	frappe.publish_realtime(RUN_EVENT, {"run": run, "status": status, "node": node}, after_commit=True)
	conversation = frappe.db.get_value("Agent Run", run, "conversation")
	if conversation:
		publish_conversation(conversation)


def publish_conversation(conversation: str):
	user = frappe.db.get_value("Assistant Conversation", conversation, "user")
	frappe.publish_realtime(CONVERSATION_EVENT, {"conversation": conversation}, user=user, after_commit=True)


@dataclass
class RunContext:
	run: str
	agent: Any  # Agent Definition doc
	requested_by: str
	max_llm_calls: int
	token_budget: int
	max_runtime_s: int
	llm_calls: int = 0
	usage: gateway.Usage = field(default_factory=gateway.Usage)
	segment_started: float = field(default_factory=time.monotonic)
	step_index: int = 0
	# Per-step scratch, reset by begin_step().
	step_tokens: int = 0
	step_tools: list[str] = field(default_factory=list)
	step_summary: str = ""
	step_started: float = 0.0
	step_output: Any = None
	policies: dict = field(default_factory=dict)
	saver: Any = None

	# --- helpers for node functions -------------------------------------------------

	def note(self, summary: str, output: Any = None):
		self.step_summary = summary
		if output is not None:
			self.step_output = output

	def say(self, content: str, kind: str = "text", card: dict | None = None):
		"""Tell the buyer something mid-run. Not for nodes that pause: they re-run on resume."""
		post_message(self.run, "assistant", content, kind, card)

	def tool(self, name: str, **arguments) -> dict:
		"""Run a read tool as the requesting user; raise on failure so the step fails visibly."""
		self.step_tools.append(name)
		outcome = tools.run_tool(name, arguments)
		if not outcome["ok"]:
			raise tools.ToolError(_("{0} failed: {1}").format(name, outcome["error"]))
		return outcome["result"]

	def try_tool(self, name: str, **arguments) -> dict:
		"""Like tool(), but return the {ok, result|error} outcome instead of raising."""
		self.step_tools.append(name)
		return tools.run_tool(name, arguments)

	def llm(
		self, messages: list[dict], *, response_schema: dict | None = None, max_tokens: int | None = None
	):
		if self.llm_calls >= self.max_llm_calls:
			raise BudgetExceeded(
				_("Stopped: the agent reached its limit of {0} LLM calls.").format(self.max_llm_calls)
			)
		if self.usage.total_tokens >= self.token_budget:
			raise BudgetExceeded(
				_("Stopped: the agent used its token budget of {0}.").format(self.token_budget)
			)
		if not self.agent.model_config and not frappe.flags.agent_eval_offline:
			raise BudgetExceeded(_("The agent has no model configuration."))
		self.llm_calls += 1
		system = {"role": "system", "content": self.agent.instructions or ""}
		response = gateway.chat(
			self.agent.model_config,
			[system, *messages],
			response_schema=response_schema,
			max_tokens=max_tokens,
		)
		self.usage.add(response.usage)
		self.step_tokens += response.usage.total_tokens
		return response

	def policy(self, rule_key: str) -> dict | None:
		"""Enabled policy for this agent (agent-specific overrides global), or None."""
		return self.policies.get(rule_key)

	# --- step bookkeeping -----------------------------------------------------------

	def check_runtime(self):
		elapsed = time.monotonic() - self.segment_started
		if elapsed > self.max_runtime_s:
			raise BudgetExceeded(
				_("Stopped: the run exceeded its {0}s runtime limit.").format(self.max_runtime_s)
			)

	def begin_step(self):
		self.step_tokens = 0
		self.step_tools = []
		self.step_summary = ""
		self.step_output = None
		self.step_started = time.monotonic()

	def end_step(self, node_id: str, kind: str, status: str, summary: str | None = None):
		self.step_index += 1
		started_at = now_datetime()
		step = frappe.new_doc("Agent Run Step")
		step.update(
			{
				"parent": self.run,
				"parenttype": "Agent Run",
				"parentfield": "steps",
				"idx": self.step_index,
				"node_id": node_id,
				"node_kind": kind,
				"status": status,
				"started_at": started_at,
				"duration_ms": int((time.monotonic() - self.step_started) * 1000),
				"tokens": self.step_tokens,
				"tool_calls": ", ".join(dict.fromkeys(self.step_tools))[:140],
				"summary": (summary if summary is not None else self.step_summary)[:2000],
				"output_json": _json(self.step_output) if self.step_output is not None else None,
			}
		)
		step.name = frappe.generate_hash(length=20)
		step.db_insert()
		frappe.db.set_value(
			"Agent Run",
			self.run,
			{
				"llm_calls": self.llm_calls,
				"prompt_tokens": self.usage.prompt_tokens,
				"completion_tokens": self.usage.completion_tokens,
				"total_tokens": self.usage.total_tokens,
			},
			update_modified=False,
		)
		if self.saver:
			self.saver.flush()
		_commit()
		_publish(self.run, "Running", node_id)


def current() -> RunContext:
	ctx = _current.get()
	if ctx is None:
		raise RuntimeError("No agent run is active")
	return ctx


def load_policies(agent: str) -> dict:
	policies = {}
	rows = frappe.get_all(
		"Agent Policy",
		filters={"enabled": 1},
		fields=["policy_name", "rule_key", "severity", "parameters", "agent"],
	)
	# Global policies first, then this agent's own rows override them.
	for row in sorted((r for r in rows if r.agent in (None, "", agent)), key=lambda r: bool(r.agent)):
		if row.rule_key:
			row.parameters = json.loads(row.parameters) if row.parameters else {}
			policies[row.rule_key] = row
	return policies


# ---------------------------------------------------------------------------
# Graph compilation


def build_graph(workflow_key: str, checkpointer=None):
	from langgraph.errors import GraphInterrupt
	from langgraph.graph import END, START, StateGraph

	workflow = registry.WORKFLOWS[workflow_key]
	module = frappe.get_module(WORKFLOW_MODULES[workflow_key])
	nodes = {n["id"]: n for n in workflow["nodes"]}
	missing = [n for n in nodes if not hasattr(module, n)]
	if missing:
		raise RuntimeError(f"Workflow {workflow_key} has no implementation for: {', '.join(missing)}")

	def wrap(node: dict):
		fn = getattr(module, node["id"])

		def run_node(state: dict) -> dict:
			ctx = current()
			ctx.check_runtime()
			ctx.begin_step()
			try:
				update = fn(state, ctx) or {}
			except GraphInterrupt:
				ctx.end_step(
					node["id"], node["kind"], "Interrupted", ctx.step_summary or _("Waiting for a person")
				)
				raise
			except Exception as error:
				ctx.end_step(node["id"], node["kind"], "Failed", str(error))
				raise
			ctx.end_step(node["id"], node["kind"], "Completed")
			return update

		return run_node

	graph = StateGraph(module.State)
	for node in workflow["nodes"]:
		graph.add_node(node["id"], wrap(node))
	graph.add_edge(START, workflow["entry"])
	for node in workflow["nodes"]:
		edges = node["next"]
		if len(edges) == 1:
			graph.add_edge(node["id"], END if edges[0][1] == "END" else edges[0][1])
		else:
			mapping = {cond: (END if target == "END" else target) for cond, target in edges}
			graph.add_conditional_edges(node["id"], lambda state: state["route"], mapping)
	return graph.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Execution


def _finish(run_name: str, values: dict):
	status = values.get("final_status") or "Completed"
	run = frappe.get_doc("Agent Run", run_name)
	run.db_set(
		{
			"status": status,
			"outcome": values.get("outcome") or "",
			"pending_question": None,
			"ended_at": now_datetime(),
			"duration_s": time_diff_in_seconds(now_datetime(), run.started_at) if run.started_at else 0,
			"result_json": _json(values.get("result") or {}),
		},
		update_modified=False,
	)
	reply = values.get("reply") or (values.get("result") or {}).get("explanation") or values.get("outcome")
	if reply:
		post_message(run_name, "assistant", reply, "result", values.get("reply_card"))
	# A finished run can never resume, so its checkpoints are no longer needed.
	MariaDBSaver().delete_thread(run.thread_id or run_name)
	return status


def execute(run: str, resume: dict | None = None):
	"""Run (or resume) a graph until it finishes or pauses. Safe to call from a worker."""
	from langgraph.types import Command

	doc = frappe.get_doc("Agent Run", run)
	if doc.status in FINISHED:
		return doc.status
	agent = frappe.get_doc("Agent Definition", doc.agent)
	previous_user = frappe.session.user
	# Tools must see exactly what the requester may see, whoever triggered this job.
	frappe.set_user(doc.requested_by)
	ctx = RunContext(
		run=run,
		agent=agent,
		requested_by=doc.requested_by,
		max_llm_calls=agent.max_steps or 8,
		token_budget=agent.token_budget or 40000,
		max_runtime_s=agent.max_runtime_s or 180,
		llm_calls=doc.llm_calls or 0,
		usage=gateway.Usage(doc.prompt_tokens or 0, doc.completion_tokens or 0, doc.total_tokens or 0),
		step_index=len(doc.steps),
		policies=load_policies(agent.name),
		saver=MariaDBSaver(),
	)
	token = _current.set(ctx)
	values = {
		"status": "Running",
		"pending_question": None,
		"model_config": agent.model_config,
		"agent_version": doc.agent_version or agent.version,
	}
	if not doc.started_at:
		values["started_at"] = now_datetime()
	doc.db_set(values, update_modified=False)
	_commit()
	_publish(run, "Running")
	try:
		graph = build_graph(agent.workflow_key, ctx.saver)
		config = {"configurable": {"thread_id": doc.thread_id or run}, "recursion_limit": RECURSION_LIMIT}
		payload = Command(resume=resume) if resume is not None else {"request": doc.request, "run": run}
		# durability="sync": save each checkpoint before the next step. The default saves in a
		# background thread, which would share this job's single database connection.
		for _update in graph.stream(payload, config, stream_mode="updates", durability="sync"):
			pass
		ctx.saver.flush()
		snapshot = graph.get_state(config)
		if snapshot.interrupts:
			pause = snapshot.interrupts[0].value or {}
			status = "Awaiting approval" if pause.get("type") == "approval" else "Waiting for buyer"
			frappe.db.set_value(
				"Agent Run",
				run,
				{"status": status, "pending_question": pause.get("message") or ""},
				update_modified=False,
			)
			post_message(
				run,
				"assistant",
				pause.get("chat") or pause.get("message") or "",
				"approval" if status == "Awaiting approval" else "question",
				pause.get("card"),
				pause.get("choices"),
			)
		else:
			status = _finish(run, snapshot.values)
	except Exception as error:
		status = "Failed"
		if not sandboxed():
			frappe.db.rollback()
		if not isinstance(error, (BudgetExceeded, gateway.LLMError, tools.ToolError)):
			frappe.log_error(
				title=f"Agent run {run} failed", reference_doctype="Agent Run", reference_name=run
			)
		frappe.db.set_value(
			"Agent Run",
			run,
			{
				"status": "Failed",
				"error": str(error)[:2000],
				"ended_at": now_datetime(),
				"pending_question": None,
			},
			update_modified=False,
		)
		post_message(run, "assistant", _friendly_error(error), "error")
		ctx.saver.discard()
		ctx.saver.delete_thread(doc.thread_id or run)
	finally:
		_current.reset(token)
		frappe.set_user(previous_user)
	_commit()
	_publish(run, status)
	return status


def _enqueue(run: str, resume: dict | None = None):
	if frappe.flags.agent_eval:
		# Evaluations must finish inside their own transaction, so run inline.
		execute(run, resume)
		return
	agent = frappe.db.get_value("Agent Run", run, "agent")
	runtime = frappe.db.get_value("Agent Definition", agent, "max_runtime_s") or 180
	frappe.enqueue(
		"pridict.agent_studio.runtime.execute",
		queue="long",
		timeout=runtime + 300,
		job_id=f"agent-run::{run}",
		deduplicate=True,
		enqueue_after_commit=True,
		run=run,
		resume=resume,
	)


# ---------------------------------------------------------------------------
# Whitelisted actions


@frappe.whitelist(methods=["POST"])
def start_run(agent: str, request: str) -> dict:
	return {"run": create_run(agent, request)}


def create_run(agent: str, request: str, conversation: str | None = None) -> str:
	"""Start a run as the session user. From a conversation, the request is already in the chat."""
	if not STARTER_ROLES & set(frappe.get_roles()):
		frappe.throw(_("You are not allowed to start agent runs."), frappe.PermissionError)
	request = (request or "").strip()
	if len(request) < 5:
		frappe.throw(
			_(
				"Describe what you need, for example: Source 500 kg of aluminium sheet for Stores by 30 October."
			)
		)
	status, workflow_key = frappe.db.get_value("Agent Definition", agent, ["status", "workflow_key"]) or (
		None,
		None,
	)
	if not status:
		frappe.throw(_("Agent {0} not found.").format(agent))
	if status != "Active" and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Agent {0} is {1}; only administrators can test it.").format(agent, _(status).lower()))
	if status in ("Disabled", "Planned"):
		frappe.throw(_("Agent {0} is {1}.").format(agent, _(status).lower()))
	if workflow_key not in WORKFLOW_MODULES:
		frappe.throw(_("Agent {0} has no runnable workflow.").format(agent))
	active = frappe.db.count(
		"Agent Run", {"requested_by": frappe.session.user, "status": ["in", ["Queued", "Running"]]}
	)
	if active >= MAX_ACTIVE_RUNS_PER_USER and not frappe.flags.agent_eval:
		frappe.throw(_("You already have {0} runs in progress. Wait for one to finish.").format(active))
	run = frappe.get_doc(
		{
			"doctype": "Agent Run",
			"agent": agent,
			"agent_version": frappe.db.get_value("Agent Definition", agent, "version"),
			"status": "Queued",
			"requested_by": frappe.session.user,
			"request": request[:4000],
			"conversation": conversation,
		}
	)
	run.insert(ignore_permissions=True)
	run.db_set("thread_id", run.name, update_modified=False)
	if not conversation:
		post_message(run.name, "user", request[:4000])
	_enqueue(run.name)
	return run.name


def _can_act_on(run) -> bool:
	return run.requested_by == frappe.session.user or "System Manager" in frappe.get_roles()


@frappe.whitelist(methods=["POST"])
def answer_run(run: str, answer: str) -> dict:
	answer_paused_run(run, answer)
	return {"run": run}


def answer_paused_run(run: str, answer: str, post: bool = True):
	"""Resume a run waiting for the buyer. post=False when the answer is already in a conversation."""
	doc = frappe.get_doc("Agent Run", run)
	if not _can_act_on(doc):
		frappe.throw(_("Only the person who started this run can answer."), frappe.PermissionError)
	if doc.status != "Waiting for buyer":
		frappe.throw(_("This run is not waiting for an answer."))
	answer = (answer or "").strip()
	if not answer:
		frappe.throw(_("Enter an answer."))
	doc.db_set({"status": "Queued", "pending_question": None}, update_modified=False)
	if post:
		post_message(run, "user", answer[:2000])
	_enqueue(run, {"answer": answer[:2000], "by": frappe.session.user})


def resume_run(run: str, resume: dict):
	"""Continue a paused run (used by the approval decision API)."""
	frappe.db.set_value(
		"Agent Run", run, {"status": "Queued", "pending_question": None}, update_modified=False
	)
	_enqueue(run, resume)


@frappe.whitelist(methods=["POST"])
def cancel_run(run: str) -> dict:
	doc = frappe.get_doc("Agent Run", run)
	if not _can_act_on(doc):
		frappe.throw(_("Only the person who started this run can cancel it."), frappe.PermissionError)
	if doc.status in FINISHED:
		frappe.throw(_("This run has already finished."))
	if doc.status == "Running":
		frappe.throw(_("The run is working right now; cancel it once it pauses or finishes."))
	for approval in frappe.get_all("Agent Approval", filters={"run": run, "status": "Pending"}, pluck="name"):
		frappe.db.set_value(
			"Agent Approval", approval, {"status": "Expired", "decision_note": _("Run cancelled")}
		)
	doc.db_set(
		{
			"status": "Cancelled",
			"pending_question": None,
			"ended_at": now_datetime(),
			"outcome": _("Cancelled by {0}").format(frappe.session.user),
		},
		update_modified=False,
	)
	MariaDBSaver().delete_thread(doc.thread_id or run)
	post_message(run, "assistant", _("Request cancelled. Nothing more will be done for it."), "notice")
	_publish(run, "Cancelled")
	return {"run": run}
