"""The AI architect: builds and changes automations from a chat, by sending spec operations.

Each admin message starts one turn, run as a background job as that admin. The model gets
the rules, the node catalog, the current draft (with its validation) and the recent chat.
It looks things up with read-only tools (always as the admin, so it sees only what they
may see), changes the draft only through apply_changes (the same operations the canvas
sends), and ends the turn with a reply or with ask_user. The chat is an Assistant
Conversation with purpose "Automation Builder"; every LLM and tool call is recorded as a
step on it.
"""

from __future__ import annotations

import json
import time

import frappe
from frappe import _
from frappe.utils import formatdate, get_fullname, now_datetime, nowdate

from pridict.agent_studio import gateway, runtime
from pridict.automation import api, expressions, guards
from pridict.automation import nodes as catalog
from pridict.automation import spec as specs

DOCTYPE = "Assistant Conversation"
PURPOSE = "Automation Builder"
CHAT_EVENT = "automation_chat"
MAX_HISTORY = 30
MAX_LLM_CALLS = 16
TOKEN_BUDGET = 150_000
MAX_RUNTIME_S = 300
TOOL_RESULT_CHARS = 20_000
# Room for reasoning plus the answer; reasoning models return nothing when this runs out.
MAX_OUTPUT_TOKENS = 16_000
SAMPLE_TEXT_CHARS = 300

PROMPT = """You are the automation architect in Pridict, an ERP built on ERPNext. You build automations
for an administrator by changing a draft automation spec. The draft is shown as a graph on a canvas
under this chat; the administrator can also edit the canvas, so always work from the CURRENT DRAFT
given to you each turn.

How you work
1. Understand the request. Use the lookup tools to find the real DocTypes, fields, users, roles,
   email accounts and reports involved. Never invent DocType or field names.
2. Ask before guessing anything that changes data or emails people: recipients, amounts and
   thresholds, whether documents are submitted or kept as drafts. Ask ONLY with the ask_user tool
   (one question per call, with short choices); never ask questions in a normal reply. Do not ask
   about things you can look up, and do not ask more than needed (at most 3 questions for a
   typical automation). When a detail has an obvious default, build with it and say so.
3. Change the draft only with apply_changes. Prefer the smallest graph that does the job.
4. After apply_changes, read the validation it returns and fix every error before replying.
   Warnings may stay if they are intended (explain them).
   "setup" problems are not yours to fix: the Run As user's missing permissions or a missing
   email account are granted by the administrator. Never stop, ask or redesign because of them.
   Build the automation as requested, then end your reply with one sentence listing what the
   administrator must set up (for example which DocTypes the Run As user needs access to).
5. Reply in one to three short sentences the administrator can check against the canvas: what you
   built or changed. No JSON, no code, no ids unless helpful.
6. If a standard ERPNext feature (Notification, Assignment Rule, Auto Repeat) could do the same
   simply, you may mention it in one short sentence of your reply, but build what was asked.
   Do not ask about it.
7. Never put document values into conditions as code: refer to them through trigger., nodes., vars.
8. You cannot run or activate automations. Tell the administrator to activate it when ready.
9. When the administrator says to use your judgement, decide and build; do not ask again.

ERPNext facts that save lookups
- Stock per item and warehouse: Bin (item_code, warehouse, actual_qty, projected_qty).
- An item's approved suppliers: child table Item Supplier of Item (supplier_items: supplier). Read
  it with data.find_documents, doctype "Item Supplier", parent_doctype "Item", filter on parent.
- A supplier's email: Supplier.email_id; its primary contact: Supplier.supplier_primary_contact.
- A customer's account manager: Customer.account_manager (a user).
- Request for Quotation needs company, transaction_date, items (item_code, qty, uom, stock_uom,
  conversion_factor, schedule_date, warehouse) and suppliers (supplier, contact). Set send_email: 0
  on supplier rows and email with action.send_email, so emails are visible and capped.
- Submitted documents have docstatus 1; drafts 0; cancelled 2.

The spec
- trigger: {id: "trigger", type, label, config}. Change it with set_trigger.
- nodes: [{id, type, label, config}], edges: [{from, to, branch?}]. "END" ends the run.
- Every step must lead somewhere (another step or END). Branching steps (If, Switch, Loop) need
  every branch connected; Stop has no outgoing edge. A Loop's body must lead back to the Loop.

Operations (the ops list of apply_changes)
- {"op": "set_trigger", "type": "trigger.document_event", "config": {...}}
- {"op": "add_node", "id": "short_id", "type": "...", "label": "Readable name", "config": {...},
   "after": "<step id>", "branch": "<branch name if after is a branching step>"}
  add_node with "after" inserts the new step between that step and whatever followed it (on that
  branch). A new step with nothing after it must then be connected (connect ... to END).
- {"op": "update_node", "id": "...", "label": "...", "config_patch": {...}}  (JSON merge patch;
   a null value removes a key)
- {"op": "remove_node", "id": "...", "reconnect": true}
- {"op": "connect", "from": "...", "to": "<id or END>", "branch": "..."}  (replaces that exit)
- {"op": "disconnect", "from": "...", "to": "...", "branch": "..."}
- {"op": "set_settings", "settings_patch": {"on_error": "stop_and_notify", "max_steps": 100}}
- {"op": "set_meta", "title": "...", "description": "one sentence summary"}
Step ids: lower case letters, digits and underscores. Keep set_meta's description up to date.

Expressions
- Text settings are Jinja templates: "Dear {{ trigger.doc.customer_name }}".
- A setting that is exactly one {{ expression }} keeps its type (lists, numbers):
  "{{ nodes.find_overdue.rows }}", "{{ trigger.doc['items'] | map(attribute='item_code') | list }}".
- Child table rows: {"$each": "{{ list }}", "field": "{{ row.x }}", ...} builds one row per item.
- Conditions (If, Switch, trigger condition) are Python-like expressions without {{ }}:
  "trigger.doc.grand_total > 100000", "any(r.qty < 0 for r in nodes.stock.rows)".
  Available: and/or/not, comparisons, any, all, len, min, max, sum, sorted, abs, round, str, int.
- Names available: trigger (doc, event, doctype, name, fired_at, input), nodes.<step id>.<output>,
  vars.<name>, run, today, now. Inside templates frappe.utils.add_days(today, -7) works.
- A document field called items, values or keys must be written doc['items'].
- A step can only use outputs of steps that always run before it.

Node catalog (type: settings; * = required)
{catalog}
"""


