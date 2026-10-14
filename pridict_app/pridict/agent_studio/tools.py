"""Agent tools: the only way an agent reads or changes ERPNext.

Each tool is a plain function taking validated arguments and returning a JSON-safe
dict. Tools run as the user who started the run (frappe.session.user), and parent
documents are read with frappe.get_list, so ERPNext permissions still apply: the
agent never sees more than the person using it.

run_tool() is the single entry point. It checks the Agent Tool record (status and
access), validates arguments against the tool's input schema, enforces the approval
requirement for write tools, and times the call.
"""

from __future__ import annotations

import json
import statistics
import time
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate

from pridict.decision_intelligence.anomaly_detector import detect_price_variances
from pridict.decision_intelligence.vendor_scoring import calculate_vendor_scores

OPEN_PO_EXCLUDED_STATUS = ["Closed", "Completed", "On Hold", "Cancelled", "Delivered"]


class ToolError(Exception):
	"""A tool refused or failed in a way the agent should be told about."""


# ---------------------------------------------------------------------------
# Argument validation (the JSON Schema subset used by registry.TOOLS)

_TYPES = {
	"string": str,
	"number": (int, float),
	"integer": int,
	"boolean": bool,
	"array": list,
	"object": dict,
}


def validate_arguments(schema: dict, value: Any, path: str = "arguments") -> None:
	expected = schema.get("type")
	if expected:
		python_type = _TYPES[expected]
		is_bool = isinstance(value, bool)
		if not isinstance(value, python_type) or (is_bool and expected in ("number", "integer")):
			raise ToolError(_("{0} must be of type {1}.").format(path, expected))
	if "enum" in schema and value not in schema["enum"]:
		raise ToolError(_("{0} must be one of {1}.").format(path, ", ".join(map(str, schema["enum"]))))
	if expected in ("number", "integer"):
		if "minimum" in schema and value < schema["minimum"]:
			raise ToolError(_("{0} must be at least {1}.").format(path, schema["minimum"]))
		if "maximum" in schema and value > schema["maximum"]:
			raise ToolError(_("{0} must be at most {1}.").format(path, schema["maximum"]))
	if expected == "string" and schema.get("format") == "date":
		try:
			getdate(value)
		except Exception:
			raise ToolError(_("{0} must be a date (YYYY-MM-DD).").format(path)) from None
	if expected == "array":
		for index, item in enumerate(value):
			validate_arguments(schema.get("items", {}), item, f"{path}[{index}]")
	if expected == "object":
		properties = schema.get("properties", {})
		for key in schema.get("required", []):
			if key not in value or value[key] in (None, ""):
				raise ToolError(_("{0}.{1} is required.").format(path, key))
		if schema.get("additionalProperties") is False:
			unknown = sorted(set(value) - set(properties))
			if unknown:
				raise ToolError(_("{0} has unknown field(s): {1}.").format(path, ", ".join(unknown)))
		for key, item in value.items():
			if key in properties and item is not None:
				validate_arguments(properties[key], item, f"{path}.{key}")


# ---------------------------------------------------------------------------
# Read tools


def search_items(query: str, limit: int = 5) -> dict:
	phrase = f"%{query.strip()}%"
	items = frappe.get_list(
		"Item",
		filters={"disabled": 0, "has_variants": 0},
		or_filters={
			"item_code": ["like", phrase],
			"item_name": ["like", phrase],
			"description": ["like", phrase],
		},
		fields=["item_code", "item_name", "stock_uom", "item_group"],
		order_by="modified desc",
		limit_page_length=min(int(limit or 5), 10),
	)
	return {"items": items}


def get_warehouses(company: str) -> dict:
	warehouses = frappe.get_list(
		"Warehouse",
		filters={"company": company, "is_group": 0, "disabled": 0},
		fields=["name"],
		order_by="name asc",
		limit_page_length=100,
	)
	return {"warehouses": [{"name": w.name, "is_group": False} for w in warehouses]}


