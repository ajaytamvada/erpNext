"""Procurement Assistant conversations: a tool-calling agent in front of the sourcing workflow.

Each user message starts one turn, run as a background job as the user (so every read
tool sees exactly what that user may see). In a turn the model answers directly, calls
read tools and answers from their results, or takes one of a few actions:

- start_sourcing / answer_sourcing / cancel_sourcing drive a procurement-sourcing Agent
  Run linked to the conversation. The run posts its own questions, cards and results
  into the run; the chat shows conversation and run messages merged in time order.
- propose_material_request shows a draft for the user to confirm; only after they agree
  (quick reply or confirm_pending_action) does create_draft_material_request run.

Every LLM call and tool call is recorded as an Agent Run Step on the conversation, so
administrators can trace a turn like any agent run.
"""

from __future__ import annotations

import json
import time

import frappe
from frappe import _
from frappe.utils import formatdate, get_fullname, getdate, now_datetime, nowdate

from pridict.agent_studio import gateway, registry, runtime, tools

DOCTYPE = "Assistant Conversation"
MAX_HISTORY = 30
MAX_ROUNDS = 6
TOOL_RESULT_CHARS = 12000


def create_label() -> str:
	return _("Yes, create the draft")


def discard_label() -> str:
	return _("No, discard it")


def _obj(properties: dict, required: list[str]) -> dict:
	return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


START_SOURCING = {
	"name": "start_sourcing",
	"description": (
		"Start the sourcing workflow for something the user wants to buy, order, source or restock. It checks "
		"stock and open orders, finds suppliers (helping create missing items or suppliers), and prepares a "
		"request for quotation for approval. Its questions and results appear in the chat by themselves."
	),
	"parameters": _obj(
		{
			"request": {
				"type": "string",
				"description": "What the user wants, in their words: item, quantity, warehouse and date if known",
			}
		},
		["request"],
	),
}
ANSWER_SOURCING = {
	"name": "answer_sourcing",
	"description": (
		"Pass the user's reply to the question the open sourcing request is waiting on. Only for a reply to "
		"that question (e.g. choosing an option, giving a quantity, date, warehouse or supplier). Never for a "
		"new question such as asking about stock, orders or suppliers: answer those yourself."
	),
	"parameters": _obj({"answer": {"type": "string"}}, ["answer"]),
}
CANCEL_SOURCING = {
	"name": "cancel_sourcing",
	"description": "Cancel the open sourcing request, only when the user asks to stop it.",
	"parameters": _obj({}, []),
}
PROPOSE_MATERIAL_REQUEST = {
	"name": "propose_material_request",
	"description": (
		"Show the user a draft purchase Material Request to confirm. Use real item codes (look them up first) "
		"and a warehouse; nothing is created until the user agrees."
	),
	"parameters": _obj(
		{
			"items": {
				"type": "array",
				"items": _obj(
					{"item_code": {"type": "string"}, "qty": {"type": "number"}}, ["item_code", "qty"]
				),
			},
			"warehouse": {"type": "string"},
			"schedule_date": {"type": "string", "description": "Required-by date, YYYY-MM-DD"},
		},
		["items", "warehouse", "schedule_date"],
	),
}
CONFIRM_PENDING = {
	"name": "confirm_pending_action",
	"description": "The user agreed to the draft shown to them: create it.",
	"parameters": _obj({}, []),
}
DISCARD_PENDING = {
	"name": "discard_pending_action",
	"description": "The user does not want the draft shown to them: discard it.",
	"parameters": _obj({}, []),
}


def _loads(value, default=None):
	try:
		return json.loads(value) if value else default
	except ValueError:
		return default


def _quick(text: str, choices: list[str]) -> str | None:
	normal = (text or "").strip().rstrip(".!").lower()
	return next((c for c in choices if c and c.lower() == normal), None)


def post(conversation: str, content: str, kind: str = "text", card=None, choices=None, role="assistant"):
	runtime.post_message(conversation, role, content, kind, card, choices, parenttype=DOCTYPE)


