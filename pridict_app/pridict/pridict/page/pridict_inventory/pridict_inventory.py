import frappe
from frappe import _


INVENTORY_DOCTYPES = ("Item", "Warehouse", "Stock Entry", "Pick List", "Stock Reconciliation", "Serial No", "Batch")


@frappe.whitelist()
def get_overview(company=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to view Inventory."), frappe.PermissionError)

	companies = frappe.get_list("Company", fields=["name", "default_currency"], order_by="name asc", limit_page_length=100)
	if not companies:
		return {"companies": [], "message": _("You do not have access to a company.")}
	company_by_name = {row.name: row for row in companies}
	company = company or frappe.defaults.get_user_default("Company") or companies[0].name
	if company not in company_by_name:
		frappe.throw(_("You do not have access to company {0}.").format(frappe.bold(company)), frappe.PermissionError)

	return {
		"companies": companies,
		"filters": {"company": company, "currency": company_by_name[company].default_currency},
		"metrics": {
			"stock_items": _count("Item", {"disabled": 0, "is_stock_item": 1}),
			"warehouses": _count("Warehouse", {"company": company, "disabled": 0, "is_group": 0}),
			"draft_stock_entries": _count("Stock Entry", {"company": company, "docstatus": 0}),
			"pending_pick_lists": _count("Pick List", {"company": company, "docstatus": ["<", 2], "status": ["not in", ["Completed", "Cancelled"]]}),
		},
		"pipeline": _get_pipeline(company),
		"attention": _get_attention(company),
		"activity": _get_recent_activity(company),
		"create_permissions": {doctype: frappe.has_permission(doctype, "create") for doctype in INVENTORY_DOCTYPES},
		"reports": [
			{"label": _("Stock Balance"), "route": "query-report/Stock Balance"},
			{"label": _("Stock Ledger"), "route": "query-report/Stock Ledger"},
			{"label": _("Stock Ageing"), "route": "query-report/Stock Ageing"},
			{"label": _("Stock Projected Qty"), "route": "query-report/Stock Projected Qty"},
		],
		"definitions": {
			"stock_items": _("Enabled stock Items across the permitted site; Items are shared master data rather than company-owned records."),
			"warehouses": _("Enabled non-group Warehouses for the selected company."),
			"draft_stock_entries": _("Draft Stock Entries for the selected company."),
			"pending_pick_lists": _("Pick Lists for the selected company that are not completed or cancelled."),
		},
	}


def _count(doctype, filters):
	if not frappe.has_permission(doctype, "read"):
		return None
	result = frappe.get_list(doctype, filters=filters, fields=["count(name) as count"], limit_page_length=1)
	return (result[0].count or 0) if result else 0


def _get_pipeline(company):
	definitions = (
		("Item", {"disabled": 0, "is_stock_item": 1}),
		("Warehouse", {"company": company, "disabled": 0}),
		("Stock Entry", {"company": company, "docstatus": ["<", 2]}),
		("Pick List", {"company": company, "docstatus": ["<", 2]}),
		("Stock Reconciliation", {"company": company, "docstatus": ["<", 2]}),
	)
	return [{"doctype": doctype, "count": _count(doctype, filters)} for doctype, filters in definitions]


def _get_attention(company):
	rows = []
	definitions = (
		("Stock Entry", {"company": company, "docstatus": 0}, ["name", "purpose", "posting_date", "modified"], _("Draft stock movement")),
		("Pick List", {"company": company, "docstatus": ["<", 2], "status": ["not in", ["Completed", "Cancelled"]]}, ["name", "purpose", "status", "customer_name", "modified"], _("Pick list awaiting completion")),
		("Stock Reconciliation", {"company": company, "docstatus": 0}, ["name", "purpose", "posting_date", "difference_amount", "modified"], _("Draft stock reconciliation")),
	)
	for doctype, filters, fields, title in definitions:
		if not frappe.has_permission(doctype, "read"):
			continue
		for row in frappe.get_list(doctype, filters=filters, fields=fields, order_by="modified desc", limit_page_length=5):
			rows.append({
				"doctype": doctype,
				"name": row.name,
				"title": title,
				"detail": row.get("customer_name") or row.get("purpose"),
				"status": row.get("status"),
				"date": row.get("posting_date"),
				"amount": row.get("difference_amount"),
				"modified": row.modified,
			})
	rows.sort(key=lambda row: row["modified"], reverse=True)
	return rows[:8]


def _get_recent_activity(company):
	activity = []
	definitions = {
		"Stock Entry": ["name", "purpose", "posting_date", "docstatus", "total_amount", "modified"],
		"Pick List": ["name", "purpose", "status", "customer_name", "modified"],
		"Stock Reconciliation": ["name", "purpose", "posting_date", "docstatus", "difference_amount", "modified"],
	}
	for doctype, fields in definitions.items():
		if not frappe.has_permission(doctype, "read"):
			continue
		for row in frappe.get_list(doctype, filters={"company": company}, fields=fields, order_by="modified desc", limit_page_length=4):
			activity.append({
				"doctype": doctype,
				"name": row.name,
				"detail": row.get("customer_name") or row.get("purpose"),
				"status": row.get("status") or ("Submitted" if row.get("docstatus") == 1 else "Draft"),
				"amount": row.get("total_amount") if row.get("total_amount") is not None else row.get("difference_amount"),
				"modified": row.modified,
			})
	activity.sort(key=lambda row: row["modified"], reverse=True)
	return activity[:8]
