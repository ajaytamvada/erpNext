"""Evaluation suite for the Procurement Sourcing agent.

Each scenario builds its own throw-away data (warehouses, suppliers, an item with
stock, open and historical purchase orders), runs the real agent end to end, checks
the outcome against expectations, and then rolls the whole transaction back, so the
site's data is never changed. Only the Agent Evaluation record is kept.

Live mode calls the agent's own model and measures the agent. Offline mode replaces
the model with ScriptedLLM, which checks the deterministic parts (tools, numbers,
policies, pauses) without an API key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from unittest.mock import patch

import frappe
from frappe import _
from frappe.utils import add_days, formatdate, getdate, now_datetime, nowdate

from pridict.agent_studio import gateway, registry, runtime

EVAL_EVENT = "agent_eval_update"


class ScriptedLLM:
	"""Stands in for gateway.chat; answers by response schema title."""

	def __init__(self, requirements: list[dict]):
		self.requirements = list(requirements)
		self.calls: list[str] = []

	def __call__(self, config, messages, *, response_schema=None, max_tokens=None, **_):
		title = (response_schema or {}).get("title", "text")
		self.calls.append(title)
		if title == "requirement":
			payload = self.requirements.pop(0) if len(self.requirements) > 1 else self.requirements[0]
		elif title == "sourcing_analysis":
			names = response_schema["properties"]["recommended_supplier"]["enum"]
			payload = {
				"recommended_supplier": names[0],
				"supplier_notes": [{"supplier": n, "note": "ok"} for n in names],
				"rationale": "Best balance.",
			}
		elif title == "recommendation":
			# Deliberately wrong numbers and supplier: the workflow must overwrite them.
			payload = {
				"shortage_qty": 1,
				"recommended_action": "ask_buyer",
				"suppliers": [],
				"recommended_supplier": "Invented Supplier",
				"estimated_value": 1,
				"explanation": "Send the RFQ.",
			}
		else:
			payload = None
		return gateway.LLMResponse(
			content=json.dumps(payload) if payload is not None else "Stock already covers the need.",
			tool_calls=[],
			finish_reason="stop",
			usage=gateway.Usage(100, 20, 120),
			model_config=config,
			model="scripted",
			latency_ms=5,
		)


@dataclass
class Scenario:
	key: str
	title: str
	expected: str
	need: float = 500
	stock: float = 100
	open_orders: list = field(default_factory=lambda: [(150, "before")])  # (qty, before|after need-by)
	approved_suppliers: int = 2
	# Past purchases in another warehouse, for prices: (supplier key, qty, rate)
	history: list = field(default_factory=lambda: [("A", 10, 250)])
	mention_warehouse: bool = True
	decision: str | None = None  # simulate an approver after the pause
	expect: dict = field(default_factory=dict)


SCENARIOS = [
	Scenario(
		"shortage",
		"Shortage exists (500 need, 100 stock, 150 on order)",
		"Shortage 250, RFQ recommended, waits for approval",
		expect={"status": "Awaiting approval", "shortage": 250, "approval": True},
	),
	Scenario(
		"no_shortage",
		"No shortage (stock 600)",
		"Explains no purchase needed; no approval request",
		stock=600,
		expect={"status": "Completed", "approval": False, "outcome": "No purchase needed"},
	),
	Scenario(
		"po_after_need_by",
		"Open PO arrives after need-by date",
		"Open PO ignored; shortage 400",
		open_orders=[(150, "after")],
		expect={"status": "Awaiting approval", "shortage": 400, "approval": True},
	),
	Scenario(
		"no_supplier",
		"No eligible supplier",
		"Asks buyer; does not invent a supplier",
		approved_suppliers=0,
		expect={"status": "Waiting for buyer", "approval": False, "question": "supplier"},
	),
	Scenario(
		"price_above_average",
		"Price 25% above average",
		"Price variance warning shown to approver",
		approved_suppliers=1,
		history=[("X", 300, 200), ("A", 10, 260)],
		expect={"status": "Awaiting approval", "approval": True, "policy": ("price_variance", "WARN")},
	),
	Scenario(
		"missing_warehouse",
		"Missing warehouse in request",
		"Asks buyer which warehouse",
		mention_warehouse=False,
		expect={"status": "Waiting for buyer", "approval": False, "question": "warehouse"},
	),
	Scenario(
		"approver_rejects",
		"Approver rejects",
		"Run ends; no document created; reason stored",
		decision="rejected",
		expect={"status": "Rejected", "outcome": "Not needed this month", "no_document": True},
	),
	Scenario(
		"above_ceiling",
		"Value above ₹25,00,000",
		"Blocked before a recommendation is prepared; no draft",
		need=12250,  # 12,000 short x at least 250 = 30,00,000 or more
		history=[("A", 10, 300)],
		expect={
			"status": "Completed",
			"approval": False,
			"outcome": "Blocked",
			"skipped_node": "prepare_recommendation",
		},
	),
]


# ---------------------------------------------------------------------------
# Throw-away fixtures (rolled back after every scenario)


def _company() -> str:
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	company = company or frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw(_("Create a Company before running the evaluation suite."))
	return company


def _leaf(doctype: str) -> str:
	name = frappe.db.get_value(doctype, {"is_group": 0}, "name")
	if not name:
		frappe.throw(_("The evaluation suite needs at least one {0} that is not a group.").format(_(doctype)))
	return name


def _warehouse(company: str, label: str) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr")
	if frappe.db.exists("Warehouse", f"{label} - {abbr}"):
		return f"{label} - {abbr}"
	parent = frappe.db.get_value("Warehouse", {"company": company, "is_group": 1}, "name", order_by="lft asc")
	doc = frappe.get_doc(
		{"doctype": "Warehouse", "warehouse_name": label, "company": company, "parent_warehouse": parent}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _purchase_order(company, supplier, item, qty, rate, warehouse, schedule_date):
	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"company": company,
			"supplier": supplier,
			"transaction_date": nowdate(),
			"schedule_date": schedule_date,
			"items": [
				{
					"item_code": item,
					"qty": qty,
					"rate": rate,
					"warehouse": warehouse,
					"schedule_date": schedule_date,
				}
			],
		}
	)
	po.set_missing_values()
	po.insert(ignore_permissions=True)
	po.submit()
	return po.name


def build_fixtures(scenario: Scenario, index: int) -> dict:
	from erpnext.stock.utils import get_or_make_bin

	company = _company()
	stores = _warehouse(company, "Agent Eval Stores")
	history_wh = _warehouse(company, "Agent Eval History")
	group = _leaf("Supplier Group")
	suppliers = {}
	for key in ("A", "B", "X"):
		name = f"Agent Eval Supplier {key}"
		if not frappe.db.exists("Supplier", name):
			frappe.get_doc({"doctype": "Supplier", "supplier_name": name, "supplier_group": group}).insert(
				ignore_permissions=True
			)
		suppliers[key] = name

	uom = "Nos" if frappe.db.exists("UOM", "Nos") else frappe.db.get_value("UOM", {}, "name")
	item_code = f"AGENT-EVAL-{index}-{frappe.generate_hash(length=5).upper()}"
	item_name = f"Eval Aluminium Sheet {index} {item_code[-5:]}"
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_name,
			"item_group": _leaf("Item Group"),
			"stock_uom": uom,
			"is_stock_item": 1,
			"lead_time_days": 7,
			"supplier_items": [{"supplier": suppliers[k]} for k in ("A", "B")[: scenario.approved_suppliers]],
		}
	).insert(ignore_permissions=True)

	if scenario.stock:
		frappe.db.set_value(
			"Bin",
			get_or_make_bin(item_code, stores),
			{"actual_qty": scenario.stock, "projected_qty": scenario.stock},
		)
	need_by = add_days(nowdate(), 14)
	for qty, when in scenario.open_orders:
		date = add_days(nowdate(), 7 if when == "before" else 30)
		_purchase_order(company, suppliers["A"], item_code, qty, 250, stores, date)
	for key, qty, rate in scenario.history:
		_purchase_order(company, suppliers[key], item_code, qty, rate, history_wh, add_days(nowdate(), 1))

	return {
		"company": company,
		"warehouse": stores,
		"item_code": item_code,
		"item_name": item_name,
		"uom": uom,
		"need_by": need_by,
	}


def _request(scenario: Scenario, fx: dict) -> str:
	where = f" delivered to {fx['warehouse']}" if scenario.mention_warehouse else ""
	return f"We need {scenario.need:g} {fx['uom']} of {fx['item_name']}{where} by {formatdate(fx['need_by'], 'dd MMMM yyyy')}."


def _scripted(scenario: Scenario, fx: dict) -> ScriptedLLM:
	return ScriptedLLM(
		[
			{
				"item_query": fx["item_name"],
				"qty": scenario.need,
				"uom": "",
				"warehouse": fx["warehouse"] if scenario.mention_warehouse else "",
				"need_by": str(getdate(fx["need_by"])),
				"company": "",
			}
		]
	)


# ---------------------------------------------------------------------------
# Checking


def check(scenario: Scenario, run) -> list[str]:
	"""Return the failed expectations (empty list = pass)."""
	expect, failures = scenario.expect, []
	approvals = frappe.get_all(
		"Agent Approval",
		filters={"run": run.name},
		fields=["name", "status", "proposal_json", "policy_results_json", "created_docname"],
	)
	if run.status != expect["status"]:
		failures.append(
			f"status was {run.status}, expected {expect['status']}" + (f" ({run.error})" if run.error else "")
		)
	if "approval" in expect and bool(approvals) != expect["approval"]:
		failures.append("an approval request was created" if approvals else "no approval request was created")
	if "shortage" in expect and approvals:
		shortage = json.loads(approvals[-1].proposal_json or "{}").get("shortage_qty")
		if shortage != expect["shortage"]:
			failures.append(f"shortage was {shortage}, expected {expect['shortage']}")
	if "outcome" in expect and expect["outcome"].lower() not in (run.outcome or "").lower():
		failures.append(f"outcome '{run.outcome}' does not mention '{expect['outcome']}'")
	if "question" in expect and expect["question"] not in (run.pending_question or "").lower():
		failures.append(f"question '{run.pending_question}' does not mention '{expect['question']}'")
	if "policy" in expect:
		rule_key, result = expect["policy"]
		name = frappe.db.get_value("Agent Policy", {"rule_key": rule_key}, "policy_name")
		results = {
			r["rule"]: r["result"] for a in approvals for r in json.loads(a.policy_results_json or "[]")
		}
		if results.get(name) != result:
			failures.append(f"policy '{name}' was {results.get(name)}, expected {result}")
	if expect.get("no_document") and any(a.created_docname for a in approvals):
		failures.append("a document was created")
	if expect.get("skipped_node") in {s.node_id for s in run.steps}:
		failures.append(f"step {expect['skipped_node']} ran but should not have")
	return failures


def run_scenario(agent: str, scenario: Scenario, index: int, live: bool) -> dict:
	"""Run one scenario inside a transaction that is always rolled back."""
	started = now_datetime()
	result = {"key": scenario.key, "case": scenario.title, "expected": scenario.expected}
	frappe.flags.agent_eval = True
	frappe.flags.agent_eval_offline = not live
	try:
		fx = build_fixtures(scenario, index)
		llm = None if live else _scripted(scenario, fx)
		with patch("pridict.agent_studio.gateway.chat", llm) if llm else _nullcontext():
			run_name = runtime.start_run(agent, _request(scenario, fx))["run"]
			if (
				scenario.decision
				and frappe.db.get_value("Agent Run", run_name, "status") == "Awaiting approval"
			):
				approval = frappe.get_doc("Agent Approval", {"run": run_name, "status": "Pending"})
				note = "Not needed this month"
				approval.db_set(
					{"status": "Rejected", "decided_by": frappe.session.user, "decision_note": note}
				)
				runtime.execute(
					run_name, {"decision": scenario.decision, "by": frappe.session.user, "note": note}
				)
		run = frappe.get_doc("Agent Run", run_name)
		failures = check(scenario, run)
		result.update(
			result="PASS" if not failures else "FAIL",
			note="; ".join(failures),
			run_status=run.status,
			outcome=run.outcome or run.pending_question or run.error or "",
			tokens=run.total_tokens or 0,
			llm_calls=run.llm_calls or 0,
			steps=[s.node_id for s in run.steps],
		)
	except Exception as error:
		frappe.log_error(title=f"Agent evaluation scenario {scenario.key} failed")
		result.update(result="FAIL", note=f"Error: {error}", tokens=0)
	finally:
		frappe.db.rollback()
		frappe.flags.agent_eval = False
		frappe.flags.agent_eval_offline = False
	result["seconds"] = round((now_datetime() - started).total_seconds(), 1)
	return result


class _nullcontext:
	def __enter__(self):
		return None

	def __exit__(self, *exc):
		return False


def execute_evaluation(evaluation: str):
	"""Background job: run every scenario and store the results on the Agent Evaluation."""
	doc = frappe.get_doc("Agent Evaluation", evaluation)
	doc.db_set({"status": "Running", "started_at": now_datetime()}, update_modified=False)
	frappe.db.commit()
	results = []
	try:
		for index, scenario in enumerate(SCENARIOS, start=1):
			results.append(run_scenario(doc.agent, scenario, index, live=doc.mode == "Live"))
			frappe.db.set_value(
				"Agent Evaluation",
				evaluation,
				"results_json",
				json.dumps(results, indent=1, default=str),
				update_modified=False,
			)
			frappe.db.commit()
			frappe.publish_realtime(EVAL_EVENT, {"evaluation": evaluation, "done": len(results)})
		passed = sum(r["result"] == "PASS" for r in results)
		doc.db_set(
			{
				"status": "Completed",
				"passed": passed,
				"total": len(results),
				"ended_at": now_datetime(),
				"total_tokens": sum(r.get("tokens") or 0 for r in results),
			},
			update_modified=False,
		)
	except Exception as error:
		frappe.db.rollback()
		doc.db_set(
			{"status": "Failed", "error": str(error)[:2000], "ended_at": now_datetime()},
			update_modified=False,
		)
	frappe.db.commit()
	frappe.publish_realtime(EVAL_EVENT, {"evaluation": evaluation, "done": len(results), "finished": True})


@frappe.whitelist(methods=["POST"])
def start_evaluation(agent: str = registry.PROCUREMENT_AGENT, mode: str = "Offline") -> dict:
	frappe.only_for("System Manager")
	if mode not in ("Live", "Offline"):
		frappe.throw(_("Mode must be Live or Offline."))
	if frappe.db.exists("Agent Evaluation", {"agent": agent, "status": ["in", ["Queued", "Running"]]}):
		frappe.throw(_("An evaluation of {0} is already running.").format(agent))
	version, model_config = frappe.db.get_value("Agent Definition", agent, ["version", "model_config"])
	doc = frappe.get_doc(
		{
			"doctype": "Agent Evaluation",
			"agent": agent,
			"agent_version": version,
			"mode": mode,
			"status": "Queued",
			"model_config": model_config if mode == "Live" else None,
			"started_by": frappe.session.user,
		}
	).insert(ignore_permissions=True)
	frappe.enqueue(
		"pridict.agent_studio.evals.execute_evaluation",
		queue="long",
		timeout=3600,
		enqueue_after_commit=True,
		evaluation=doc.name,
	)
	return {"evaluation": doc.name}


def latest(agent: str) -> dict | None:
	rows = frappe.get_all(
		"Agent Evaluation",
		filters={"agent": agent},
		fields=[
			"name",
			"agent_version",
			"mode",
			"status",
			"passed",
			"total",
			"total_tokens",
			"started_at",
			"ended_at",
			"results_json",
			"error",
		],
		order_by="creation desc",
		limit=1,
	)
	if not rows:
		return None
	row = rows[0]
	row.results = json.loads(row.pop("results_json") or "[]")
	return row
