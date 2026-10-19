"""Node implementations for the Procurement Sourcing workflow (registry.WORKFLOWS).

Every function name matches a node id. Each receives the graph state and the
RunContext and returns a partial state update. Nodes with several outgoing edges
set "route" to the edge condition they chose.

Division of labour:
- The LLM reads and writes language: parsing the request, weighing suppliers,
  explaining the outcome. Its answers are constrained by JSON schemas.
- Code does every number (stock, shortage, value, limits) and every policy check.
  Figures in LLM output are overwritten with the computed ones.

The run is a conversation with the buyer. Pausing nodes put the buyer-facing text in
the interrupt payload ("chat", "card", "choices"); finishing nodes set "reply". When
the item or a supplier does not exist, the agent drafts it, asks the buyer to confirm,
and creates it with a master-data tool, instead of sending the buyer to do it by hand.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypedDict

import frappe
from frappe import _
from frappe.utils import add_days, flt, fmt_money, get_fullname, getdate, nowdate

from pridict.agent_studio import registry, tools
from pridict.agent_studio.runtime import BudgetExceeded, RunContext

MAX_QUESTIONS = 6
COMMON_UOMS = ["Nos", "Unit", "Pair", "Set", "Box", "Pack", "Kg", "Gram", "Litre", "Meter"]


class State(TypedDict, total=False):
	run: str
	request: str
	requirement: dict
	record: dict
	missing: list
	question: str
	asks: int
	conversation: list
	route: str
	stock: dict
	open_orders: list
	usable_open_qty: float
	shortage_qty: float
	suppliers: list
	excluded: list
	price_history: dict
	candidates: list
	analysis: dict
	rate: float
	estimate: float
	policy_results: list
	risk: str
	required_approvals: int
	approval_roles: list
	recommendation: dict
	approval: str
	reviewed: list
	decision: dict
	rfq: str
	outcome: str
	final_status: str
	result: dict
	# Conversation
	choices: list
	answered_by: str
	reply: str
	reply_card: dict
	missing_item: str
	item_proposal: dict
	item_options: dict
	similar_items: list
	item_feedback: str
	supplier_suggestions: list
	supplier_plan: list
	supplier_feedback: str
	created: list
	revalidation_note: str


def _str(schema_title: str, properties: dict) -> dict:
	return {
		"title": schema_title,
		"type": "object",
		"properties": properties,
		"required": list(properties),
		"additionalProperties": False,
	}


REQUIREMENT_SCHEMA = _str(
	"requirement",
	{
		"item_query": {"type": "string", "description": "Item code or name as the buyer wrote it"},
		"qty": {"type": "number", "description": "Quantity; 0 if not stated"},
		"uom": {"type": "string", "description": "Unit of measure as written; empty if not stated"},
		"warehouse": {"type": "string", "description": "Receiving warehouse as written; empty if not stated"},
		"need_by": {"type": "string", "description": "YYYY-MM-DD, or empty if not stated"},
		"company": {"type": "string", "description": "Company if stated, else empty"},
	},
)


def _num(value: float) -> str:
	return f"{flt(value):,.3f}".rstrip("0").rstrip(".")


def _money(value: float, company: str | None) -> str:
	currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
	return fmt_money(value, currency=currency)


def _facts(**values) -> str:
	return json.dumps(values, default=str, ensure_ascii=False, indent=1)


def _answer(resume) -> tuple[str, str]:
	"""(text, user) from an interrupt resume value."""
	if isinstance(resume, dict):
		return str(resume.get("answer") or "").strip(), resume.get("by") or ""
	return str(resume or "").strip(), ""


def _quick(text: str, choices: list[str]) -> str | None:
	"""The quick-reply button the buyer clicked (or typed exactly), if any."""
	normal = text.strip().rstrip(".!").lower()
	return next((c for c in choices if c.lower() == normal), None)


def _label(name: str, code: str) -> str:
	return name if not code or name == code else f"{name} ({code})"


def _and(names: list[str]) -> str:
	names = list(names)
	return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " " + _("and") + " " + names[-1]


def _check_questions(state: State):
	if (state.get("asks") or 0) >= MAX_QUESTIONS:
		raise BudgetExceeded(
			_("Stopped after {0} questions without enough information.").format(MAX_QUESTIONS)
		)


def _master(ctx: RunContext, state: State, name: str, **arguments) -> dict:
	"""Run a master-data tool with the buyer's chat confirmation."""
	ctx.step_tools.append(name)
	confirmation = {"run": ctx.run, "by": state.get("answered_by") or ctx.requested_by}
	outcome = tools.run_tool(name, arguments, confirmation=confirmation)
	if not outcome["ok"]:
		raise tools.ToolError(_("{0} failed: {1}").format(name, outcome["error"]))
	return outcome["result"]


# ---------------------------------------------------------------------------
# Understanding the request


def parse_requirement(state: State, ctx: RunContext) -> dict:
	response = ctx.llm(
		[
			{
				"role": "user",
				"content": (
					f"Today is {nowdate()}. Extract the purchase requirement from the buyer's request. "
					"Use an empty string or 0 for anything not stated; never guess. Resolve dates such as "
					"'30 October' to the next such date in YYYY-MM-DD.\n\nRequest:\n" + state["request"]
				),
			}
		],
		response_schema=REQUIREMENT_SCHEMA,
		max_tokens=1024,
	)
	requirement = response.json()
	ctx.note(
		_("Extracted '{0}', qty {1} {2}, warehouse '{3}', need-by {4}").format(
			requirement["item_query"],
			_num(requirement["qty"]),
			requirement["uom"] or "-",
			requirement["warehouse"] or "-",
			requirement["need_by"] or "-",
		),
		requirement,
	)
	return {
		"requirement": requirement,
		"asks": state.get("asks", 0),
		"conversation": state.get("conversation", []),
	}


