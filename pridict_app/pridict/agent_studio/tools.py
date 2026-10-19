"""Agent tools: the only way an agent reads or changes ERPNext.

Each tool is a plain function taking validated arguments and returning a JSON-safe
dict. Tools run as the user who started the run (frappe.session.user), and parent
documents are read with frappe.get_list, so ERPNext permissions still apply: the
agent never sees more than the person using it.

run_tool() is the single entry point. It checks the Agent Tool record (status and
access), validates arguments against the tool's input schema, enforces the approval
requirement for write tools (or the buyer's chat confirmation for master-data tools),
and times the call.
"""

from __future__ import annotations

import json
import statistics
import time
from typing import Any
from urllib.parse import quote

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
	query = query.strip()
	limit = min(int(limit or 5), 10)
	fields = ["item_code", "item_name", "stock_uom", "item_group"]
	base = {"disabled": 0, "has_variants": 0}
	# Exact code or name matches first, so a precise request is never crowded out.
	exact = frappe.get_list(
		"Item",
		filters=base,
		or_filters={"item_code": query, "item_name": query},
		fields=fields,
		limit_page_length=limit,
	)
	phrase = f"%{query}%"
	partial = frappe.get_list(
		"Item",
		filters={**base, "name": ["not in", [i.item_code for i in exact] or [""]]},
		or_filters={
			"item_code": ["like", phrase],
			"item_name": ["like", phrase],
			"description": ["like", phrase],
		},
		fields=fields,
		order_by="modified desc",
		limit_page_length=max(limit - len(exact), 0),
	)
	return {"items": (exact + partial)[:limit]}


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


# ---------------------------------------------------------------------------
# Read tools for the Procurement Assistant (general questions about buying and stock).
# All use frappe.get_list / has_permission, so answers never exceed what the user may see.

MAX_ROWS = 50

# doctype -> (list fields, date field, item child table, has supplier field)
BUYING_DOCTYPES: dict[str, dict] = {
	"Purchase Order": {
		"fields": [
			"name",
			"supplier",
			"transaction_date",
			"schedule_date",
			"status",
			"grand_total",
			"currency",
			"per_received",
			"per_billed",
		],
		"date": "transaction_date",
		"items": "Purchase Order Item",
		"supplier": True,
	},
	"Material Request": {
		"fields": [
			"name",
			"material_request_type",
			"transaction_date",
			"schedule_date",
			"status",
			"per_ordered",
		],
		"date": "transaction_date",
		"items": "Material Request Item",
		"supplier": False,
	},
	"Request for Quotation": {
		"fields": ["name", "transaction_date", "status"],
		"date": "transaction_date",
		"items": "Request for Quotation Item",
		"supplier": False,
	},
	"Supplier Quotation": {
		"fields": ["name", "supplier", "transaction_date", "valid_till", "status", "grand_total", "currency"],
		"date": "transaction_date",
		"items": "Supplier Quotation Item",
		"supplier": True,
	},
	"Purchase Receipt": {
		"fields": ["name", "supplier", "posting_date", "status", "grand_total", "currency", "per_billed"],
		"date": "posting_date",
		"items": "Purchase Receipt Item",
		"supplier": True,
	},
	"Purchase Invoice": {
		"fields": [
			"name",
			"supplier",
			"posting_date",
			"due_date",
			"status",
			"grand_total",
			"outstanding_amount",
			"currency",
		],
		"date": "posting_date",
		"items": "Purchase Invoice Item",
		"supplier": True,
	},
}
ITEM_FIELDS = [
	"item_code",
	"item_name",
	"qty",
	"uom",
	"rate",
	"amount",
	"schedule_date",
	"warehouse",
	"received_qty",
]


def _url(doctype: str, name: str) -> str:
	return f"/app/{frappe.scrub(doctype).replace('_', '-')}/{quote(name, safe='')}"


def _rows(doctype: str, rows: list[dict]) -> list[dict]:
	return [
		{**{k: v for k, v in row.items() if v not in (None, "")}, "url": _url(doctype, row["name"])}
		for row in rows
	]


def _limit(limit) -> int:
	return max(1, min(int(limit or 20), MAX_ROWS))


