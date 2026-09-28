import frappe
from frappe import _


PURCHASING_DOCTYPES = (
	"Material Request",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
)


@frappe.whitelist()
def get_overview(company=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to view Procurement."), frappe.PermissionError)

	companies = frappe.get_list(
		"Company",
		fields=["name", "default_currency"],
		order_by="name asc",
		limit_page_length=100,
	)
	if not companies:
		return {"companies": [], "message": _("You do not have access to a company.")}

	company_by_name = {row.name: row for row in companies}
	company = company or frappe.defaults.get_user_default("Company") or companies[0].name
	if company not in company_by_name:
		frappe.throw(_("You do not have access to company {0}.").format(frappe.bold(company)), frappe.PermissionError)

	return {
		"companies": companies,
		"filters": {
			"company": company,
			"currency": company_by_name[company].default_currency,
		},
		"metrics": _get_metrics(company),
		"pipeline": _get_pipeline(company),
		"attention": _get_attention(company),
		"activity": _get_recent_activity(company),
		"create_permissions": {doctype: frappe.has_permission(doctype, "create") for doctype in PURCHASING_DOCTYPES},
		"definitions": {
			"material_requests": _("Submitted Material Requests for the selected company."),
			"purchase_orders_to_receive": _("Submitted Purchase Orders with less than 100% received."),
			"purchase_orders_to_bill": _("Submitted Purchase Orders with less than 100% billed."),
			"unpaid_purchase_invoices": _("Submitted Purchase Invoices with an outstanding amount greater than zero."),
		},
	}


def _get_metrics(company):
	return {
		"material_requests": _count("Material Request", {"company": company, "docstatus": 1}),
		"purchase_orders_to_receive": _count(
			"Purchase Order", {"company": company, "docstatus": 1, "per_received": ["<", 100]}
		),
		"purchase_orders_to_bill": _count(
			"Purchase Order", {"company": company, "docstatus": 1, "per_billed": ["<", 100]}
		),
		"unpaid_purchase_invoices": _count(
			"Purchase Invoice", {"company": company, "docstatus": 1, "outstanding_amount": [">", 0]}
		),
	}


def _get_pipeline(company):
	definitions = (
		("Material Request", {"company": company, "docstatus": ["<", 2]}),
		("Purchase Order", {"company": company, "docstatus": ["<", 2]}),
		("Purchase Receipt", {"company": company, "docstatus": ["<", 2]}),
		("Purchase Invoice", {"company": company, "docstatus": ["<", 2]}),
	)
	return [{"doctype": doctype, "count": _count(doctype, filters)} for doctype, filters in definitions]


def _count(doctype, filters):
	if not frappe.has_permission(doctype, "read"):
		return None
	result = frappe.get_list(
		doctype,
		filters=filters,
		fields=["count(name) as count"],
		limit_page_length=1,
	)
	return (result[0].count or 0) if result else 0


def _get_attention(company):
	rows = []
	definitions = (
		(
			"Material Request",
			{"company": company, "docstatus": 1, "per_ordered": ["<", 100]},
			["name", "status", "schedule_date", "modified"],
			_("Request awaiting ordering"),
		),
		(
			"Purchase Order",
			{"company": company, "docstatus": 1, "per_received": ["<", 100]},
			["name", "supplier_name", "status", "schedule_date", "modified"],
			_("Order awaiting receipt"),
		),
		(
			"Purchase Invoice",
			{"company": company, "docstatus": 1, "outstanding_amount": [">", 0]},
			["name", "supplier_name", "status", "due_date", "outstanding_amount", "currency", "modified"],
			_("Invoice awaiting payment"),
		),
	)

	for doctype, filters, fields, title in definitions:
		if not frappe.has_permission(doctype, "read"):
			continue
		for row in frappe.get_list(
			doctype,
			filters=filters,
			fields=fields,
			order_by="modified desc",
			limit_page_length=4,
		):
			rows.append(
				{
					"doctype": doctype,
					"name": row.name,
					"title": title,
					"party": row.get("supplier_name"),
					"status": row.get("status"),
					"date": row.get("schedule_date") or row.get("due_date"),
					"amount": row.get("outstanding_amount"),
					"currency": row.get("currency"),
					"modified": row.modified,
				}
			)
	rows.sort(key=lambda row: row["modified"], reverse=True)
	return rows[:8]


def _get_recent_activity(company):
	activity = []
	for doctype in PURCHASING_DOCTYPES:
		if not frappe.has_permission(doctype, "read"):
			continue
		fields = ["name", "status", "modified"]
		if doctype != "Material Request":
			fields.append("supplier_name")
		for row in frappe.get_list(
			doctype,
			filters={"company": company},
			fields=fields,
			order_by="modified desc",
			limit_page_length=3,
		):
			activity.append(
				{
					"doctype": doctype,
					"name": row.name,
					"party": row.get("supplier_name"),
					"status": row.get("status"),
					"modified": row.modified,
				}
			)
	activity.sort(key=lambda row: row["modified"], reverse=True)
	return activity[:6]