# ---------------------------------------------------------------------------
# Tool definitions


def _obj(properties: dict, required: list[str]) -> dict:
	return {"type": "object", "properties": properties, "required": required}


TOOLS = [
	{
		"name": "search_doctypes",
		"description": "Find DocTypes (document types) by name or module, e.g. 'invoice', 'stock'.",
		"parameters": _obj({"query": {"type": "string"}}, ["query"]),
	},
	{
		"name": "get_doctype_fields",
		"description": "Fields of a DocType (names, labels, types, options, required), whether it can be "
		"submitted, and its child tables with their fields.",
		"parameters": _obj({"doctype": {"type": "string"}}, ["doctype"]),
	},
	{
		"name": "get_sample_document",
		"description": "One recent document of a DocType, to see real values. Use sparingly.",
		"parameters": _obj({"doctype": {"type": "string"}}, ["doctype"]),
	},
	{
		"name": "list_users_and_roles",
		"description": "Find enabled users and roles by name, for recipients, assignees and approvers.",
		"parameters": _obj({"query": {"type": "string"}}, ["query"]),
	},
	{
		"name": "list_email_accounts",
		"description": "Email accounts that can send email.",
		"parameters": _obj({}, []),
	},
	{
		"name": "list_print_formats",
		"description": "Print formats for a DocType (for email attachments).",
		"parameters": _obj({"doctype": {"type": "string"}}, ["doctype"]),
	},
	{
		"name": "list_reports",
		"description": "Find Query and Script Reports by name.",
		"parameters": _obj({"query": {"type": "string"}}, ["query"]),
	},
	{
		"name": "validate_expression",
		"description": "Check a template or condition before using it, and list the values available "
		"at a step.",
		"parameters": _obj(
			{
				"expression": {"type": "string"},
				"kind": {"type": "string", "enum": ["template", "condition"]},
				"at_node": {"type": "string", "description": "Step id where it will be used"},
			},
			["expression", "kind"],
		),
	},
	{
		"name": "apply_changes",
		"description": "Change the draft with a list of operations. Returns the new draft, its "
		"validation (fix every error) or why it failed.",
		"parameters": _obj(
			{
				"ops": {"type": "array", "items": {"type": "object"}},
				"summary": {"type": "string", "description": "One line for the change history"},
			},
			["ops", "summary"],
		),
	},
	{
		"name": "ask_user",
		"description": "Ask the administrator a question and end your turn. Offer 2-4 short choices "
		"when the answer is one of a few options.",
		"parameters": _obj(
			{"question": {"type": "string"}, "choices": {"type": "array", "items": {"type": "string"}}},
			["question"],
		),
	},
]