def list_documents(
	doctype: str,
	status: str = "",
	supplier: str = "",
	item_code: str = "",
	from_date: str = "",
	to_date: str = "",
	overdue: bool = False,
	limit: int = 20,
) -> dict:
	spec = BUYING_DOCTYPES.get(doctype)
	if not spec:
		raise ToolError(_("{0} is not a buying document I can list.").format(doctype))
	limit = _limit(limit)
	filters: list = []
	if status:
		filters.append([doctype, "status", "=", status])
	if supplier:
		if spec["supplier"]:
			filters.append([doctype, "supplier", "like", f"%{supplier}%"])
		elif doctype == "Request for Quotation":
			filters.append(["Request for Quotation Supplier", "supplier", "like", f"%{supplier}%"])
	if item_code:
		filters.append([spec["items"], "item_code", "=", item_code])
	if from_date:
		filters.append([doctype, spec["date"], ">=", from_date])
	if to_date:
		filters.append([doctype, spec["date"], "<=", to_date])
	if overdue:
		if doctype != "Purchase Order":
			raise ToolError(_("Overdue is only tracked for purchase orders."))
		filters += [
			[doctype, "docstatus", "=", 1],
			[doctype, "schedule_date", "<", nowdate()],
			[doctype, "per_received", "<", 100],
			[doctype, "status", "not in", OPEN_PO_EXCLUDED_STATUS],
		]
	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=spec["fields"],
		order_by=f"`tab{doctype}`.{spec['date']} desc, `tab{doctype}`.creation desc",
		limit_page_length=limit + 1,
		distinct=True,
	)
	return {"doctype": doctype, "documents": _rows(doctype, rows[:limit]), "more": len(rows) > limit}


def get_document(doctype: str, name: str) -> dict:
	if doctype not in (*BUYING_DOCTYPES, "Item", "Supplier"):
		raise ToolError(_("I can't open {0} documents.").format(doctype))
	if not frappe.db.exists(doctype, name):
		raise ToolError(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", name):
		raise ToolError(_("You are not allowed to see {0} {1}.").format(doctype, name))
	doc = frappe.get_doc(doctype, name)
	if doctype == "Item":
		return {
			"item_code": doc.name,
			"item_name": doc.item_name,
			"item_group": doc.item_group,
			"stock_uom": doc.stock_uom,
			"is_stock_item": bool(doc.is_stock_item),
			"disabled": bool(doc.disabled),
			"description": frappe.utils.strip_html(doc.description or "")[:500],
			"suppliers": [row.supplier for row in doc.supplier_items],
			"url": _url(doctype, name),
		}
	if doctype == "Supplier":
		email = (
			frappe.db.get_value("Contact", doc.supplier_primary_contact, "email_id")
			if doc.supplier_primary_contact
			else None
		)
		return {
			"supplier": doc.name,
			"supplier_name": doc.supplier_name,
			"supplier_group": doc.supplier_group,
			"country": doc.country,
			"on_hold": bool(doc.on_hold),
			"disabled": bool(doc.disabled),
			"email": email,
			"url": _url(doctype, name),
		}
	spec = BUYING_DOCTYPES[doctype]
	header = {field: doc.get(field) for field in spec["fields"] if doc.get(field) not in (None, "")}
	header.update(company=doc.get("company"), docstatus=doc.docstatus, url=_url(doctype, name))
	if doctype == "Request for Quotation":
		header["suppliers"] = [row.supplier for row in doc.suppliers]
	items = [
		{field: row.get(field) for field in ITEM_FIELDS if row.get(field) not in (None, "")}
		for row in doc.get("items")[:MAX_ROWS]
	]
	return {**header, "items": items}


def list_items(query: str = "", item_group: str = "", limit: int = 20) -> dict:
	limit = _limit(limit)
	filters = {"disabled": 0}
	if item_group:
		filters["item_group"] = item_group
	or_filters = {"item_code": ["like", f"%{query}%"], "item_name": ["like", f"%{query}%"]} if query else None
	rows = frappe.get_list(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "item_name", "item_group", "stock_uom", "is_stock_item"],
		order_by="modified desc",
		limit_page_length=limit + 1,
	)
	return {"items": _rows("Item", rows[:limit]), "more": len(rows) > limit}