def resolve_records(state: State, ctx: RunContext) -> dict:
	requirement = state["requirement"]
	record: dict[str, Any] = {}
	missing: list[str] = []
	choices: list[str] = []
	new_item = ""

	query = (requirement.get("item_query") or "").strip()
	if not query:
		missing.append(_("Which item do you need?"))
	else:
		items = ctx.tool("search_items", query=query, limit=5)["items"]
		exact = [
			i for i in items if query.lower() in (i["item_code"].lower(), (i["item_name"] or "").lower())
		]
		choice = exact[0] if len(exact) == 1 else (items[0] if len(items) == 1 else None)
		if not items and ctx.policy("create_missing_master_data"):
			new_item = query
		elif not items:
			missing.append(_("I could not find an item matching '{0}'. What is the item code?").format(query))
		elif not choice:
			options = ", ".join(f"{i['item_code']} ({i['item_name']})" for i in items)
			missing.append(_("Which item do you mean: {0}?").format(options))
			choices = [i["item_code"] for i in items]
		else:
			record.update(
				item_code=choice["item_code"], item_name=choice["item_name"], stock_uom=choice["stock_uom"]
			)

	wanted = (requirement.get("warehouse") or "").strip()
	company = (requirement.get("company") or "").strip() or frappe.defaults.get_user_default("Company")
	if not wanted:
		missing.append(_("Which warehouse should receive it?"))
		if company:
			choices = [w["name"] for w in ctx.tool("get_warehouses", company=company)["warehouses"][:8]]
	elif frappe.db.exists("Warehouse", wanted) and frappe.has_permission("Warehouse", "read", wanted):
		record.update(warehouse=wanted, company=frappe.db.get_value("Warehouse", wanted, "company"))
	elif company:
		warehouses = ctx.tool("get_warehouses", company=company)["warehouses"]
		matches = [w["name"] for w in warehouses if wanted.lower() in w["name"].lower()]
		if len(matches) == 1:
			record.update(warehouse=matches[0], company=company)
		elif matches:
			missing.append(_("Which warehouse do you mean: {0}?").format(", ".join(matches[:8])))
			choices = matches[:8]
		else:
			missing.append(
				_("I could not find warehouse '{0}' in {1}. Which warehouse?").format(wanted, company)
			)
	else:
		missing.append(_("I could not find warehouse '{0}'. Which warehouse?").format(wanted))

	found = ", ".join(f"{k}={v}" for k, v in record.items() if k in ("item_code", "warehouse", "company"))
	if new_item:
		ctx.note(_("No item matches '{0}'; offering to create one").format(new_item), record)
		return {"route": "new item", "missing_item": new_item, "record": record, "missing": missing}
	ctx.note(
		_("Resolved {0}").format(found or "-") + (f"; {len(missing)} open question(s)" if missing else ""),
		record,
	)
	# Quick replies only make sense when there is exactly one question.
	return {
		"route": "found",
		"record": record,
		"missing": missing,
		"choices": choices if len(missing) == 1 else [],
	}


def _conversion_factor(item_code: str, uom: str, stock_uom: str) -> float | None:
	if not uom or uom.lower() == stock_uom.lower():
		return 1.0
	for row in frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": item_code, "parenttype": "Item"},
		fields=["uom", "conversion_factor"],
	):
		if row.uom.lower() == uom.lower():
			return flt(row.conversion_factor)
	return None


def validate_inputs(state: State, ctx: RunContext) -> dict:
	requirement, record = state["requirement"], dict(state["record"])
	missing = list(state.get("missing") or [])
	results = []

	qty = flt(requirement.get("qty"))
	if qty <= 0:
		missing.append(_("How much do you need?"))

	need_by = (requirement.get("need_by") or "").strip()
	if not need_by:
		missing.append(_("By what date do you need it?"))
	else:
		try:
			need_by_date = getdate(need_by)
		except Exception:
			need_by_date = None
			missing.append(_("I could not read the date '{0}'. By what date do you need it?").format(need_by))
		if need_by_date and need_by_date < getdate(nowdate()) and ctx.policy("need_by_not_past"):
			missing.append(_("The need-by date {0} has passed. When do you need it?").format(need_by))
		elif need_by_date:
			record["need_by"] = str(need_by_date)

	if record.get("item_code") and qty > 0:
		uom = (requirement.get("uom") or "").strip() or record["stock_uom"]
		factor = _conversion_factor(record["item_code"], uom, record["stock_uom"])
		if factor is None:
			missing.append(
				_("I cannot convert {0} to {1} for this item. How many {1} do you need?").format(
					uom, record["stock_uom"]
				)
			)
		else:
			record.update(qty=qty, uom=uom, conversion_factor=factor, required_stock_qty=qty * factor)

	for rule_key, field, label in (
		("permitted_companies", "company", _("company")),
		("permitted_warehouses", "warehouse", _("warehouse")),
	):
		policy = ctx.policy(rule_key)
		allowed = (policy.parameters.get(rule_key.split("_", 1)[1]) if policy else None) or []
		if allowed and record.get(field) and record[field] not in allowed:
			missing.append(
				_("{0} is not a permitted {1} for this agent. Choose one of: {2}.").format(
					record[field], label, ", ".join(allowed)
				)
			)
		elif policy:
			results.append({"rule": policy.policy_name, "result": "PASS", "detail": record.get(field) or "-"})

	if not missing:
		if not frappe.has_permission("Request for Quotation", "create"):
			raise tools.ToolError(
				_(
					"{0} may not create Requests for Quotation, so the agent cannot help with sourcing."
				).format(ctx.requested_by)
			)
		if record.get("company") and not frappe.has_permission("Company", "read", record["company"]):
			raise tools.ToolError(
				_("{0} has no access to company {1}.").format(ctx.requested_by, record["company"])
			)

	if missing:
		_check_questions(state)
		questions = list(dict.fromkeys(missing))
		question = "\n".join(questions)
		ctx.note(_("Missing information: {0}").format(question.replace("\n", " ")))
		choices = (state.get("choices") or []) if len(questions) == 1 else []
		return {"route": "missing data", "question": question, "record": record, "choices": choices}

	if ctx.policy("required_fields"):
		results.append(
			{
				"rule": ctx.policy("required_fields").policy_name,
				"result": "PASS",
				"detail": _("All required fields present"),
			}
		)
	if ctx.policy("need_by_not_past"):
		results.append(
			{
				"rule": ctx.policy("need_by_not_past").policy_name,
				"result": "PASS",
				"detail": record["need_by"],
			}
		)
	ctx.note(
		_("Valid: {0} {1} of {2} into {3} by {4}").format(
			_num(record["required_stock_qty"]),
			record["stock_uom"],
			record["item_code"],
			record["warehouse"],
			record["need_by"],
		),
		record,
	)
	return {"route": "valid", "record": record, "policy_results": results, "question": ""}


def ask_buyer(state: State, ctx: RunContext) -> dict:
	from langgraph.types import interrupt

	question = state.get("question") or _("Can you give more detail?")
	ctx.note(_("Asked the buyer: {0}").format(question.replace("\n", " ")))
	text, _by = _answer(
		interrupt({"type": "question", "message": question, "choices": state.get("choices") or []})
	)

	conversation = [*(state.get("conversation") or []), {"question": question, "answer": text}]
	response = ctx.llm(
		[
			{
				"role": "user",
				"content": (
					f"Today is {nowdate()}. Update the purchase requirement with the buyer's answer. "
					"Keep fields the answer does not change. Never guess.\n\n"
					f"Original request:\n{state['request']}\n\nCurrent requirement:\n{_facts(**state['requirement'])}\n\n"
					f"Question asked:\n{question}\n\nBuyer's answer:\n{text}"
				),
			}
		],
		response_schema=REQUIREMENT_SCHEMA,
		max_tokens=1024,
	)
	requirement = response.json()
	ctx.note(_("Buyer answered: {0}").format(text), requirement)
	return {
		"requirement": requirement,
		"asks": (state.get("asks") or 0) + 1,
		"conversation": conversation,
		"choices": [],
	}


# ---------------------------------------------------------------------------
# Creating a missing item