def get_stock_balance(item_code: str, warehouse: str) -> dict:
	bins = frappe.get_list(
		"Bin",
		filters={"item_code": item_code, "warehouse": warehouse},
		fields=["actual_qty", "reserved_qty", "projected_qty"],
		limit_page_length=1,
	)
	row = bins[0] if bins else {}
	return {
		"actual_qty": flt(row.get("actual_qty")),
		"reserved_qty": flt(row.get("reserved_qty")),
		"projected_qty": flt(row.get("projected_qty")),
	}


def get_open_purchase_orders(item_code: str, warehouse: str, before_date: str) -> dict:
	"""Submitted, not fully received PO lines for the item and warehouse due on or before a date.

	pending_qty is in the item's stock UOM.
	"""
	rows = frappe.get_list(
		"Purchase Order",
		filters=[
			["Purchase Order", "docstatus", "=", 1],
			["Purchase Order", "status", "not in", OPEN_PO_EXCLUDED_STATUS],
			["Purchase Order Item", "item_code", "=", item_code],
			["Purchase Order Item", "warehouse", "=", warehouse],
			["Purchase Order Item", "schedule_date", "<=", before_date],
		],
		fields=[
			"name",
			"supplier",
			"`tabPurchase Order Item`.qty as qty",
			"`tabPurchase Order Item`.received_qty as received_qty",
			"`tabPurchase Order Item`.conversion_factor as conversion_factor",
			"`tabPurchase Order Item`.schedule_date as schedule_date",
		],
		order_by="`tabPurchase Order Item`.schedule_date asc",
		limit_page_length=50,
	)
	orders = []
	for row in rows:
		pending = (flt(row.qty) - flt(row.received_qty)) * (flt(row.conversion_factor) or 1)
		if pending > 0:
			orders.append(
				{
					"name": row.name,
					"supplier": row.supplier,
					"pending_qty": pending,
					"schedule_date": str(row.schedule_date),
				}
			)
	return {"orders": orders}


def get_approved_suppliers(item_code: str) -> dict:
	"""Suppliers listed on the item (Item Supplier), excluding disabled ones."""
	if not frappe.has_permission("Item", "read", item_code):
		raise ToolError(_("Not permitted to read item {0}.").format(item_code))
	if not frappe.db.exists("Item", item_code):
		raise ToolError(_("Item {0} does not exist.").format(item_code))
	listed = frappe.get_all(
		"Item Supplier",
		filters={"parent": item_code, "parenttype": "Item"},
		pluck="supplier",
		order_by="idx asc",
	)
	if not listed:
		return {"suppliers": []}
	lead_time = flt(frappe.db.get_value("Item", item_code, "lead_time_days"))
	suppliers = frappe.get_list(
		"Supplier",
		filters={"name": ["in", listed], "disabled": 0},
		fields=["name", "on_hold", "hold_type", "release_date"],
		limit_page_length=0,
	)
	today = getdate(nowdate())
	result = []
	for supplier in sorted(suppliers, key=lambda s: listed.index(s.name)):
		on_hold = bool(supplier.on_hold) and (
			not supplier.release_date or getdate(supplier.release_date) > today
		)
		result.append({"supplier": supplier.name, "on_hold": on_hold, "lead_time_days": lead_time})
	return {"suppliers": result}


def _stock_rates(item_code: str, since: str) -> list[dict]:
	"""Submitted PO lines for the item since a date, with the rate per stock UOM in company currency."""
	rows = frappe.get_list(
		"Purchase Order",
		filters=[
			["Purchase Order", "docstatus", "=", 1],
			["Purchase Order", "transaction_date", ">=", since],
			["Purchase Order Item", "item_code", "=", item_code],
		],
		fields=[
			"name",
			"supplier",
			"transaction_date",
			"`tabPurchase Order Item`.base_rate as base_rate",
			"`tabPurchase Order Item`.conversion_factor as conversion_factor",
			"`tabPurchase Order Item`.stock_qty as stock_qty",
		],
		order_by="transaction_date desc",
		limit_page_length=500,
	)
	return [
		{
			"name": r.name,
			"supplier": r.supplier,
			"date": str(r.transaction_date),
			"rate": flt(r.base_rate) / (flt(r.conversion_factor) or 1),
			"stock_qty": flt(r.stock_qty),
		}
		for r in rows
		if flt(r.base_rate) > 0
	]


