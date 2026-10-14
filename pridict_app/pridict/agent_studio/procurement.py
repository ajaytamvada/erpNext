"""Node implementations for the Procurement Sourcing workflow (registry.WORKFLOWS).

Every function name matches a node id. Each receives the graph state and the
RunContext and returns a partial state update. Nodes with several outgoing edges
set "route" to the edge condition they chose.

Division of labour:
- The LLM reads and writes language: parsing the request, weighing suppliers,
  explaining the outcome. Its answers are constrained by JSON schemas.
- Code does every number (stock, shortage, value, limits) and every policy check.
  Figures in LLM output are overwritten with the computed ones.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

import frappe
from frappe import _
from frappe.utils import add_days, flt, fmt_money, getdate, nowdate

from pridict.agent_studio import registry, tools
from pridict.agent_studio.runtime import BudgetExceeded, RunContext

MAX_QUESTIONS = 3


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

	query = (requirement.get("item_query") or "").strip()
	if not query:
		missing.append(_("Which item do you need?"))
	else:
		items = ctx.tool("search_items", query=query, limit=5)["items"]
		exact = [
			i for i in items if query.lower() in (i["item_code"].lower(), (i["item_name"] or "").lower())
		]
		choice = exact[0] if len(exact) == 1 else (items[0] if len(items) == 1 else None)
		if not items:
			missing.append(_("I could not find an item matching '{0}'. What is the item code?").format(query))
		elif not choice:
			options = ", ".join(f"{i['item_code']} ({i['item_name']})" for i in items)
			missing.append(_("Which item do you mean: {0}?").format(options))
		else:
			record.update(
				item_code=choice["item_code"], item_name=choice["item_name"], stock_uom=choice["stock_uom"]
			)

	wanted = (requirement.get("warehouse") or "").strip()
	company = (requirement.get("company") or "").strip() or frappe.defaults.get_user_default("Company")
	if not wanted:
		missing.append(_("Which warehouse should receive it?"))
	elif frappe.db.exists("Warehouse", wanted) and frappe.has_permission("Warehouse", "read", wanted):
		record.update(warehouse=wanted, company=frappe.db.get_value("Warehouse", wanted, "company"))
	elif company:
		warehouses = ctx.tool("get_warehouses", company=company)["warehouses"]
		matches = [w["name"] for w in warehouses if wanted.lower() in w["name"].lower()]
		if len(matches) == 1:
			record.update(warehouse=matches[0], company=company)
		elif matches:
			missing.append(_("Which warehouse do you mean: {0}?").format(", ".join(matches[:8])))
		else:
			missing.append(
				_("I could not find warehouse '{0}' in {1}. Which warehouse?").format(wanted, company)
			)
	else:
		missing.append(_("I could not find warehouse '{0}'. Which warehouse?").format(wanted))

	found = ", ".join(f"{k}={v}" for k, v in record.items() if k in ("item_code", "warehouse", "company"))
	ctx.note(
		_("Resolved {0}").format(found or "-") + (f"; {len(missing)} open question(s)" if missing else ""),
		record,
	)
	return {"record": record, "missing": missing}


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
		if (state.get("asks") or 0) >= MAX_QUESTIONS:
			raise BudgetExceeded(
				_("Stopped after {0} questions without enough information.").format(MAX_QUESTIONS)
			)
		question = "\n".join(dict.fromkeys(missing))
		ctx.note(_("Missing information: {0}").format(question.replace("\n", " ")))
		return {"route": "missing data", "question": question, "record": record}

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
	answer = interrupt({"type": "question", "message": question})
	text = (answer.get("answer") if isinstance(answer, dict) else str(answer or "")).strip()

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
	return {"requirement": requirement, "asks": (state.get("asks") or 0) + 1, "conversation": conversation}


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
	risk = "High" if blocked or warnings >= 2 or required > 1 else ("Medium" if warnings else "Low")
	ctx.note(
		_("Estimated {0} ({1} × {2}); risk {3}").format(
			money(estimate), _num(state["shortage_qty"]), money(rate), risk
		),
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
			}
		)
		doc.insert(ignore_permissions=True)
		approval = doc.name
	ctx.note(_("Waiting for approval {0}").format(approval))
	decision = interrupt(
		{
			"type": "approval",
			"approval": approval,
			"message": _("Approval {0}: Draft RFQ worth {1}").format(
				approval, _money(state["estimate"], state["record"].get("company"))
			),
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
	return {
		"outcome": outcome,
		"final_status": "Rejected",
		"result": {**state["recommendation"], "decision": decision},
	}


def revalidate(state: State, ctx: RunContext) -> dict:
	record = state["record"]
	approval = frappe.get_doc("Agent Approval", state["approval"])
	problems = []

	if ctx.policy("no_self_approval") and approval.decided_by == ctx.requested_by:
		problems.append(_("The requester cannot approve their own run."))
	roles = set(state.get("approval_roles") or [])
	if (
		roles
		and not roles & set(frappe.get_roles(approval.decided_by))
		and approval.decided_by != "Administrator"
	):
		problems.append(
			_("{0} does not hold an approving role ({1}).").format(
				approval.decided_by, ", ".join(sorted(roles))
			)
		)

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
	return {
		"outcome": outcome,
		"final_status": "Completed",
		"result": {**state["recommendation"], "rfq": rfq.name, "decision": state["decision"]},
	}