def catalog_text() -> str:
	lines = []
	for node in catalog.describe_all():
		schema = node["config_schema"] or {}
		required = set(schema.get("required") or [])
		settings = []
		for key, prop in (schema.get("properties") or {}).items():
			kind = prop.get("type") or ("list|object" if prop.get("oneOf") else "any")
			if prop.get("enum"):
				kind = "|".join(map(str, prop["enum"]))
			elif prop.get("format") in ("template", "condition"):
				kind = prop["format"]
			settings.append(f"{key}{'*' if key in required else ''} ({kind})")
		extra = []
		if node["branches"]:
			extra.append(f"branches: {', '.join(node['branches'])}")
		if node["type"] == "logic.switch":
			extra.append("branches: each case name, plus default")
		if node["terminal"]:
			extra.append("ends the run")
		if node["outputs"]:
			extra.append(f"outputs: {', '.join(node['outputs'])}")
		lines.append(
			f"- {node['type']} ({node['label']}): {node['description']} "
			f"Settings: {', '.join(settings) or 'none'}." + (f" [{'; '.join(extra)}]" if extra else "")
		)
	return "\n".join(lines)


def split_issues(issues: list[dict]) -> dict:
	"""Validation for the model: design errors to fix, warnings, setup the admin must do."""

	def short(issue):
		return f"{issue['node_id'] or 'automation'}: {issue['message']}"

	return {
		"errors": [short(i) for i in issues if i["level"] == "error" and i.get("kind") != "setup"],
		"warnings": [short(i) for i in issues if i["level"] == "warning"],
		"setup": sorted({i["message"] for i in issues if i.get("kind") == "setup"}),
	}


def compact_spec(spec: dict) -> dict:
	"""The spec without canvas positions, for the model."""

	def strip(node):
		return {key: value for key, value in node.items() if key != "position"}

	return {
		"title": spec.get("title"),
		"description": spec.get("description"),
		"trigger": strip(spec["trigger"]) if spec.get("trigger") else None,
		"nodes": [strip(node) for node in spec.get("nodes", [])],
		"edges": spec.get("edges", []),
		"settings": spec.get("settings"),
	}


# ---------------------------------------------------------------------------
# Conversations


def conversation_for(automation, create: bool = True) -> str | None:
	"""The builder chat of an automation (created on first use)."""
	name = frappe.db.get_value("Automation", automation, "conversation")
	if name and frappe.db.exists(DOCTYPE, name):
		return name
	if not create:
		return None
	title = frappe.db.get_value("Automation", automation, "title")
	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"title": _("Builder: {0}").format(title)[:140],
			"user": frappe.session.user,
			"purpose": PURPOSE,
			"automation": automation,
			"last_activity": now_datetime(),
		}
	).insert(ignore_permissions=True)
	frappe.db.set_value("Automation", automation, "conversation", doc.name, update_modified=False)
	return doc.name


def post(conversation: str, role: str, content: str, kind: str = "text", choices=None, card=None):
	runtime.post_message(conversation, role, content, kind, card, choices, parenttype=DOCTYPE)


def publish(automation: str):
	frappe.publish_realtime(
		CHAT_EVENT, {"automation": automation}, doctype="Automation", docname=automation, after_commit=True
	)


def messages(conversation: str) -> list[dict]:
	return frappe.get_all(
		"Agent Chat Message",
		filters={"parent": conversation, "parenttype": DOCTYPE},
		fields=["role", "kind", "content", "card_json", "choices_json", "posted_at", "idx"],
		order_by="idx asc",
	)


# ---------------------------------------------------------------------------
# The turn