def merged_messages(conversation: str) -> list[dict]:
	"""The conversation's own messages plus those of its sourcing runs, in time order."""
	runs = frappe.get_all("Agent Run", filters={"conversation": conversation}, pluck="name")
	fields = [
		"parent",
		"parenttype",
		"role",
		"kind",
		"content",
		"card_json",
		"choices_json",
		"posted_at",
		"idx",
	]
	rows = frappe.get_all(
		"Agent Chat Message", filters={"parent": conversation, "parenttype": DOCTYPE}, fields=fields
	)
	if runs:
		rows += frappe.get_all(
			"Agent Chat Message", filters={"parent": ["in", runs], "parenttype": "Agent Run"}, fields=fields
		)
	return sorted(rows, key=lambda m: (m.posted_at, m.parenttype == DOCTYPE, m.idx))


def _as_text(message) -> str:
	text = message.content or ""
	card = _loads(message.card_json)
	if card:
		lines = [f"{k}: {v}" for k, v in card.get("fields") or []]
		text += f"\n[{card.get('title') or 'Card'}]\n" + "\n".join(lines)
	return text


class Turn:
	def __init__(self, conversation, agent):
		self.conversation = conversation
		self.agent = agent
		self.user = conversation.user
		self.model_config = agent.model_config or frappe.db.get_value(
			"Agent Definition", registry.PROCUREMENT_AGENT, "model_config"
		)
		self.max_llm_calls = agent.max_steps or 8
		self.token_budget = agent.token_budget or 40000
		self.max_runtime_s = agent.max_runtime_s or 120
		self.started = time.monotonic()
		self.llm_calls = 0
		self.usage = gateway.Usage()
		self.step_index = frappe.db.count(
			"Agent Run Step", {"parent": conversation.name, "parenttype": DOCTYPE}
		)

	# --- bookkeeping ------------------------------------------------------------------

	def step(
		self, node: str, kind: str, status: str, summary: str, started: float, tokens: int = 0, output=None
	):
		self.step_index += 1
		row = frappe.new_doc("Agent Run Step")
		row.update(
			{
				"parent": self.conversation.name,
				"parenttype": DOCTYPE,
				"parentfield": "steps",
				"idx": self.step_index,
				"node_id": node,
				"node_kind": kind,
				"status": status,
				"started_at": now_datetime(),
				"duration_ms": int((time.monotonic() - started) * 1000),
				"tokens": tokens,
				"tool_calls": node if kind == "tool" else "",
				"summary": summary[:2000],
				"output_json": json.dumps(output, default=str, ensure_ascii=False)[:60000]
				if output is not None
				else None,
			}
		)
		row.name = frappe.generate_hash(length=20)
		row.db_insert()

	def llm(self, messages: list[dict], specs: list[dict]) -> gateway.LLMResponse:
		if self.llm_calls >= self.max_llm_calls:
			raise runtime.BudgetExceeded(_("I needed more steps than I'm allowed for one message."))
		if self.usage.total_tokens >= self.token_budget:
			raise runtime.BudgetExceeded(
				_("This question needed more reading than I'm allowed for one message.")
			)
		if time.monotonic() - self.started > self.max_runtime_s:
			raise runtime.BudgetExceeded(_("This took longer than I'm allowed for one message."))
		if not self.model_config:
			raise runtime.BudgetExceeded(_("The assistant has no model configured."))
		started = time.monotonic()
		self.llm_calls += 1
		response = gateway.chat(self.model_config, messages, tools=specs or None, max_tokens=4096)
		self.usage.add(response.usage)
		wanted = ", ".join(c.name for c in response.tool_calls)
		self.step(
			"assistant",
			"llm",
			"Completed",
			_("Calls {0}").format(wanted) if wanted else (response.content or "")[:300],
			started,
			response.usage.total_tokens,
		)
		return response

	# --- state ------------------------------------------------------------------------

	@property
	def pending(self) -> dict | None:
		return _loads(self.conversation.pending_action_json)

	def set_pending(self, value: dict | None):
		self.conversation.pending_action_json = json.dumps(value, default=str) if value else None
		frappe.db.set_value(
			DOCTYPE,
			self.conversation.name,
			"pending_action_json",
			self.conversation.pending_action_json,
			update_modified=False,
		)

	def active_run(self):
		name = self.conversation.active_run
		if not name or not frappe.db.exists("Agent Run", name):
			return None
		return frappe.get_doc("Agent Run", name)

	def open_run(self):
		run = self.active_run()
		return run if run and run.status not in runtime.FINISHED else None

	def say(self, content: str, kind: str = "text", card=None, choices=None):
		post(self.conversation.name, content, kind, card, choices)

	# --- the turn -----------------------------------------------------------------------

	def run(self):
		history = merged_messages(self.conversation.name)
		text = next((m.content for m in reversed(history) if m.role == "user"), "") or ""
		run = self.open_run()

		# Quick replies are handled without the model: they are unambiguous.
		if self.pending and _quick(text, [create_label(), discard_label()]):
			return self.confirm_pending() if _quick(text, [create_label()]) else self.discard_pending()
		if run and run.status == "Waiting for buyer":
			last = next(
				(m for m in reversed(history) if m.parent == run.name and m.role == "assistant"), None
			)
			if last and _quick(text, _loads(last.choices_json, [])):
				runtime.answer_paused_run(run.name, text, post=False)
				return

		messages = [
			{"role": "system", "content": self.agent.instructions or registry.ASSISTANT_INSTRUCTIONS},
			{"role": "system", "content": self.context(run)},
			*[
				{"role": m.role, "content": _as_text(m)}
				for m in history[-MAX_HISTORY:]
				if (m.content or m.card_json)
			],
		]
		specs = self.specs(run)
		for _round in range(MAX_ROUNDS):
			response = self.llm(messages, specs)
			if not response.tool_calls:
				self.say((response.content or "").strip() or _("Sorry, I don't have an answer for that."))
				return
			messages.append(response.assistant_message())
			finished = False
			for call in response.tool_calls:
				result, ends_turn = self.dispatch(call)
				messages.append(
					{
						"role": "tool",
						"tool_call_id": call.id,
						"content": json.dumps(result, default=str, ensure_ascii=False)[:TOOL_RESULT_CHARS],
					}
				)
				finished = finished or ends_turn
			if finished:
				return
		self.say(
			_("Sorry, I couldn't work that out in the steps I'm allowed. Could you narrow the question down?")
		)

	def context(self, run) -> str:
		company = frappe.defaults.get_user_default("Company")
		lines = [
			f"Today is {formatdate(nowdate(), 'dd MMM yyyy')} ({nowdate()}).",
			f"The user is {get_fullname(self.user)} ({self.user}). Their default company is {company or 'not set'}.",
		]
		if run:
			lines.append(
				f"There is an open sourcing request {run.name} for: {run.request}. Status: {run.status}."
			)
			if run.status == "Waiting for buyer":
				lines.append(
					f"It is waiting for the user's answer to: {run.pending_question}\n"
					"If the user's latest message replies to that, call answer_sourcing. If it is a question or about "
					"something else, answer it yourself with the tools and do not call answer_sourcing; then remind "
					"them in one short sentence that the purchase request is still waiting for their answer."
				)
			elif run.status == "Awaiting approval":
				lines.append(
					"It is waiting for a manager's approval; the user will be told here when they decide."
				)
		else:
			lines.append("There is no open sourcing request.")
		if self.pending:
			lines.append(
				"A draft is waiting for the user's confirmation: "
				+ json.dumps(self.pending.get("arguments"), default=str)
				+ ". If they agree, call confirm_pending_action; if they decline, call discard_pending_action."
			)
		return "\n".join(lines)

	def specs(self, run) -> list[dict]:
		bound = [row.tool for row in self.agent.tools]
		specs = tools.tool_specs(bound)
		specs.append(START_SOURCING)
		if run and run.status == "Waiting for buyer":
			specs.append(ANSWER_SOURCING)
		if run and run.status != "Running":
			specs.append(CANCEL_SOURCING)
		if "create_draft_material_request" in bound:
			specs.append(PROPOSE_MATERIAL_REQUEST)
		if self.pending:
			specs += [CONFIRM_PENDING, DISCARD_PENDING]
		return specs

	# --- tools and actions ----------------------------------------------------------------

	def dispatch(self, call) -> tuple[dict, bool]:
		"""Run one tool call. Returns (result for the model, whether the turn ends here)."""
		started = time.monotonic()
		actions = {
			"start_sourcing": self.start_sourcing,
			"answer_sourcing": self.answer_sourcing,
			"cancel_sourcing": self.cancel_sourcing,
			"propose_material_request": self.propose_material_request,
			"confirm_pending_action": self.confirm_action,
			"discard_pending_action": self.discard_action,
		}
		if call.name in actions:
			try:
				result, ends_turn = actions[call.name](**(call.arguments or {}))
			except (TypeError, frappe.ValidationError, frappe.PermissionError, tools.ToolError) as error:
				result, ends_turn = {"ok": False, "error": frappe.utils.strip_html(str(error))}, False
			self.step(
				call.name,
				"human" if ends_turn else "rule",
				"Completed",
				json.dumps(result, default=str)[:300],
				started,
			)
			return result, ends_turn

		bound = {row.tool for row in self.agent.tools}
		if call.name not in bound or call.name not in tools.READ_TOOLS:
			outcome = {"ok": False, "error": _("Tool {0} is not available.").format(call.name)}
		else:
			outcome = tools.run_tool(call.name, call.arguments or {})
		summary = (
			_("{0} ok").format(call.name)
			if outcome["ok"]
			else _("{0} failed: {1}").format(call.name, outcome["error"])
		)
		self.step(
			call.name,
			"tool",
			"Completed" if outcome["ok"] else "Failed",
			summary,
			started,
			output=call.arguments,
		)
		return (outcome["result"] if outcome["ok"] else {"error": outcome["error"]}), False

	def start_sourcing(self, request: str):
		run = self.open_run()
		if run:
			return {
				"ok": False,
				"error": f"Sourcing request {run.name} is still open ({run.status}). Ask the user to finish or cancel it first.",
			}, False
		name = runtime.create_run(registry.PROCUREMENT_AGENT, request, conversation=self.conversation.name)
		self.conversation.active_run = name
		frappe.db.set_value(DOCTYPE, self.conversation.name, "active_run", name, update_modified=False)
		self.say(_("On it. I'm checking stock, open orders, suppliers and prices for that."))
		return {"ok": True, "run": name}, True

	def answer_sourcing(self, answer: str):
		run = self.open_run()
		if not run or run.status != "Waiting for buyer":
			return {"ok": False, "error": "No sourcing request is waiting for an answer."}, False
		runtime.answer_paused_run(run.name, answer, post=False)
		return {"ok": True}, True

	def cancel_sourcing(self):
		run = self.open_run()
		if not run:
			return {"ok": False, "error": "There is no open sourcing request."}, False
		runtime.cancel_run(run.name)
		return {"ok": True}, True

	def propose_material_request(self, items: list, warehouse: str, schedule_date: str):
		problems = []
		if not frappe.db.exists("Warehouse", {"name": warehouse, "is_group": 0}):
			problems.append(f"Warehouse {warehouse} does not exist.")
		try:
			if getdate(schedule_date) < getdate(nowdate()):
				problems.append("The required-by date is in the past.")
		except Exception:
			problems.append(f"Cannot read the date {schedule_date}.")
		lines = []
		for line in items or []:
			code, qty = line.get("item_code"), line.get("qty") or 0
			item = frappe.db.get_value("Item", code, ["item_name", "stock_uom"], as_dict=True)
			if not item:
				problems.append(f"Item {code} does not exist; look it up with list_items.")
			elif qty <= 0:
				problems.append(f"Quantity for {code} must be more than zero.")
			else:
				lines.append((code, item, qty))
		if not lines:
			problems.append("Give at least one item.")
		if problems:
			return {"ok": False, "error": " ".join(problems)}, False

		arguments = {
			"items": [{"item_code": code, "qty": qty} for code, _item, qty in lines],
			"warehouse": warehouse,
			"schedule_date": str(getdate(schedule_date)),
		}
		self.set_pending({"tool": "create_draft_material_request", "arguments": arguments})
		card = {
			"title": _("Draft Material Request (purchase)"),
			"fields": [
				[_("Deliver to"), warehouse],
				[_("Required by"), formatdate(schedule_date)],
				*[
					[
						item.item_name if item.item_name == code else f"{item.item_name} ({code})",
						f"{qty:g} {item.stock_uom}",
					]
					for code, item, qty in lines
				],
			],
		}
		self.say(
			_("Here's the Material Request I'd raise. Shall I create it as a draft?"),
			"question",
			card,
			[create_label(), discard_label()],
		)
		return {"ok": True, "shown_to_user": True}, True

	def confirm_pending(self):
		pending = self.pending
		if not pending:
			self.say(_("There's nothing waiting to be created."))
			return
		self.set_pending(None)
		outcome = tools.run_tool(
			pending["tool"],
			pending["arguments"],
			confirmation={"conversation": self.conversation.name, "by": self.user},
		)
		if not outcome["ok"]:
			self.say(_("I couldn't create it: {0}").format(outcome["error"]), "error")
			return
		name = outcome["result"]["material_request"]
		self.say(
			_(
				"Done. I created the draft Material Request {0}. It's still a draft: open it to review and submit."
			).format(name),
			"result",
			{
				"title": _("Draft Material Request"),
				"link": {"doctype": "Material Request", "name": name},
				"fields": [[_("Document"), name], [_("Deliver to"), pending["arguments"]["warehouse"]]],
			},
		)

	def discard_pending(self):
		self.set_pending(None)
		self.say(_("OK, I've discarded that draft."), "notice")

	def confirm_action(self):
		self.confirm_pending()
		return {"ok": True}, True

	def discard_action(self):
		self.discard_pending()
		return {"ok": True}, True