def list_suppliers(query: str = "", supplier_group: str = "", limit: int = 20) -> dict:
	limit = _limit(limit)
	filters = {"disabled": 0}
	if supplier_group:
		filters["supplier_group"] = supplier_group
	or_filters = {"name": ["like", f"%{query}%"], "supplier_name": ["like", f"%{query}%"]} if query else None
	rows = frappe.get_list(
		"Supplier",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "supplier_name", "supplier_group", "country", "on_hold"],
		order_by="modified desc",
		limit_page_length=limit + 1,
	)
	return {"suppliers": _rows("Supplier", rows[:limit]), "more": len(rows) > limit}


def get_stock_levels(item_code: str = "", warehouse: str = "", limit: int = 20) -> dict:
	if not item_code and not warehouse:
		raise ToolError(_("Give an item or a warehouse."))
	limit = _limit(limit)
	filters = {}
	if item_code:
		filters["item_code"] = item_code
	if warehouse:
		filters["warehouse"] = warehouse
	rows = frappe.get_list(
		"Bin",
		filters=filters,
		fields=[
			"item_code",
			"warehouse",
			"actual_qty",
			"reserved_qty",
			"ordered_qty",
			"projected_qty",
			"stock_uom",
		],
		order_by="actual_qty desc",
		limit_page_length=limit + 1,
	)
	return {"stock": rows[:limit], "more": len(rows) > limit}


def purchase_summary(group_by: str, from_date: str = "", to_date: str = "", limit: int = 10) -> dict:
	"""Submitted purchase order value (company currency) grouped by supplier, item or month."""
	limit = _limit(limit)
	filters = [["Purchase Order", "docstatus", "=", 1]]
	if from_date:
		filters.append(["Purchase Order", "transaction_date", ">=", from_date])
	if to_date:
		filters.append(["Purchase Order", "transaction_date", "<=", to_date])
	if group_by == "supplier":
		fields = ["supplier as label", "sum(base_grand_total) as amount", "count(name) as orders"]
		group = "supplier"
	elif group_by == "item":
		fields = [
			"`tabPurchase Order Item`.item_code as label",
			"sum(`tabPurchase Order Item`.base_net_amount) as amount",
			"sum(`tabPurchase Order Item`.stock_qty) as qty",
		]
		group = "`tabPurchase Order Item`.item_code"
	elif group_by == "month":
		fields = [
			"date_format(transaction_date, '%Y-%m') as label",
			"sum(base_grand_total) as amount",
			"count(name) as orders",
		]
		group = "label"
	else:
		raise ToolError(_("Group by supplier, item or month."))
	rows = frappe.get_list(
		"Purchase Order",
		filters=filters,
		fields=fields,
		group_by=group,
		order_by="label desc" if group_by == "month" else "amount desc",
		limit_page_length=limit,
	)
	company = frappe.defaults.get_user_default("Company")
	currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
	return {
		"group_by": group_by,
		"currency": currency,
		"rows": [{**r, "amount": flt(r.amount, 2)} for r in rows],
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
	"list_documents": list_documents,
	"get_document": get_document,
	"list_items": list_items,
	"list_suppliers": list_suppliers,
	"get_stock_levels": get_stock_levels,
	"purchase_summary": purchase_summary,
}

# ---------------------------------------------------------------------------
# Write tools. They receive the approved Agent Approval and may only do exactly what
# it approved. They never submit: documents stay in Draft for a person to send.