def _item_options() -> dict:
	groups = frappe.get_all(
		"Item Group", filters={"is_group": 0}, pluck="name", order_by="name asc", limit=80
	)
	used = frappe.get_all(
		"Item",
		fields=["stock_uom", "count(name) as n"],
		group_by="stock_uom",
		order_by="n desc",
		limit=20,
	)
	wanted = list(dict.fromkeys([*(u.stock_uom for u in used if u.stock_uom), *COMMON_UOMS]))
	uoms = frappe.get_all("UOM", filters={"name": ["in", wanted], "enabled": 1}, pluck="name")
	return {"groups": groups, "uoms": sorted(uoms, key=wanted.index)}


def _item_schema(title: str, options: dict, extra: dict | None = None) -> dict:
	return _str(
		title,
		{
			**(extra or {}),
			"item_name": {"type": "string", "description": "Short, clear, singular item name in title case"},
			"item_group": {"type": "string", "enum": options["groups"]},
			"stock_uom": {"type": "string", "enum": options["uoms"]},
			"is_stock_item": {"type": "boolean", "description": "True for physical goods kept in stock"},
			"description": {"type": "string"},
		},
	)


def propose_item(state: State, ctx: RunContext) -> dict:
	query = state["missing_item"]
	similar: dict[str, dict] = {}
	# Look for near misses ("laptops" vs "Laptop 14in") one word at a time.
	for word in list(dict.fromkeys(w.rstrip("s") for w in re.findall(r"[\w-]{3,}", query.lower())))[:4]:
		for item in ctx.tool("search_items", query=word, limit=5)["items"]:
			similar.setdefault(item["item_code"], item)
	similar_items = list(similar.values())[:5]

	options = _item_options()
	if not options["groups"] or not options["uoms"]:
		raise tools.ToolError(_("ERPNext has no item groups or units set up, so I cannot create items."))
	proposal = ctx.llm(
		[
			{
				"role": "user",
				"content": (
					"The buyer asked to purchase something that is not in the item master. Draft a new item for them "
					"to confirm: a clear singular name, the best matching item group and stock unit from the lists, "
					"and whether it is a physical good kept in stock (false for services).\n\n"
					f"Buyer's request:\n{state['request']}\n\nItem as written: {query}"
				),
			}
		],
		response_schema=_item_schema("item_proposal", options),
		max_tokens=512,
	).json()
	ctx.note(
		_("Proposed new item {0} ({1}, {2}); {3} similar item(s)").format(
			proposal["item_name"], proposal["item_group"], proposal["stock_uom"], len(similar_items)
		),
		{"proposal": proposal, "similar": similar_items},
	)
	return {
		"item_proposal": proposal,
		"item_options": options,
		"similar_items": similar_items,
		"item_feedback": "",
	}


def _item_card(proposal: dict, alternative: bool = False) -> dict:
	return {
		"title": _("Or create a new item") if alternative else _("New item"),
		"fields": [
			[_("Name"), proposal["item_name"]],
			[_("Item group"), proposal["item_group"]],
			[_("Unit"), proposal["stock_uom"]],
			[_("Kept in stock"), _("Yes") if proposal["is_stock_item"] else _("No")],
		],
	}


def confirm_item(state: State, ctx: RunContext) -> dict:
	from langgraph.types import interrupt

	_check_questions(state)
	proposal, similar = state["item_proposal"], state.get("similar_items") or []
	stop = _("Cancel request")
	lines = [
		state.get("item_feedback") or _('I couldn\'t find "{0}" in your items.').format(state["missing_item"])
	]
	# An item with exactly the proposed name already exists: steer towards it, not a duplicate.
	same = next((i for i in similar if i["item_name"].lower() == proposal["item_name"].lower()), None)
	if same:
		similar = [same, *[i for i in similar if i is not same]]
	# Buttons show item names; map them back to codes.
	use = {_("Use {0}").format(i["item_name"]): i["item_code"] for i in similar[:4]}
	if same:
		create = _("Create a separate new item")
		lines.append(
			_("You already have an item called {0}. Shall I use it?").format(
				_label(same["item_name"], same["item_code"])
			)
		)
	elif len(similar) == 1:
		create = _("No, create a new item")
		lines.append(
			_("Did you mean {0}? If not, I can create a new item for it.").format(
				_label(similar[0]["item_name"], similar[0]["item_code"])
			)
		)
	elif similar:
		create = _("None of these, create it")
		lines.append(
			_("Did you mean one of these? {0}").format(
				", ".join(_label(i["item_name"], i["item_code"]) for i in similar)
			)
		)
		lines.append(_("If not, I can create a new item for it."))
	else:
		create = _("Yes, create it")
		lines.append(_("I can create it as a new item. Shall I? You can also change any of the details."))
	question = "\n".join(lines)
	ctx.note(_("Asked the buyer to confirm new item {0}").format(proposal["item_name"]))
	text, by = _answer(
		interrupt(
			{
				"type": "question",
				"message": question,
				"card": _item_card(proposal, alternative=bool(similar)),
				# With an exact-name match, "create anyway" sits right after it, before other near misses.
				"choices": [*list(use)[:1], create, *list(use)[1:], stop] if same else [*use, create, stop],
			}
		)
	)
	asks = (state.get("asks") or 0) + 1
	conversation = [*(state.get("conversation") or []), {"question": question, "answer": text}]
	common = {"asks": asks, "conversation": conversation, "answered_by": by}
	codes = [i["item_code"] for i in similar]

	quick = _quick(text, [create, stop, *use, *codes])
	if quick == create:
		decision = {"action": "create", **proposal}
	elif quick == stop:
		decision = {"action": "stop"}
	elif quick:
		decision = {"action": "use_existing", "existing_item": use.get(quick, quick)}
	else:
		decision = ctx.llm(
			[
				{
					"role": "user",
					"content": (
						"You asked the buyer to confirm a new item. Decide what the buyer wants:\n"
						"- create: they agree to create it (apply any changes they asked for to the fields)\n"
						"- use_existing: they picked one of the similar existing items (give its code)\n"
						"- stop: they do not want to continue\n"
						"- unclear: anything else (apply any changes they mentioned to the fields)\n"
						"If the question asked whether they meant an existing item and they simply agree "
						"('yes', 'that one'), choose use_existing with that item. If it only offered to create, "
						"'yes' means create.\n\n"
						+ _facts(
							question=question, proposal=proposal, similar_items=similar, buyer_answer=text
						)
					),
				}
			],
			response_schema=_item_schema(
				"item_answer",
				state["item_options"],
				{
					"action": {"type": "string", "enum": ["create", "use_existing", "stop", "unclear"]},
					"existing_item": {"type": "string", "enum": ["", *codes]},
				},
			),
			max_tokens=512,
		).json()

	action = decision.get("action")
	updated = (
		{k: decision.get(k, proposal[k]) for k in proposal} if action in ("create", "unclear") else proposal
	)
	ctx.note(_("Buyer answered: {0} → {1}").format(text, action), decision)
	if action == "create":
		return {**common, "item_proposal": updated, "route": "create"}
	if action == "use_existing" and decision.get("existing_item") in codes:
		requirement = {**state["requirement"], "item_query": decision["existing_item"]}
		return {**common, "requirement": requirement, "route": "use existing"}
	if action == "stop":
		return {**common, "route": "stop"}
	return {
		**common,
		"item_proposal": updated,
		"item_feedback": _("I've updated the details.")
		if updated != proposal
		else _("Sorry, I didn't quite get that."),
		"route": "change",
	}