def respond(conversation: str):
	"""Background job: answer the latest user message in a conversation."""
	conv = frappe.get_doc(DOCTYPE, conversation)
	agent = frappe.get_doc("Agent Definition", conv.agent)
	previous = frappe.session.user
	frappe.set_user(conv.user)
	turn = Turn(conv, agent)
	try:
		turn.run()
	except Exception as error:
		if not runtime.sandboxed():
			frappe.db.rollback()
		if not isinstance(error, (gateway.LLMError, runtime.BudgetExceeded, tools.ToolError)):
			frappe.log_error(
				title=f"Assistant conversation {conversation} failed",
				reference_doctype=DOCTYPE,
				reference_name=conversation,
			)
		post(conversation, runtime._friendly_error(error), "error")
	finally:
		frappe.db.set_value(
			DOCTYPE,
			conversation,
			{
				"working": 0,
				"last_activity": now_datetime(),
				"llm_calls": (conv.llm_calls or 0) + turn.llm_calls,
				"total_tokens": (conv.total_tokens or 0) + turn.usage.total_tokens,
			},
			update_modified=False,
		)
		frappe.set_user(previous)
	runtime._commit()
	runtime.publish_conversation(conversation)


def enqueue_respond(conversation: str):
	runtime_s = frappe.db.get_value("Agent Definition", registry.ASSISTANT_AGENT, "max_runtime_s") or 120
	frappe.enqueue(
		"pridict.agent_studio.conversation.respond",
		queue="long",
		timeout=runtime_s + 120,
		job_id=f"assistant::{conversation}",
		deduplicate=True,
		enqueue_after_commit=True,
		conversation=conversation,
	)