def get_price_history(item_code: str, days: int = 90) -> dict:
	lines = _stock_rates(item_code, add_days(nowdate(), -min(int(days or 90), 365)))
	total_qty = sum(line["stock_qty"] for line in lines)
	avg = (
		sum(line["rate"] * line["stock_qty"] for line in lines) / total_qty
		if total_qty
		else (statistics.fmean(line["rate"] for line in lines) if lines else 0)
	)
	by_supplier: dict[str, dict] = {}
	for line in lines:  # newest first, so the first line per supplier is its last price
		by_supplier.setdefault(
			line["supplier"],
			{"supplier": line["supplier"], "last_rate": line["rate"], "last_date": line["date"]},
		)
	return {
		"prices": [
			{"supplier": x["supplier"], "rate": round(x["rate"], 4), "date": x["date"]} for x in lines[:20]
		],
		"avg_rate": round(avg, 4),
		"by_supplier": list(by_supplier.values()),
		"line_count": len(lines),
	}


def get_supplier_quotations(item_code: str, valid_on: str) -> dict:
	rows = frappe.get_list(
		"Supplier Quotation",
		filters=[
			["Supplier Quotation", "docstatus", "=", 1],
			["Supplier Quotation", "status", "not in", ["Expired", "Stopped", "Cancelled"]],
			["Supplier Quotation", "valid_till", ">=", valid_on],
			["Supplier Quotation Item", "item_code", "=", item_code],
		],
		fields=[
			"name",
			"supplier",
			"valid_till",
			"`tabSupplier Quotation Item`.base_rate as base_rate",
			"`tabSupplier Quotation Item`.conversion_factor as conversion_factor",
		],
		order_by="valid_till desc",
		limit_page_length=20,
	)
	return {
		"quotations": [
			{
				"name": r.name,
				"supplier": r.supplier,
				"rate": round(flt(r.base_rate) / (flt(r.conversion_factor) or 1), 4),
				"valid_till": str(r.valid_till),
			}
			for r in rows
		]
	}


def score_vendors(suppliers: list[str]) -> dict:
	"""Score suppliers on the last 365 days with the Decision Intelligence engine."""
	suppliers = list(dict.fromkeys(suppliers))[:20]
	since = add_days(nowdate(), -365)
	po_rows = [
		dict(r)
		for r in frappe.get_list(
			"Purchase Order",
			filters={"docstatus": 1, "supplier": ["in", suppliers], "transaction_date": [">=", since]},
			fields=["name", "supplier", "grand_total", "schedule_date", "transaction_date"],
			limit_page_length=0,
		)
	]
	pr_rows = [
		dict(r)
		for r in frappe.get_list(
			"Purchase Receipt",
			filters={"docstatus": 1, "supplier": ["in", suppliers], "posting_date": [">=", since]},
			fields=["name", "supplier", "posting_date"],
			limit_page_length=0,
		)
	]
	pr_items = (
		[
			dict(r)
			for r in frappe.get_all(
				"Purchase Receipt Item",
				filters={"parent": ["in", [r["name"] for r in pr_rows]]},
				fields=["parent", "qty", "received_qty", "rejected_qty", "purchase_order"],
				limit_page_length=0,
			)
		]
		if pr_rows
		else []
	)
	scored = {s.vendor_id: s for s in calculate_vendor_scores(po_rows, [], pr_rows, pr_items)}
	scores = []
	for supplier in suppliers:
		score = scored.get(supplier)
		if score:
			scores.append(
				{
					"supplier": supplier,
					"score": round(score.overall_score, 1),
					"tier": score.tier.value,
					"orders_365d": score.order_count,
					"on_time_pct": round(score.on_time_delivery_rate, 1),
					"risk_flags": list(score.risk_flags),
				}
			)
		else:
			scores.append(
				{
					"supplier": supplier,
					"score": None,
					"tier": "No history",
					"orders_365d": 0,
					"on_time_pct": None,
					"risk_flags": [],
				}
			)
	return {"scores": scores}