def create_item(state: State, ctx: RunContext) -> dict:
	proposal = state["item_proposal"]
	created = _master(
		ctx,
		state,
		"create_item",
		item_name=proposal["item_name"],
		item_group=proposal["item_group"],
		stock_uom=proposal["stock_uom"],
		is_stock_item=bool(proposal["is_stock_item"]),
		description=proposal.get("description") or "",
	)
	ctx.note(_("Created item {0}").format(created["item_code"]), created)
	ctx.say(
		_("Done. I created the item {0}.").format(_label(created["item_name"], created["item_code"])),
		"notice",
	)
	return {
		"requirement": {**state["requirement"], "item_query": created["item_code"]},
		"created": [*(state.get("created") or []), {"doctype": "Item", "name": created["item_code"]}],
	}


# ---------------------------------------------------------------------------
# Supply and shortage


def read_supply(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	stock = ctx.tool("get_stock_balance", item_code=record["item_code"], warehouse=record["warehouse"])
	orders = ctx.tool(
		"get_open_purchase_orders",
		item_code=record["item_code"],
		warehouse=record["warehouse"],
		before_date=record["need_by"],
	)["orders"]
	ctx.note(
		_("Stock {0} {1}; {2} open order(s) due by {3}: {4} {1}").format(
			_num(stock["actual_qty"]),
			record["stock_uom"],
			len(orders),
			record["need_by"],
			_num(sum(o["pending_qty"] for o in orders)),
		),
		{"stock": stock, "orders": orders},
	)
	return {"stock": stock, "open_orders": orders}


def calc_shortage(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	required = flt(record["required_stock_qty"])
	actual = max(flt(state["stock"]["actual_qty"]), 0)
	usable = sum(flt(o["pending_qty"]) for o in state["open_orders"])
	shortage = round(max(required - actual - usable, 0), 6)
	ctx.note(f"{_num(required)} − {_num(actual)} − {_num(usable)} = {_num(shortage)} {record['stock_uom']}")
	return {"usable_open_qty": usable, "shortage_qty": shortage}


def shortage_router(state: State, ctx: RunContext) -> dict:
	route = "yes" if state["shortage_qty"] > 0 else "no"
	ctx.note(_("Shortage {0} → {1}").format(_num(state["shortage_qty"]), route))
	return {"route": route}


def explain_no_purchase(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	facts = _facts(
		item=record["item_name"],
		required=record["required_stock_qty"],
		uom=record["stock_uom"],
		in_stock=state["stock"]["actual_qty"],
		open_orders=state["open_orders"],
		need_by=record["need_by"],
	)
	text = (
		ctx.llm(
			[
				{
					"role": "user",
					"content": "In two or three plain sentences, tell the buyer that no purchase is needed and why, using only these facts:\n"
					+ facts,
				}
			],
			max_tokens=400,
		).content
		or ""
	).strip()
	ctx.note(text)
	return {
		"outcome": _("No purchase needed: stock and open orders cover {0} {1}.").format(
			_num(record["required_stock_qty"]), record["stock_uom"]
		),
		"final_status": "Completed",
		"result": {"recommended_action": "no_purchase", "shortage_qty": 0, "explanation": text},
	}


# ---------------------------------------------------------------------------
# Suppliers and analysis


def find_suppliers(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	approved = ctx.tool("get_approved_suppliers", item_code=record["item_code"])["suppliers"]
	strict = ctx.policy("approved_suppliers_only")
	eligible, excluded = [], []
	for supplier in approved:
		if supplier["on_hold"] and strict:
			excluded.append({"supplier": supplier["supplier"], "reason": _("on hold")})
		else:
			eligible.append(dict(supplier))

	if eligible:
		scores = {
			s["supplier"]: s
			for s in ctx.tool("score_vendors", suppliers=[s["supplier"] for s in eligible])["scores"]
		}
		minimum = ctx.policy("min_vendor_score")
		min_score = flt(minimum.parameters.get("min_score")) if minimum else 0
		kept = []
		for supplier in eligible:
			score = scores.get(supplier["supplier"], {})
			supplier.update(
				score=score.get("score"), tier=score.get("tier"), risk_flags=score.get("risk_flags") or []
			)
			if min_score and supplier["score"] is not None and supplier["score"] < min_score:
				excluded.append(
					{
						"supplier": supplier["supplier"],
						"reason": _("score {0} below {1}").format(supplier["score"], _num(min_score)),
					}
				)
			else:
				kept.append(supplier)
		eligible = kept

	if not eligible and ctx.policy("create_missing_master_data"):
		if excluded:
			intro = _("The suppliers set up for {0} can't be used right now ({1}).").format(
				record["item_name"], "; ".join(f"{e['supplier']}: {e['reason']}" for e in excluded)
			)
		else:
			intro = _("{0} doesn't have any suppliers set up yet.").format(record["item_name"])
		question = (
			intro
			+ " "
			+ _(
				"Which supplier should I ask for a quote? Name one you already buy from or a new one (add their email if you have it)."
			)
		)
		suggestions = _supplier_suggestions(record["item_code"], [e["supplier"] for e in excluded])
		ctx.note(question, {"excluded": excluded, "suggestions": suggestions})
		return {
			"route": "no supplier",
			"question": question,
			"suppliers": [],
			"excluded": excluded,
			"supplier_suggestions": suggestions,
			"supplier_plan": [],
			"supplier_feedback": "",
		}

	if not eligible:
		reasons = "; ".join(f"{e['supplier']}: {e['reason']}" for e in excluded) or _(
			"none are listed on the item"
		)
		question = _(
			"No approved supplier is available for {0} ({1}). Add suppliers to the item's Supplier list in ERPNext and reply 'done', or tell me what to change."
		).format(record["item_code"], reasons)
		ctx.note(question)
		return {"route": "not enough", "question": question, "suppliers": [], "excluded": excluded}

	ctx.note(
		_("{0} eligible: {1}").format(
			len(eligible),
			", ".join(
				f"{s['supplier']} ({s['score'] if s['score'] is not None else 'no history'})"
				for s in eligible
			),
		)
		+ (_("; excluded {0}").format(", ".join(e["supplier"] for e in excluded)) if excluded else ""),
		{"eligible": eligible, "excluded": excluded},
	)
	return {"route": "enough data", "suppliers": eligible, "excluded": excluded}


def _supplier_suggestions(item_code: str, exclude: list[str]) -> list[str]:
	"""Suppliers of other items in the same group, else the most used suppliers overall."""
	group = frappe.db.get_value("Item", item_code, "item_group")
	rows = frappe.db.sql(
		"""
		select isup.supplier, count(*) as n
		from `tabItem Supplier` isup
		join `tabItem` i on i.name = isup.parent and isup.parenttype = 'Item'
		join `tabSupplier` s on s.name = isup.supplier
		where i.item_group = %(group)s and s.disabled = 0 and s.on_hold = 0
		group by isup.supplier order by n desc limit 8
		""",
		{"group": group},
		as_dict=True,
	)
	names = [r.supplier for r in rows]
	if len(names) < 3:
		names += [
			r.supplier
			for r in frappe.get_all(
				"Purchase Order",
				filters={"docstatus": 1, "transaction_date": [">=", add_days(nowdate(), -365)]},
				fields=["supplier", "count(name) as n"],
				group_by="supplier",
				order_by="n desc",
				limit=8,
			)
		]
	return [n for n in dict.fromkeys(names) if n not in exclude][:4]


def _match_supplier(name: str) -> str | None:
	"""Existing, enabled supplier the buyer meant by this name, if exactly one matches."""
	name = name.strip()
	for field in ("name", "supplier_name"):
		found = frappe.db.get_value("Supplier", {field: name, "disabled": 0}, "name")
		if found:
			return found
	matches = frappe.get_all(
		"Supplier", filters={"supplier_name": ["like", f"%{name}%"], "disabled": 0}, pluck="name", limit=2
	)
	return matches[0] if len(matches) == 1 else None


def _supplier_card(plan: list[dict], item_name: str) -> dict:
	return {
		"title": _("Suppliers for {0}").format(item_name),
		"fields": [
			[
				p["name"],
				(_("New supplier") + (f" · {p['email']}" if p.get("email") else ""))
				if p["new"]
				else _("Existing supplier"),
			]
			for p in plan
		],
	}


SUPPLIER_ANSWER_SCHEMA = _str(
	"supplier_answer",
	{
		"action": {"type": "string", "enum": ["confirm", "use", "stop", "unclear"]},
		"suppliers": {
			"type": "array",
			"items": {
				"type": "object",
				"properties": {"name": {"type": "string"}, "email": {"type": "string"}},
				"required": ["name", "email"],
				"additionalProperties": False,
			},
		},
	},
)


def confirm_supplier(state: State, ctx: RunContext) -> dict:
	from langgraph.types import interrupt

	_check_questions(state)
	record = state["record"]
	plan = state.get("supplier_plan") or []
	go, stop = _("Yes, go ahead"), _("Cancel request")
	suggestions = state.get("supplier_suggestions") or []
	if plan:
		new = [p["name"] for p in plan if p["new"]]
		question = _("{0} isn't one of your suppliers yet. I'll create it and add it to {1}.").format(
			_and(new), record["item_name"]
		)
		if len(new) > 1:
			question = _("{0} aren't among your suppliers yet. I'll create them and add them to {1}.").format(
				_and(new), record["item_name"]
			)
		if len(plan) > len(new):
			question += " " + _("The others are already set up and will be added too.")
		question += " " + _("Shall I go ahead?")
		choices, card = [go, stop], _supplier_card(plan, record["item_name"])
	else:
		question = state["question"]
		choices, card = [*suggestions, stop], None
	if state.get("supplier_feedback"):
		question = f"{state['supplier_feedback']} {question}"
	ctx.note(_("Asked the buyer about suppliers"), {"plan": plan, "suggestions": suggestions})
	text, by = _answer(interrupt({"type": "question", "message": question, "card": card, "choices": choices}))
	asks = (state.get("asks") or 0) + 1
	conversation = [*(state.get("conversation") or []), {"question": question, "answer": text}]
	common = {"asks": asks, "conversation": conversation, "answered_by": by, "supplier_feedback": ""}

	quick = _quick(text, choices)
	if quick == stop:
		decision = {"action": "stop", "suppliers": []}
	elif quick == go:
		decision = {"action": "confirm", "suppliers": []}
	elif quick:
		decision = {"action": "use", "suppliers": [{"name": quick, "email": ""}]}
	else:
		decision = ctx.llm(
			[
				{
					"role": "user",
					"content": (
						"You are helping the buyer choose suppliers to ask for a quotation. Decide what the buyer wants:\n"
						"- confirm: they agree to the current plan as shown\n"
						"- use: they name suppliers; return the complete list they want now, with an email when they give one\n"
						"- stop: they do not want to continue\n"
						"- unclear: anything else\n\n"
						+ _facts(
							item=record["item_name"], question=question, current_plan=plan, buyer_answer=text
						)
					),
				}
			],
			response_schema=SUPPLIER_ANSWER_SCHEMA,
			max_tokens=512,
		).json()

	action = decision.get("action")
	ctx.note(_("Buyer answered: {0} → {1}").format(text, action), decision)
	if action == "stop":
		return {**common, "route": "stop"}
	if action == "confirm" and plan:
		return {**common, "route": "ready"}
	named = [s for s in decision.get("suppliers") or [] if (s.get("name") or "").strip()]
	same = {s["name"].strip().lower() for s in named} == {p["name"].lower() for p in plan}
	if plan and action == "use" and same:
		# Restating the suppliers already shown is agreement, not a new plan to confirm again.
		return {**common, "route": "ready"}
	if action in ("use", "confirm") and named:
		plan = []
		for entry in named:
			existing = _match_supplier(entry["name"])
			plan.append(
				{
					"name": existing or entry["name"].strip(),
					"supplier": existing or "",
					"email": (entry.get("email") or "").strip(),
					"new": not existing,
				}
			)
		# Naming existing suppliers is the go-ahead; new ones are confirmed first.
		route = "again" if any(p["new"] for p in plan) else "ready"
		return {**common, "supplier_plan": plan, "route": route}
	return {**common, "supplier_feedback": _("Sorry, I didn't quite get that."), "route": "again"}


def setup_suppliers(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	created = list(state.get("created") or [])
	new, linked = [], []
	for entry in state["supplier_plan"]:
		supplier = entry["supplier"]
		if entry["new"]:
			supplier = _master(
				ctx, state, "create_supplier", supplier_name=entry["name"], email=entry["email"]
			)["supplier"]
			new.append(supplier)
			created.append({"doctype": "Supplier", "name": supplier})
		_master(ctx, state, "link_item_supplier", item_code=record["item_code"], supplier=supplier)
		linked.append(supplier)
	message = _("Done. {0} can now supply {1}.").format(_and(linked), record["item_name"])
	if new:
		message = _("Done. I created the supplier record for {0}, and {1} can now supply {2}.").format(
			_and(new), _and(linked), record["item_name"]
		)
	ctx.note(message, {"created": new, "linked": linked})
	ctx.say(message, "notice")
	return {"supplier_plan": [], "created": created}


def end_conversation(state: State, ctx: RunContext) -> dict:
	ctx.note(_("The buyer stopped the request"))
	return {
		"outcome": _("Stopped by the buyer"),
		"final_status": "Cancelled",
		"reply": _("OK, I've stopped here. Start a new request whenever you're ready."),
		"result": {"recommended_action": "stopped", "created": state.get("created") or []},
	}


def analyze_sourcing(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	history = ctx.tool("get_price_history", item_code=record["item_code"], days=90)
	quotations = ctx.tool("get_supplier_quotations", item_code=record["item_code"], valid_on=nowdate())[
		"quotations"
	]
	last_rates = {row["supplier"]: row for row in history["by_supplier"]}

	candidates = []
	for supplier in state["suppliers"]:
		name = supplier["supplier"]
		quotes = sorted((q for q in quotations if q["supplier"] == name), key=lambda q: q["rate"])
		rate = (
			quotes[0]["rate"]
			if quotes
			else (last_rates.get(name, {}).get("last_rate") or history["avg_rate"] or None)
		)
		anomalies = (
			ctx.tool("detect_price_anomalies", item_code=record["item_code"], proposed_rate=rate)["anomalies"]
			if rate
			else []
		)
		candidates.append(
			{
				**supplier,
				"rate": rate,
				"rate_source": "quotation"
				if quotes
				else ("last purchase" if name in last_rates else ("average" if rate else "none")),
				"quotation": f"{quotes[0]['name']} @ {quotes[0]['rate']} (valid till {quotes[0]['valid_till']})"
				if quotes
				else "",
				"last_rate": last_rates.get(name, {}).get("last_rate"),
				"anomalies": anomalies,
			}
		)

	names = [c["supplier"] for c in candidates]
	schema = _str(
		"sourcing_analysis",
		{
			"recommended_supplier": {"type": "string", "enum": names},
			"supplier_notes": {
				"type": "array",
				"items": _str(
					"note", {"supplier": {"type": "string", "enum": names}, "note": {"type": "string"}}
				),
			},
			"rationale": {"type": "string"},
		},
	)
	schema["properties"]["supplier_notes"]["items"].pop("title")
	response = ctx.llm(
		[
			{
				"role": "user",
				"content": (
					"Compare these eligible suppliers for the shortage below. Weigh price (rate per stock unit, company currency), "
					"lead time against the need-by date, vendor score and tier, and any price anomalies. Recommend one supplier and "
					"write one short note per supplier. Use only these facts.\n\n"
					+ _facts(
						item=record["item_name"],
						shortage_qty=state["shortage_qty"],
						uom=record["stock_uom"],
						need_by=record["need_by"],
						today=nowdate(),
						avg_rate_90d=history["avg_rate"],
						suppliers=candidates,
					)
				),
			}
		],
		response_schema=schema,
		max_tokens=2048,
	)
	analysis = response.json()
	ctx.note(
		_("Recommends {0}: {1}").format(analysis["recommended_supplier"], analysis["rationale"]), analysis
	)
	return {"price_history": history, "candidates": candidates, "analysis": analysis}


def check_limits(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	candidates = {c["supplier"]: c for c in state["candidates"]}
	chosen = candidates.get(state["analysis"]["recommended_supplier"]) or next(iter(candidates.values()))
	avg = flt(state["price_history"].get("avg_rate"))
	rate = flt(chosen.get("rate")) or avg
	estimate = round(state["shortage_qty"] * rate, 2)
	money = lambda v: _money(v, record.get("company"))  # noqa: E731
	results = list(state.get("policy_results") or [])

	def add(rule_key, result, detail):
		policy = ctx.policy(rule_key)
		if policy:
			results.append({"rule": policy.policy_name, "result": result, "detail": detail})

	excluded = state.get("excluded") or []
	add(
		"approved_suppliers_only",
		"PASS",
		_("{0} approved supplier(s) eligible").format(len(candidates))
		+ (
			_("; excluded {0}").format(", ".join(f"{e['supplier']} ({e['reason']})" for e in excluded))
			if excluded
			else ""
		),
	)
	scored = [c["score"] for c in candidates.values() if c.get("score") is not None]
	add(
		"min_vendor_score",
		"PASS",
		_("Lowest included score: {0}").format(min(scored))
		if scored
		else _("No supplier has purchase history yet"),
	)
	watch = [c["supplier"] for c in candidates.values() if c.get("tier") in ("Watchlist", "High Risk")]
	add(
		"watchlist_suppliers",
		"WARN" if watch else "PASS",
		_("On watchlist: {0}").format(", ".join(watch)) if watch else _("None on watchlist"),
	)

	variance = ctx.policy("price_variance")
	if variance:
		tolerance = flt(variance.parameters.get("tolerance_pct") or 10)
		if avg and rate:
			pct = (rate - avg) / avg * 100
			add(
				"price_variance",
				"WARN" if abs(pct) > tolerance else "PASS",
				_("{0} per {1} is {2:+.1f}% vs 90-day average {3}").format(
					money(rate), record["stock_uom"], pct, money(avg)
				),
			)
		else:
			add("price_variance", "WARN", _("No recent purchase price to compare with"))

	sanity = ctx.policy("quantity_sanity")
	if sanity:
		consumed = -sum(
			flt(q)
			for q in frappe.get_all(
				"Stock Ledger Entry",
				filters={
					"item_code": record["item_code"],
					"warehouse": record["warehouse"],
					"is_cancelled": 0,
					"actual_qty": ["<", 0],
					"posting_date": [">=", add_days(nowdate(), -90)],
				},
				pluck="actual_qty",
			)
		)
		monthly = consumed / 3
		multiple = flt(sanity.parameters.get("max_multiple") or 3)
		if monthly > 0:
			too_much = state["shortage_qty"] > multiple * monthly
			add(
				"quantity_sanity",
				"WARN" if too_much else "PASS",
				_("{0} vs {1} × {2} average monthly use").format(
					_num(state["shortage_qty"]), _num(multiple), _num(monthly)
				),
			)
		else:
			add("quantity_sanity", "PASS", _("No consumption in the last 90 days to compare with"))

	ceiling = ctx.policy("hard_ceiling")
	ceiling_value = flt(ceiling.parameters.get("max_value")) if ceiling else 0
	dual = ctx.policy("dual_approval")
	single = ctx.policy("single_approver_limit")
	blocked = bool(ceiling_value and estimate > ceiling_value)
	required, roles = 1, ["Purchase Manager"]
	if blocked:
		add(
			"hard_ceiling",
			"BLOCK",
			_("Estimated {0} is above {1}").format(money(estimate), money(ceiling_value)),
		)
	elif not rate:
		# No quotation and no purchase history: the value is unknown, not zero. Use the
		# strictest approval short of blocking, and say so.
		if dual:
			required, roles = 2, dual.parameters.get("roles") or roles
		results.append(
			{
				"rule": _("Value unknown"),
				"result": "WARN",
				"detail": _("No quotation or purchase history to price this item; needs {0}").format(
					" + ".join(roles)
				),
			}
		)
	else:
		if dual and estimate > flt(dual.parameters.get("min_value")):
			required, roles = 2, dual.parameters.get("roles") or roles
			add(
				"dual_approval",
				"PASS",
				_("Estimated {0} needs {1}").format(money(estimate), " + ".join(roles)),
			)
		elif single:
			roles = single.parameters.get("roles") or roles
			add(
				"single_approver_limit",
				"PASS",
				_("Estimated {0} needs one {1}").format(money(estimate), " / ".join(roles)),
			)
		if ceiling:
			add("hard_ceiling", "PASS", _("Below {0}").format(money(ceiling_value)))
	add("no_submit", "PASS", _("Proposed action creates a Draft RFQ only"))

	warnings = sum(r["result"] == "WARN" for r in results)
	risk = (
		"High" if blocked or not rate or warnings >= 2 or required > 1 else ("Medium" if warnings else "Low")
	)
	ctx.note(
		_("Estimated {0} ({1} × {2}); risk {3}").format(
			money(estimate), _num(state["shortage_qty"]), money(rate), risk
		)
		if rate
		else _("Value unknown: no quotation or purchase history; risk {0}").format(risk),
		results,
	)
	return {
		"route": "above ceiling" if blocked else "within limits",
		"rate": rate,
		"estimate": estimate,
		"policy_results": results,
		"risk": risk,
		"required_approvals": required,
		"approval_roles": roles,
	}


def explain_blocked(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	blocked = [r for r in state["policy_results"] if r["result"] == "BLOCK"]
	text = (
		ctx.llm(
			[
				{
					"role": "user",
					"content": "In two or three plain sentences, tell the buyer that the agent cannot prepare this purchase and what they can do instead "
					"(for example, raise it through the normal approval process). Facts:\n"
					+ _facts(
						item=record["item_name"],
						shortage=state["shortage_qty"],
						uom=record["stock_uom"],
						estimate=state["estimate"],
						blocked_by=blocked,
					),
				}
			],
			max_tokens=400,
		).content
		or ""
	).strip()
	ctx.note(text)
	return {
		"outcome": _("Blocked by policy: {0}").format("; ".join(r["detail"] for r in blocked)),
		"final_status": "Completed",
		"result": {
			"recommended_action": "blocked",
			"shortage_qty": state["shortage_qty"],
			"estimated_value": state["estimate"],
			"explanation": text,
		},
	}


def prepare_recommendation(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	schema = (
		json.loads(ctx.agent.output_schema)
		if ctx.agent.output_schema
		else dict(registry.PROCUREMENT_AGENT_DEFAULTS["output_schema"])
	)
	schema = {"title": "recommendation", **schema}
	response = ctx.llm(
		[
			{
				"role": "user",
				"content": (
					"Write the final sourcing recommendation for the approver. The action is to send a Request for Quotation to the "
					"eligible suppliers. Explain in plain language, citing the evidence. Use only these facts and copy numbers exactly.\n\n"
					+ _facts(
						item=record["item_name"],
						item_code=record["item_code"],
						warehouse=record["warehouse"],
						need_by=record["need_by"],
						required_qty=record["required_stock_qty"],
						in_stock=state["stock"]["actual_qty"],
						usable_open_orders=state["usable_open_qty"],
						shortage_qty=state["shortage_qty"],
						uom=record["stock_uom"],
						estimated_value=state["estimate"],
						suppliers=state["candidates"],
						analysis=state["analysis"],
						policy_results=state["policy_results"],
					)
				),
			}
		],
		response_schema=schema,
		max_tokens=2048,
	)
	recommendation = response.json()
	# Numbers and the chosen supplier come from code and the constrained analysis, not free text.
	names = [c["supplier"] for c in state["candidates"]]
	recommendation["shortage_qty"] = state["shortage_qty"]
	recommendation["estimated_value"] = state["estimate"]
	recommendation["recommended_action"] = "create_rfq"
	if recommendation.get("recommended_supplier") not in names:
		recommendation["recommended_supplier"] = state["analysis"]["recommended_supplier"]
	ctx.note(recommendation.get("explanation") or "", recommendation)
	return {"recommendation": recommendation}


# ---------------------------------------------------------------------------
# Human review and execution


def _proposal(state: State) -> dict:
	record, rec = state["record"], state["recommendation"]
	notes = {n["supplier"]: n["note"] for n in state["analysis"].get("supplier_notes", [])}
	return {
		"item_code": record["item_code"],
		"item_name": record["item_name"],
		"uom": record["stock_uom"],
		"warehouse": record["warehouse"],
		"company": record["company"],
		"need_by": record["need_by"],
		"required_qty": record["required_stock_qty"],
		"stock_qty": state["stock"]["actual_qty"],
		"open_orders": state["open_orders"],
		"usable_open_qty": state["usable_open_qty"],
		"shortage_qty": state["shortage_qty"],
		"recommendation": rec.get("explanation") or state["analysis"]["rationale"],
		"recommended_supplier": rec["recommended_supplier"],
		"rfq_suppliers": [c["supplier"] for c in state["candidates"]],
		"suppliers": [
			{
				"supplier": c["supplier"],
				"score": c.get("score"),
				"tier": c.get("tier"),
				"last_price": c.get("last_rate"),
				"lead_time_days": c.get("lead_time_days"),
				"quotation": c.get("quotation"),
				"note": notes.get(c["supplier"], ""),
			}
			for c in state["candidates"]
		],
		"excluded": state.get("excluded") or [],
		"rate": state["rate"],
	}


def _approval_chat(state: State) -> dict:
	record, rec = state["record"], state["recommendation"]
	roles = [_(r) for r in (state.get("approval_roles") or ["Purchase Manager"])]
	lines = []
	if state.get("revalidation_note"):
		lines.append(
			_("Things changed while this was waiting ({0}), so I've updated it.").format(
				state["revalidation_note"]
			)
		)
	lines.append(rec.get("explanation") or state["analysis"]["rationale"])
	if len(roles) > 1:
		lines.append(
			_(
				"It needs two approvals ({0}). I've sent it to them and will let you know here when they decide."
			).format(_and(roles))
		)
	else:
		lines.append(
			_("I've sent it to a {0} for approval and will let you know here when they decide.").format(
				roles[0]
			)
		)
	estimate = (
		_money(state["estimate"], record.get("company"))
		if state.get("rate")
		else _("Unknown (no price history yet)")
	)
	card = {
		"title": _("Request for quotation · waiting for approval"),
		"fields": [
			[_("Item"), _label(record["item_name"], record["item_code"])],
			[_("Quantity to buy"), f"{_num(state['shortage_qty'])} {record['stock_uom']}"],
			[
				_("In stock / on order"),
				f"{_num(state['stock']['actual_qty'])} / {_num(state['usable_open_qty'])}",
			],
			[_("Deliver to"), record["warehouse"]],
			[_("Needed by"), frappe.format(record["need_by"], "Date")],
			[_("Suppliers"), ", ".join(c["supplier"] for c in state["candidates"])],
			[_("Recommended"), rec.get("recommended_supplier") or ""],
			[_("Estimated value"), estimate],
		],
	}
	return {"chat": "\n\n".join(lines), "card": card}


def human_review(state: State, ctx: RunContext) -> dict:
	from langgraph.types import interrupt

	# This node runs again when the run resumes, so reuse the approval it created
	# unless that approval was already consumed by an earlier review round.
	reviewed = list(state.get("reviewed") or [])
	latest = frappe.get_all(
		"Agent Approval", filters={"run": ctx.run}, pluck="name", order_by="creation desc", limit=1
	)
	if latest and latest[0] not in reviewed:
		approval = latest[0]
	else:
		record = state["record"]
		doc = frappe.get_doc(
			{
				"doctype": "Agent Approval",
				"run": ctx.run,
				"status": "Pending",
				"action": _("Create Draft RFQ"),
				"estimated_value": state["estimate"],
				"risk": state["risk"],
				"required_approvals": state["required_approvals"],
				"summary": _("RFQ for {0} {1} {2} to {3} supplier(s)").format(
					_num(state["shortage_qty"]),
					record["stock_uom"],
					record["item_name"],
					len(state["candidates"]),
				),
				"proposal_json": json.dumps(_proposal(state), default=str, indent=1),
				"policy_results_json": json.dumps(state["policy_results"], default=str, indent=1),
				"required_roles": json.dumps(state.get("approval_roles") or ["Purchase Manager"]),
			}
		)
		doc.insert(ignore_permissions=True)
		approval = doc.name
		from pridict.agent_studio.approvals import notify_approvers

		notify_approvers(doc)
	ctx.note(_("Waiting for approval {0}").format(approval))
	decision = interrupt(
		{
			"type": "approval",
			"approval": approval,
			"message": _("Approval {0}: Draft RFQ worth {1}").format(
				approval, _money(state["estimate"], state["record"].get("company"))
			),
			**_approval_chat(state),
		}
	)
	decision = decision if isinstance(decision, dict) else {"decision": str(decision)}
	approved = decision.get("decision") == "approved"
	ctx.note(
		_("{0} by {1}{2}").format(
			_("Approved") if approved else _("Rejected"),
			decision.get("by", "-"),
			f": {decision['note']}" if decision.get("note") else "",
		)
	)
	return {
		"approval": approval,
		"decision": decision,
		"reviewed": [*reviewed, approval],
		"route": "approved" if approved else "rejected",
	}


def record_rejection(state: State, ctx: RunContext) -> dict:
	decision = state["decision"]
	outcome = _("Rejected by {0}: {1}").format(
		decision.get("by", "-"), decision.get("note") or _("no reason given")
	)
	ctx.note(outcome)
	by = get_fullname(decision["by"]) if decision.get("by") else _("The approver")
	reply = _("{0} decided not to go ahead with this purchase.").format(by)
	if decision.get("note"):
		reply += " " + _("Reason: {0}").format(decision["note"])
	return {
		"outcome": outcome,
		"final_status": "Rejected",
		"result": {**state["recommendation"], "decision": decision},
		"reply": reply,
	}


def revalidate(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	approval = frappe.get_doc("Agent Approval", state["approval"])
	problems = []

	if approval.status != "Approved":
		problems.append(
			_("Approval {0} is {1}, not approved.").format(approval.name, _(approval.status).lower())
		)
	# Re-check every recorded approver: roles can be removed while a run waits.
	for row in approval.decisions:
		if row.decision != "Approved":
			continue
		if ctx.policy("no_self_approval") and row.approver == ctx.requested_by:
			problems.append(_("The requester cannot approve their own run."))
		if row.approver_role and row.approver_role not in frappe.get_roles(row.approver):
			problems.append(_("{0} no longer holds the {1} role.").format(row.approver, row.approver_role))

	stock = ctx.tool("get_stock_balance", item_code=record["item_code"], warehouse=record["warehouse"])
	orders = ctx.tool(
		"get_open_purchase_orders",
		item_code=record["item_code"],
		warehouse=record["warehouse"],
		before_date=record["need_by"],
	)["orders"]
	usable = sum(flt(o["pending_qty"]) for o in orders)
	shortage = round(max(flt(record["required_stock_qty"]) - max(flt(stock["actual_qty"]), 0) - usable, 0), 6)
	if abs(shortage - state["shortage_qty"]) > 1e-6:
		problems.append(
			_("Shortage changed from {0} to {1} {2} while waiting.").format(
				_num(state["shortage_qty"]), _num(shortage), record["stock_uom"]
			)
		)

	if problems:
		ctx.note(" ".join(problems))
		estimate = round(shortage * flt(state["rate"]), 2)
		return {
			"route": "fail",
			"revalidation_note": " ".join(problems),
			"stock": stock,
			"open_orders": orders,
			"usable_open_qty": usable,
			"shortage_qty": shortage,
			"estimate": estimate,
		}
	ctx.note(_("Re-checked approver, stock and open orders: unchanged"))
	return {"route": "pass"}


def create_draft(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	approval = frappe.get_doc("Agent Approval", state["approval"])
	arguments = {
		"item_code": record["item_code"],
		"qty": state["shortage_qty"],
		"schedule_date": record["need_by"],
		"suppliers": [c["supplier"] for c in state["candidates"]],
		"approval_id": approval.name,
	}
	ctx.step_tools.append("create_draft_rfq")
	outcome = tools.run_tool("create_draft_rfq", arguments, approval=approval)
	if not outcome["ok"]:
		raise tools.ToolError(_("create_draft_rfq failed: {0}").format(outcome["error"]))
	rfq = outcome["result"]["rfq"]
	ctx.note(_("Created draft {0}").format(rfq), outcome["result"])
	return {"rfq": rfq}


def verify_audit(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	rfq = frappe.get_doc("Request for Quotation", state["rfq"])
	expected = {c["supplier"] for c in state["candidates"]}
	problems = []
	if rfq.docstatus != 0:
		problems.append(_("RFQ is not a draft"))
	if {s.supplier for s in rfq.suppliers} != expected:
		problems.append(_("Supplier list differs from the approved proposal"))
	items = [i for i in rfq.items if i.item_code == record["item_code"]]
	if len(items) != 1 or abs(flt(items[0].stock_qty or items[0].qty) - state["shortage_qty"]) > 1e-6:
		problems.append(_("Item quantity differs from the approved proposal"))
	if problems:
		raise tools.ToolError(_("{0} does not match the approval: {1}").format(rfq.name, "; ".join(problems)))

	frappe.db.set_value(
		"Agent Approval",
		state["approval"],
		{"created_doctype": "Request for Quotation", "created_docname": rfq.name},
		update_modified=False,
	)
	outcome = _("Draft {0} created for {1} {2} {3} to {4} supplier(s)").format(
		rfq.name, _num(state["shortage_qty"]), record["stock_uom"], record["item_name"], len(expected)
	)
	ctx.note(outcome)
	approvers = [
		get_fullname(row.approver)
		for row in frappe.get_doc("Agent Approval", state["approval"]).decisions
		if row.decision == "Approved"
	]
	reply = _(
		"Good news: {0} approved it. I've created a draft Request for Quotation {1} for {2} {3} of {4}, addressed to {5}. "
		"It is still a draft: open it to check the details and send it to the suppliers."
	).format(
		" and ".join(approvers) or _("your approver"),
		rfq.name,
		_num(state["shortage_qty"]),
		record["stock_uom"],
		record["item_name"],
		", ".join(sorted(expected)),
	)
	return {
		"outcome": outcome,
		"final_status": "Completed",
		"result": {**state["recommendation"], "rfq": rfq.name, "decision": state["decision"]},
		"reply": reply,
		"reply_card": {
			"title": _("Draft Request for Quotation"),
			"link": {"doctype": "Request for Quotation", "name": rfq.name},
			"fields": [
				[_("Document"), rfq.name],
				[_("Item"), record["item_name"]],
				[_("Quantity"), f"{_num(state['shortage_qty'])} {record['stock_uom']}"],
				[_("Suppliers"), ", ".join(sorted(expected))],
			],
		},
	}