def create_draft_rfq(
	approval, item_code: str, qty: float, schedule_date: str, suppliers: list[str], approval_id: str
) -> dict:
	if approval.name != approval_id:
		raise ToolError(_("approval_id does not match the approval being executed."))
	if approval.created_docname:
		raise ToolError(
			_("Approval {0} was already used to create {1}.").format(approval.name, approval.created_docname)
		)
	proposal = json.loads(approval.proposal_json or "{}")
	mismatches = []
	if item_code != proposal.get("item_code"):
		mismatches.append(_("item"))
	if abs(flt(qty) - flt(proposal.get("shortage_qty"))) > 1e-6:
		mismatches.append(_("quantity"))
	if sorted(suppliers) != sorted(proposal.get("rfq_suppliers") or []):
		mismatches.append(_("suppliers"))
	if str(getdate(schedule_date)) != str(proposal.get("need_by")):
		mismatches.append(_("date"))
	if mismatches:
		raise ToolError(_("The request differs from what was approved ({0}).").format(", ".join(mismatches)))

	stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
	rfq = frappe.get_doc(
		{
			"doctype": "Request for Quotation",
			"company": proposal["company"],
			"transaction_date": nowdate(),
			"message_for_supplier": _(
				"Please send your best price and delivery date for the item below, required by {0}."
			).format(schedule_date),
			"suppliers": [{"supplier": supplier} for supplier in suppliers],
			"items": [
				{
					"item_code": item_code,
					"qty": flt(qty),
					"uom": stock_uom,
					"stock_uom": stock_uom,
					"conversion_factor": 1,
					"warehouse": proposal["warehouse"],
					"schedule_date": schedule_date,
				}
			],
		}
	)
	# Normal insert: the requester's own ERPNext permissions decide whether this is allowed.
	rfq.insert()
	rfq.add_comment(
		"Comment",
		_("Prepared by Agent Studio run {0}; approved in {1} by {2}.").format(
			approval.run,
			approval.name,
			", ".join(row.approver for row in approval.decisions if row.decision == "Approved"),
		),
	)
	return {"rfq": rfq.name}


WRITE_TOOLS: dict[str, Any] = {"create_draft_rfq": create_draft_rfq}


# ---------------------------------------------------------------------------
# Master-data tools. They run only after the buyer confirmed the exact record in chat
# (confirmation = {"run", "by"}). By design they do not depend on the buyer's own
# Item/Supplier permissions: the assistant creates on their behalf, and every record
# carries a comment naming the buyer and the run, so the action is fully attributable.


def _attribute(doc, confirmation: dict, what: str):
	doc.add_comment(
		"Comment",
		_("{0} by the Procurement Assistant for {1}, who confirmed it in conversation {2}.").format(
			what, confirmation["by"], confirmation.get("run") or confirmation.get("conversation")
		),
	)


def _unique_name(doctype: str, name: str) -> str:
	candidate, n = name, 1
	while frappe.db.exists(doctype, candidate):
		n += 1
		candidate = f"{name} - {n}"
	return candidate


def create_item(
	confirmation: dict,
	item_name: str,
	item_group: str,
	stock_uom: str,
	is_stock_item: bool,
	description: str = "",
) -> dict:
	item_name = item_name.strip()[:140]
	if not item_name:
		raise ToolError(_("The item needs a name."))
	if not frappe.db.exists("Item Group", {"name": item_group, "is_group": 0}):
		raise ToolError(_("Item group {0} does not exist.").format(item_group))
	if not frappe.db.exists("UOM", {"name": stock_uom, "enabled": 1}):
		raise ToolError(_("Unit {0} does not exist.").format(stock_uom))
	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_name": item_name,
			"item_group": item_group,
			"stock_uom": stock_uom,
			"is_stock_item": 1 if is_stock_item else 0,
			"is_purchase_item": 1,
			"description": description or item_name,
		}
	)
	if frappe.db.get_single_value("Stock Settings", "item_naming_by") != "Naming Series":
		item.item_code = _unique_name("Item", item_name)
	item.insert(ignore_permissions=True)
	_attribute(item, confirmation, _("Created"))
	return {"item_code": item.name, "item_name": item.item_name, "stock_uom": item.stock_uom}


def _default_supplier_group() -> str:
	group = frappe.db.get_single_value("Buying Settings", "supplier_group")
	if group:
		return group
	groups = frappe.get_all(
		"Supplier Group", filters={"is_group": 0}, pluck="name", order_by="lft asc", limit=1
	)
	if not groups:
		raise ToolError(_("No supplier group exists to put the new supplier in."))
	return groups[0]


def create_supplier(confirmation: dict, supplier_name: str, email: str = "") -> dict:
	supplier_name = supplier_name.strip()[:140]
	if not supplier_name:
		raise ToolError(_("The supplier needs a name."))
	email = (email or "").strip()
	if email and not frappe.utils.validate_email_address(email):
		raise ToolError(_("{0} is not a valid email address.").format(email))
	supplier = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": supplier_name,
			"supplier_group": _default_supplier_group(),
			"supplier_type": "Company",
		}
	)
	supplier.insert(ignore_permissions=True)
	_attribute(supplier, confirmation, _("Created"))
	contact = None
	if email:
		doc = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": supplier_name,
				"email_ids": [{"email_id": email, "is_primary": 1}],
				"links": [{"link_doctype": "Supplier", "link_name": supplier.name}],
			}
		)
		doc.insert(ignore_permissions=True)
		contact = doc.name
		# The RFQ picks up the supplier's email from its primary contact.
		supplier.db_set("supplier_primary_contact", contact)
	return {"supplier": supplier.name, "contact": contact or ""}