def detect_price_anomalies(item_code: str, proposed_rate: float) -> dict:
	"""Compare a proposed stock-UOM rate with the median of the last 365 days."""
	rates = [line["rate"] for line in _stock_rates(item_code, add_days(nowdate(), -365))]
	if not rates:
		return {"anomalies": [], "benchmark_rate": None, "note": "No purchase history to compare against."}
	benchmark = statistics.median(rates)
	findings = detect_price_variances(
		[{"name": "PROPOSED", "supplier": ""}],
		[{"name": "PROPOSED", "parent": "PROPOSED", "item_code": item_code, "rate": proposed_rate, "qty": 1}],
		{item_code: benchmark},
	)
	return {
		"anomalies": [
			{
				"title": f"Proposed rate is {f.variance_percent:.1f}% above the 365-day median",
				"severity": f.severity.value,
				"variance_pct": round(f.variance_percent, 1),
			}
			for f in findings
		],
		"benchmark_rate": round(benchmark, 4),
	}


READ_TOOLS = {
	"search_items": search_items,
	"get_warehouses": get_warehouses,
	"get_stock_balance": get_stock_balance,
	"get_open_purchase_orders": get_open_purchase_orders,
	"get_approved_suppliers": get_approved_suppliers,
	"get_price_history": get_price_history,
	"get_supplier_quotations": get_supplier_quotations,
	"score_vendors": score_vendors,
	"detect_price_anomalies": detect_price_anomalies,
}

# Write tools are registered by the approval flow; they receive the approval document.
WRITE_TOOLS: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Dispatcher


def _tool_record(name: str) -> dict:
	record = frappe.db.get_value("Agent Tool", name, ["access", "status", "input_schema"], as_dict=True)
	if not record:
		raise ToolError(_("Unknown tool {0}.").format(name))
	return record


def tool_specs(names: list[str]) -> list[dict]:
	"""Function definitions for the LLM: enabled read tools only, in the given order."""
	specs = []
	for name in names:
		record = frappe.db.get_value(
			"Agent Tool", name, ["access", "status", "description", "input_schema"], as_dict=True
		)
		if record and record.access == "Read" and record.status == "Enabled" and name in READ_TOOLS:
			specs.append(
				{
					"name": name,
					"description": record.description,
					"parameters": json.loads(record.input_schema),
				}
			)
	return specs


def run_tool(name: str, arguments: dict | None, *, approval=None) -> dict:
	"""Run a tool and return {ok, result | error, duration_ms}. Never raises for tool errors."""
	started = time.monotonic()
	try:
		record = _tool_record(name)
		if record.status in ("Disabled", "Blocked for agents"):
			raise ToolError(_("Tool {0} is {1}.").format(name, _(record.status).lower()))
		if record.access != "Read":
			if approval is None or approval.status != "Approved":
				raise ToolError(_("Tool {0} changes data and needs an approved Agent Approval.").format(name))
			if name not in WRITE_TOOLS:
				raise ToolError(_("Tool {0} has no implementation.").format(name))
		elif name not in READ_TOOLS:
			raise ToolError(_("Tool {0} has no implementation.").format(name))

		arguments = arguments or {}
		validate_arguments(json.loads(record.input_schema or "{}"), arguments)
		if record.access == "Read":
			result = READ_TOOLS[name](**arguments)
		else:
			result = WRITE_TOOLS[name](approval=approval, **arguments)
		return {"ok": True, "result": result, "duration_ms": int((time.monotonic() - started) * 1000)}
	except (ToolError, frappe.PermissionError, frappe.ValidationError, frappe.DoesNotExistError) as error:
		message = str(error) or type(error).__name__
		return {
			"ok": False,
			"error": frappe.utils.strip_html(message),
			"duration_ms": int((time.monotonic() - started) * 1000),
		}


@frappe.whitelist(methods=["POST"])
def try_tool(name: str, arguments: str | dict | None = None) -> dict:
	"""Run a read tool from the Tools page so admins can see exactly what the agent sees."""
	frappe.only_for("System Manager")
	if isinstance(arguments, str):
		try:
			arguments = json.loads(arguments or "{}")
		except ValueError:
			return {"ok": False, "error": _("Arguments must be valid JSON.")}
	if _tool_record(name).access != "Read":
		return {"ok": False, "error": _("Only read tools can be tried from here.")}
	return run_tool(name, arguments)
