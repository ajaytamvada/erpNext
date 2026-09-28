import frappe
from frappe import _
from frappe.utils import nowdate


SALES_DOCTYPES = ("Lead", "Opportunity", "Quotation", "Sales Order", "Delivery Note", "Sales Invoice")


@frappe.whitelist()
def get_overview(company=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to view Sales and CRM."), frappe.PermissionError)

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
		"filters": {"company": company, "currency": company_by_name[company].default_currency},
		"metrics": _get_metrics(company),
		"pipeline": _get_pipeline(company),
		"attention": _get_attention(company),
		"activity": _get_recent_activity(company),
		"create_permissions": {doctype: frappe.has_permission(doctype, "create") for doctype in SALES_DOCTYPES},
		"definitions": {
			"open_opportunities": _("Open and replied Opportunities for the selected company."),
			"active_quotations": _("Submitted Quotations that remain open, replied, or partially ordered."),
			"orders_to_deliver": _("Submitted Sales Orders that are not closed and remain below 100% delivered."),
			"orders_to_bill": _("Submitted Sales Orders that are not closed and remain below 100% billed."),
		},
	}


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


def _get_metrics(company):
	return {
		"open_opportunities": _count(
			"Opportunity", {"company": company, "status": ["in", ["Open", "Replied"]]}
		),
		"active_quotations": _count(
			"Quotation",
			{"company": company, "docstatus": 1, "status": ["in", ["Open", "Replied", "Partially Ordered"]]},
		),
		"orders_to_deliver": _count(
			"Sales Order", {"company": company, "docstatus": 1, "status": ["!=", "Closed"], "per_delivered": ["<", 100]}
		),
		"orders_to_bill": _count(
			"Sales Order", {"company": company, "docstatus": 1, "status": ["!=", "Closed"], "per_billed": ["<", 100]}
		),
	}


def _get_pipeline(company):
	definitions = (
		("Lead", {"company": company, "status": ["not in", ["Converted", "Do Not Contact"]]}),
		("Opportunity", {"company": company, "status": ["in", ["Open", "Replied"]]}),
		("Quotation", {"company": company, "docstatus": ["<", 2]}),
		("Sales Order", {"company": company, "docstatus": ["<", 2]}),
		("Delivery Note", {"company": company, "docstatus": ["<", 2]}),
		("Sales Invoice", {"company": company, "docstatus": ["<", 2]}),
	)
	return [{"doctype": doctype, "count": _count(doctype, filters)} for doctype, filters in definitions]


def _get_attention(company):
	today = nowdate()
	definitions = (
		(
			"Opportunity",
			{"company": company, "status": ["in", ["Open", "Replied"]], "expected_closing": ["<", today]},
			["name", "customer_name", "party_name", "status", "expected_closing", "opportunity_amount", "currency", "modified"],
			_("Opportunity past expected closing"),
		),
		(
			"Quotation",
			{"company": company, "docstatus": 1, "status": ["in", ["Open", "Replied", "Partially Ordered"]], "valid_till": ["<", today]},
			["name", "customer_name", "party_name", "status", "valid_till", "grand_total", "currency", "modified"],
			_("Quotation past validity"),
		),
		(
			"Sales Order",
			{"company": company, "docstatus": 1, "status": ["!=", "Closed"], "per_delivered": ["<", 100], "delivery_date": ["<", today]},
			["name", "customer_name", "status", "delivery_date", "grand_total", "currency", "modified"],
			_("Order past delivery date"),
		),
		(
			"Sales Invoice",
			{"company": company, "docstatus": 1, "due_date": ["<", today], "outstanding_amount": [">", 0]},
			["name", "customer_name", "status", "due_date", "outstanding_amount", "currency", "modified"],
			_("Invoice payment overdue"),
		),
	)
	rows = []
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
					"party": row.get("customer_name") or row.get("party_name"),
					"status": row.get("status"),
					"date": row.get("expected_closing") or row.get("valid_till") or row.get("delivery_date") or row.get("due_date"),
					"amount": row.get("opportunity_amount") or row.get("grand_total") or row.get("outstanding_amount"),
					"currency": row.get("currency"),
					"modified": row.modified,
				}
			)
	rows.sort(key=lambda row: row["modified"], reverse=True)
	return rows[:8]


def _get_recent_activity(company):
	activity = []
	definitions = {
		"Lead": ["name", "lead_name", "company_name", "status", "modified"],
		"Opportunity": ["name", "customer_name", "party_name", "status", "opportunity_amount", "currency", "modified"],
		"Quotation": ["name", "customer_name", "party_name", "status", "grand_total", "currency", "modified"],
		"Sales Order": ["name", "customer_name", "status", "grand_total", "currency", "modified"],
		"Delivery Note": ["name", "customer_name", "status", "grand_total", "currency", "modified"],
		"Sales Invoice": ["name", "customer_name", "status", "grand_total", "currency", "modified"],
	}
	for doctype, fields in definitions.items():
		if not frappe.has_permission(doctype, "read"):
			continue
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
					"party": row.get("lead_name") or row.get("customer_name") or row.get("party_name") or row.get("company_name"),
					"status": row.get("status"),
					"amount": row.get("opportunity_amount") or row.get("grand_total"),
					"currency": row.get("currency"),
					"modified": row.modified,
				}
			)
	activity.sort(key=lambda row: row["modified"], reverse=True)
	return activity[:8]
