import frappe
from frappe import _


ASSET_DOCTYPES = ("Asset", "Asset Category", "Asset Movement", "Asset Repair", "Asset Maintenance", "Asset Depreciation Schedule")


@frappe.whitelist()
def get_overview(company=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to view Assets."), frappe.PermissionError)
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
			"operating_assets": _count("Asset", {"company": company, "status": ["in", ["Submitted", "Partially Depreciated", "In Maintenance"]]}),
			"assets_in_maintenance": _count("Asset", {"company": company, "status": "In Maintenance"}),
			"pending_repairs": _count("Asset Repair", {"company": company, "repair_status": "Pending", "docstatus": ["<", 2]}),
			"draft_movements": _count("Asset Movement", {"company": company, "docstatus": 0}),
		},
		"attention": _attention(company),
		"activity": _activity(company),
		"create_permissions": {doctype: frappe.has_permission(doctype, "create") for doctype in ASSET_DOCTYPES},
		"reports": [{"label": _("Fixed Asset Register"), "route": "query-report/Fixed Asset Register"}, {"label": _("Asset Activity"), "route": "query-report/Asset Activity"}, {"label": _("Asset Maintenance"), "route": "query-report/Asset Maintenance"}],
		"definitions": {
			"operating_assets": _("Submitted, partially depreciated, or in-maintenance Assets for the selected company."),
			"assets_in_maintenance": _("Assets currently marked In Maintenance."),
			"pending_repairs": _("Pending Asset Repairs that are not cancelled."),
			"draft_movements": _("Draft Asset Movements awaiting review or submission."),
		},
	}


def _count(doctype, filters):
	if not frappe.has_permission(doctype, "read"):
		return None
	rows = frappe.get_list(doctype, filters=filters, fields=["count(name) as count"], limit_page_length=1)
	return (rows[0].count or 0) if rows else 0


def _attention(company):
	rows = []
	definitions = (
		("Asset Repair", {"company": company, "repair_status": "Pending", "docstatus": ["<", 2]}, ["name", "asset", "asset_name", "repair_status", "failure_date", "repair_cost", "modified"], _("Repair awaiting completion")),
		("Asset Movement", {"company": company, "docstatus": 0}, ["name", "purpose", "transaction_date", "modified"], _("Movement awaiting submission")),
	)
	for doctype, filters, fields, title in definitions:
		if not frappe.has_permission(doctype, "read"):
			continue
		for row in frappe.get_list(doctype, filters=filters, fields=fields, order_by="modified desc", limit_page_length=5):
			rows.append({"doctype": doctype, "name": row.name, "title": title, "detail": row.get("asset_name") or row.get("asset") or row.get("purpose"), "status": row.get("repair_status"), "date": row.get("failure_date") or row.get("transaction_date"), "amount": row.get("repair_cost"), "modified": row.modified})
	rows.sort(key=lambda row: row["modified"], reverse=True)
	return rows[:8]


def _activity(company):
	rows = []
	definitions = {
		"Asset": ["name", "asset_name", "status", "gross_purchase_amount", "modified"],
		"Asset Movement": ["name", "purpose", "transaction_date", "docstatus", "modified"],
		"Asset Repair": ["name", "asset_name", "repair_status", "repair_cost", "modified"],
		"Asset Maintenance": ["name", "asset_name", "maintenance_team", "modified"],
	}
	for doctype, fields in definitions.items():
		if not frappe.has_permission(doctype, "read"):
			continue
		for row in frappe.get_list(doctype, filters={"company": company}, fields=fields, order_by="modified desc", limit_page_length=3):
			rows.append({"doctype": doctype, "name": row.name, "detail": row.get("asset_name") or row.get("purpose") or row.get("maintenance_team"), "status": row.get("status") or row.get("repair_status") or ("Submitted" if row.get("docstatus") == 1 else "Draft"), "amount": row.get("gross_purchase_amount") if row.get("gross_purchase_amount") is not None else row.get("repair_cost"), "modified": row.modified})
	rows.sort(key=lambda row: row["modified"], reverse=True)
	return rows[:8]