class Turn:
	def __init__(self, automation: str, conversation: str, focus_node: str | None = None):
		self.automation = automation
		self.conversation = conversation
		self.focus_node = focus_node
		self.user = frappe.session.user
		self.model_config = guards.settings().architect_model
		self.started = time.monotonic()
		self.llm_calls = 0
		self.usage = gateway.Usage()
		self.step_index = frappe.db.count("Agent Run Step", {"parent": conversation, "parenttype": DOCTYPE})
		self.changed = False

	# --- bookkeeping ------------------------------------------------------------------

	def step(self, node: str, kind: str, status: str, summary: str, started: float, tokens=0, output=None):
		self.step_index += 1
		row = frappe.new_doc("Agent Run Step")
		row.update(
			{
				"parent": self.conversation,
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

	def llm(self, messages: list[dict]) -> gateway.LLMResponse:
		if not self.model_config:
			raise runtime.BudgetExceeded(_("No AI model is set for the architect (Automation Settings)."))
		if self.llm_calls >= MAX_LLM_CALLS:
			raise runtime.BudgetExceeded(_("I needed more steps than I'm allowed for one message."))
		if self.usage.total_tokens >= TOKEN_BUDGET:
			raise runtime.BudgetExceeded(_("This needed more reading than I'm allowed for one message."))
		if time.monotonic() - self.started > MAX_RUNTIME_S:
			raise runtime.BudgetExceeded(_("This took longer than I'm allowed for one message."))
		started = time.monotonic()
		self.llm_calls += 1
		response = gateway.chat(self.model_config, messages, tools=TOOLS, max_tokens=MAX_OUTPUT_TOKENS)
		self.usage.add(response.usage)
		wanted = ", ".join(c.name for c in response.tool_calls)
		self.step(
			"architect",
			"llm",
			"Completed",
			_("Calls {0}").format(wanted) if wanted else (response.content or "")[:300],
			started,
			response.usage.total_tokens,
		)
		return response

	def say(self, content: str, kind: str = "text", choices=None):
		post(self.conversation, "assistant", content, kind, choices)

	# --- context ------------------------------------------------------------------------

	def draft(self) -> tuple[dict, int, str]:
		row = frappe.db.get_value(
			"Automation", self.automation, ["draft_spec", "draft_revision", "run_as"], as_dict=True
		)
		return specs.load(row.draft_spec or "{}"), row.draft_revision or 0, row.run_as

	def context(self) -> str:
		spec, revision, run_as = self.draft()
		problems = split_issues(specs.validate(spec, live=True, run_as=run_as))
		lines = [
			f"Today is {formatdate(nowdate(), 'dd MMM yyyy')} ({nowdate()}).",
			f"You are helping {get_fullname(self.user)} ({self.user}). The automation runs as {run_as}.",
			f"CURRENT DRAFT (revision {revision}):",
			json.dumps(compact_spec(spec), ensure_ascii=False),
			"VALIDATION: " + json.dumps(problems, ensure_ascii=False),
		]
		if self.focus_node:
			node = specs.all_nodes(spec).get(self.focus_node)
			if node:
				lines.append(
					f"The administrator is asking about the step '{node.get('label') or self.focus_node}' "
					f"(id {self.focus_node}). Focus on that step."
				)
		return "\n".join(lines)

	# --- the loop -------------------------------------------------------------------------

	def run(self):
		history = [m for m in messages(self.conversation) if m.content][-MAX_HISTORY:]
		conversation = [
			{"role": "system", "content": PROMPT.replace("{catalog}", catalog_text())},
			{"role": "system", "content": self.context()},
			*[{"role": m.role, "content": m.content} for m in history],
		]
		nudged = False
		for _round in range(MAX_LLM_CALLS):
			response = self.llm(conversation)
			if not response.tool_calls and not (response.content or "").strip() and not nudged:
				# An empty answer usually means the model spent its output on reasoning; ask once more.
				nudged = True
				conversation.append(
					{
						"role": "system",
						"content": "Your last answer was empty. Continue: call a tool or reply.",
					}
				)
				continue
			if not response.tool_calls:
				reply = (response.content or "").strip() or (
					_("I've updated the draft.")
					if self.changed
					else _("I couldn't work out that change. Could you say it another way?")
				)
				# A reply that changed nothing and ends with a question is a question, even if the
				# model did not use ask_user.
				asks = not self.changed and reply.rstrip().endswith("?")
				self.say(reply, "question" if asks else "text")
				return
			conversation.append(response.assistant_message())
			ends = False
			for call in response.tool_calls:
				result, ends_turn = self.dispatch(call)
				conversation.append(
					{
						"role": "tool",
						"tool_call_id": call.id,
						"content": json.dumps(result, default=str, ensure_ascii=False)[:TOOL_RESULT_CHARS],
					}
				)
				ends = ends or ends_turn
			if ends:
				return
		self.say(
			_(
				"Sorry, I couldn't finish that in the steps I'm allowed. "
				"Could you break it into smaller changes?"
			)
		)

	def dispatch(self, call) -> tuple[dict, bool]:
		started = time.monotonic()
		handler = getattr(self, f"tool_{call.name}", None)
		if not handler or call.name not in {tool["name"] for tool in TOOLS}:
			result, ends = {"ok": False, "error": f"Unknown tool {call.name}."}, False
		else:
			try:
				result, ends = handler(**(call.arguments or {}))
			except TypeError as error:
				result, ends = {"ok": False, "error": f"Bad arguments: {error}"}, False
			except (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError) as error:
				result, ends = {"ok": False, "error": frappe.utils.strip_html(str(error))}, False
			except Exception as error:
				# A bug or a malformed call must not end the turn: log it and let the model recover.
				frappe.log_error(title=f"Automation architect tool {call.name} failed")
				result, ends = {"ok": False, "error": f"The tool failed: {error!r}"}, False
		ok = not (isinstance(result, dict) and result.get("ok") is False)
		self.step(
			call.name,
			"tool",
			"Completed" if ok else "Failed",
			json.dumps(result, default=str, ensure_ascii=False)[:300],
			started,
			output=call.arguments,
		)
		return result, ends

	# --- tools (read-only lookups run as the admin) -----------------------------------------

	def tool_search_doctypes(self, query: str):
		query = (query or "").strip()
		rows = frappe.get_all(
			"DocType",
			filters={"istable": 0},
			or_filters={"name": ["like", f"%{query}%"], "module": ["like", f"%{query}%"]},
			fields=["name", "module", "is_submittable", "issingle"],
			order_by="name",
			limit=40,
		)
		found = [
			{
				"doctype": r.name,
				"module": r.module,
				"submittable": bool(r.is_submittable),
				"single": bool(r.issingle),
			}
			for r in rows
			if frappe.has_permission(r.name, "read")
		][:20]
		return {"doctypes": found}, False

	def _fields(self, doctype: str) -> list[dict]:
		"""Readable fields of a DocType (hidden and layout fields left out)."""
		from frappe.model import no_value_fields

		meta = frappe.get_meta(doctype)
		levels = set(meta.get_permlevel_access("read") or [0]) | {0}
		return [
			field
			for field in meta.fields
			if (field.fieldtype not in no_value_fields or field.fieldtype == "Table")
			and field.permlevel in levels
			and not field.hidden
		]

	def _describe(self, field) -> str:
		"""One compact line: fieldname (Type -> Options) "Label" *required."""
		kind = field.fieldtype
		if field.fieldtype in ("Link", "Table", "Dynamic Link") and field.options:
			kind += f" -> {field.options}"
		elif field.fieldtype == "Select" and field.options:
			kind += ": " + "|".join(o for o in field.options.splitlines() if o)[:120]
		label = (
			f' "{field.label}"'
			if field.label and field.label.lower().replace(" ", "_") != field.fieldname
			else ""
		)
		return f"{field.fieldname} ({kind}){label}{' *' if field.reqd else ''}"

	def tool_get_doctype_fields(self, doctype: str):
		if not frappe.db.exists("DocType", doctype):
			return {"ok": False, "error": f"DocType {doctype} does not exist. Use search_doctypes."}, False
		if not frappe.has_permission(doctype, "read"):
			return {"ok": False, "error": f"You cannot read {doctype}."}, False
		meta = frappe.get_meta(doctype)
		fields = self._fields(doctype)
		tables = {
			f.options: [self._describe(c) for c in self._fields(f.options)][:60]
			for f in fields
			if f.fieldtype == "Table" and f.options
		}
		return {
			"doctype": doctype,
			"submittable": bool(meta.is_submittable),
			"fields": [self._describe(f) for f in fields],
			"child_tables": tables,
			"note": "* = required. Standard fields name, owner, creation, modified, docstatus also exist.",
		}, False

	def tool_get_sample_document(self, doctype: str):
		if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
			return {"ok": False, "error": f"Cannot read {doctype}."}, False
		names = frappe.get_list(doctype, pluck="name", order_by="modified desc", limit_page_length=1)
		if not names:
			return {"ok": True, "document": None, "note": f"No {doctype} documents yet."}, False
		doc = frappe.get_doc(doctype, names[0])
		allowed = {f.fieldname for f in self._fields(doctype)} | {"name", "docstatus", "owner", "creation"}

		def trim(values: dict, keep: set[str] | None):
			out = {}
			for key, value in values.items():
				if keep is not None and key not in keep:
					continue
				if isinstance(value, list):
					out[key] = [trim(row, None) for row in value[:3] if isinstance(row, dict)]
				elif isinstance(value, str) and len(value) > SAMPLE_TEXT_CHARS:
					out[key] = value[:SAMPLE_TEXT_CHARS] + "…"
				elif value not in (None, "", 0, []):
					out[key] = value
			return out

		data = expressions.to_data(doc.as_dict())
		for key in ("_user_tags", "_comments", "_assign", "_liked_by", "_seen"):
			data.pop(key, None)
		return {"document": trim(data, allowed)}, False

	def tool_list_users_and_roles(self, query: str):
		like = f"%{(query or '').strip()}%"
		users = frappe.get_all(
			"User",
			filters={
				"enabled": 1,
				"user_type": "System User",
				"name": ["not in", ["Administrator", "Guest"]],
			},
			or_filters={"name": ["like", like], "full_name": ["like", like]},
			fields=["name", "full_name"],
			limit=15,
		)
		roles = frappe.get_all(
			"Role", filters={"disabled": 0, "role_name": ["like", like]}, pluck="name", limit=15
		)
		return {"users": users, "roles": roles}, False

	def tool_list_email_accounts(self):
		rows = frappe.get_all(
			"Email Account",
			filters={"enable_outgoing": 1},
			fields=["name", "email_id", "default_outgoing"],
		)
		note = "" if rows else "No email account can send email yet; email steps will not pass validation."
		return {"email_accounts": rows, "note": note}, False

	def tool_list_print_formats(self, doctype: str):
		rows = frappe.get_all("Print Format", filters={"doc_type": doctype, "disabled": 0}, pluck="name")
		return {"print_formats": ["Standard", *rows]}, False

	def tool_list_reports(self, query: str):
		rows = frappe.get_all(
			"Report",
			filters={
				"report_type": ["in", ["Query Report", "Script Report"]],
				"name": ["like", f"%{query}%"],
				"disabled": 0,
			},
			fields=["name", "ref_doctype", "report_type"],
			limit=20,
		)
		return {"reports": [r for r in rows if frappe.has_permission("Report", "read", r.name)]}, False

	def tool_validate_expression(self, expression: str, kind: str = "template", at_node: str | None = None):
		problem = (
			expressions.check_condition(expression)
			if kind == "condition"
			else expressions.check_template(expression)
		)
		spec, _revision, _run_as = self.draft()
		nodes = specs.all_nodes(spec)
		issues = [problem] if problem else []
		available = []
		if at_node:
			if at_node not in nodes:
				issues.append(f"There is no step {at_node}.")
			else:
				available = [r["value"] for r in api.get_references(self.automation, at_node)][:80]
				before = {value.split(".")[1] for value in available if value.startswith("nodes.")}
				for ref in expressions.references(expression):
					if ref not in before:
						issues.append(f"nodes.{ref} is not available at {at_node}.")
		return {"ok": not issues, "problems": issues, "available": available}, False

	# --- tools that change things or end the turn -------------------------------------------

	def tool_apply_changes(self, ops: list, summary: str = ""):
		# Models sometimes send an operation (or the whole list) as JSON text; accept that.
		if isinstance(ops, str):
			ops = frappe.parse_json(ops)
		ops = [frappe.parse_json(op) if isinstance(op, str) else op for op in ops or []]
		_spec, revision, _run_as = self.draft()
		result = api.apply_ops(self.automation, revision, ops, source="ai", summary=summary or None)
		if result.get("conflict"):
			spec, revision, run_as = self.draft()
			return {
				"ok": False,
				"error": "The draft changed meanwhile (someone edited the canvas). "
				"Here is the current draft; "
				"redo your change on it.",
				"draft": compact_spec(spec),
				"revision": revision,
			}, False
		if not result.get("ok"):
			return {"ok": False, "error": result.get("error")}, False
		self.changed = True
		return {
			"ok": True,
			"revision": result["revision"],
			"draft": compact_spec(result["spec"]),
			**split_issues(result["validation"]),
		}, False

	def tool_ask_user(self, question: str, choices: list | None = None):
		choices = [str(c)[:80] for c in (choices or []) if str(c).strip()][:4]
		self.say(question.strip(), "question", choices or None)
		return {"ok": True, "asked": True}, True


# ---------------------------------------------------------------------------
# Jobs and endpoints


def respond(automation: str, conversation: str, user: str, focus_node: str | None = None):
	"""Background job: answer the latest admin message in an automation's builder chat."""
	previous = frappe.session.user
	frappe.set_user(user)
	turn = Turn(automation, conversation, focus_node)
	try:
		turn.run()
	except Exception as error:
		if not runtime.sandboxed():
			frappe.db.rollback()
		if not isinstance(error, gateway.LLMError | runtime.BudgetExceeded):
			frappe.log_error(
				title=f"Automation architect {conversation} failed",
				reference_doctype=DOCTYPE,
				reference_name=conversation,
			)
		post(conversation, "assistant", runtime._friendly_error(error), "error")
	finally:
		values = frappe.db.get_value(DOCTYPE, conversation, ["llm_calls", "total_tokens"], as_dict=True) or {}
		frappe.db.set_value(
			DOCTYPE,
			conversation,
			{
				"working": 0,
				"last_activity": now_datetime(),
				"llm_calls": (values.get("llm_calls") or 0) + turn.llm_calls,
				"total_tokens": (values.get("total_tokens") or 0) + turn.usage.total_tokens,
			},
			update_modified=False,
		)
		frappe.set_user(previous)
	runtime._commit()
	publish(automation)


@frappe.whitelist()
def get_chat(name: str) -> dict:
	frappe.get_doc("Automation", name).check_permission("read")
	conversation = conversation_for(name, create=False)
	if not conversation:
		return {"messages": [], "working": False, "model": bool(guards.settings().architect_model)}
	rows = messages(conversation)
	return {
		"messages": [
			{
				"role": m.role,
				"kind": m.kind,
				"content": m.content,
				"choices": json.loads(m.choices_json) if m.choices_json else None,
				"posted_at": m.posted_at,
			}
			for m in rows
		],
		"working": bool(frappe.db.get_value(DOCTYPE, conversation, "working")),
		"model": bool(guards.settings().architect_model),
	}


@frappe.whitelist(methods=["POST"])
def send_message(name: str, text: str, focus_node: str | None = None) -> dict:
	doc = frappe.get_doc("Automation", name)
	doc.check_permission("write")
	text = (text or "").strip()
	if not text:
		frappe.throw(_("Type a message."))
	if len(text) > 4000:
		frappe.throw(_("Please keep messages under 4,000 characters."))
	if not guards.settings().architect_model:
		frappe.throw(
			_("No AI model is set for the architect. An administrator can choose one in Automation Settings.")
		)
	conversation = conversation_for(name)
	if frappe.db.get_value(DOCTYPE, conversation, "working"):
		frappe.throw(_("The architect is still working on your last message."))
	post(conversation, "user", text)
	frappe.db.set_value(
		DOCTYPE, conversation, {"working": 1, "last_activity": now_datetime()}, update_modified=False
	)
	if frappe.flags.in_test or frappe.flags.architect_inline:
		# Tests and the live eval run the turn right away instead of in a worker.
		respond(name, conversation, frappe.session.user, focus_node)
	else:
		frappe.enqueue(
			"pridict.automation.architect.respond",
			queue="long",
			timeout=MAX_RUNTIME_S + 120,
			job_id=f"automation-architect::{conversation}",
			deduplicate=True,
			enqueue_after_commit=True,
			automation=name,
			conversation=conversation,
			user=frappe.session.user,
			focus_node=focus_node,
		)
	publish(name)
	return {"conversation": conversation}