def link_item_supplier(confirmation: dict, item_code: str, supplier: str) -> dict:
	if not frappe.db.exists("Supplier", supplier):
		raise ToolError(_("Supplier {0} does not exist.").format(supplier))
	item = frappe.get_doc("Item", item_code)
	if any(row.supplier == supplier for row in item.supplier_items):
		return {"added": False}
	item.append("supplier_items", {"supplier": supplier})
	item.save(ignore_permissions=True)
	_attribute(item, confirmation, _("Supplier {0} added").format(supplier))
	return {"added": True}


MASTER_DATA_TOOLS: dict[str, Any] = {
	"create_item": create_item,
	"create_supplier": create_supplier,
	"link_item_supplier": link_item_supplier,
}


def create_draft_material_request(
	confirmation: dict, items: list[dict], warehouse: str, schedule_date: str, company: str = ""
) -> dict:
	"""A draft Material Request (Purchase) the user confirmed in chat. Created as the user, never submitted."""
	company = company or frappe.db.get_value("Warehouse", warehouse, "company")
	if not company:
		raise ToolError(_("Warehouse {0} does not exist.").format(warehouse))
	rows = []
	for line in items:
		item_code, qty = line.get("item_code"), flt(line.get("qty"))
		if not frappe.db.exists("Item", item_code):
			raise ToolError(_("Item {0} does not exist.").format(item_code))
		if qty <= 0:
			raise ToolError(_("Quantity for {0} must be more than zero.").format(item_code))
		rows.append(
			{
				"item_code": item_code,
				"qty": qty,
				"schedule_date": line.get("schedule_date") or schedule_date,
				"warehouse": warehouse,
			}
		)
	doc = frappe.get_doc(
		{
			"doctype": "Material Request",
			"material_request_type": "Purchase",
			"company": company,
			"transaction_date": nowdate(),
			"schedule_date": schedule_date,
			"set_warehouse": warehouse,
			"items": rows,
		}
	)
	# Normal insert: the user's own permission to create Material Requests applies.
	doc.insert()
	_attribute(doc, confirmation, _("Drafted"))
	return {"material_request": doc.name, "url": _url("Material Request", doc.name)}


# Tools that run on the user's confirmation in chat instead of an Agent Approval.
CONFIRMED_TOOLS: dict[str, Any] = {
	**MASTER_DATA_TOOLS,
	"create_draft_material_request": create_draft_material_request,
}


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


def run_tool(name: str, arguments: dict | None, *, approval=None, confirmation=None) -> dict:
	"""Run a tool and return {ok, result | error, duration_ms}. Never raises for tool errors."""
	started = time.monotonic()
	try:
		record = _tool_record(name)
		if record.status in ("Disabled", "Blocked for agents"):
			raise ToolError(_("Tool {0} is {1}.").format(name, _(record.status).lower()))
		if name in CONFIRMED_TOOLS:
			if not (
				confirmation
				and confirmation.get("by")
				and (confirmation.get("run") or confirmation.get("conversation"))
			):
				raise ToolError(_("Tool {0} needs the buyer's confirmation in chat.").format(name))
		elif record.access != "Read":
			if approval is None or approval.status != "Approved":
				raise ToolError(_("Tool {0} changes data and needs an approved Agent Approval.").format(name))
			if name not in WRITE_TOOLS:
				raise ToolError(_("Tool {0} has no implementation.").format(name))
		elif name not in READ_TOOLS:
			raise ToolError(_("Tool {0} has no implementation.").format(name))

		arguments = arguments or {}
		validate_arguments(json.loads(record.input_schema or "{}"), arguments)
		if name in CONFIRMED_TOOLS:
			result = CONFIRMED_TOOLS[name](confirmation=confirmation, **arguments)
		elif record.access == "Read":
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
