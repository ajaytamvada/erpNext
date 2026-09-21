import frappe
from erpnext.accounts.report.profit_and_loss_statement import profit_and_loss_statement
from erpnext.accounts.utils import get_fiscal_year
from frappe import _
from frappe.utils import add_months, date_diff, getdate, nowdate


MAX_PERIOD_DAYS = 366


@frappe.whitelist()
def get_dashboard(company=None, from_date=None, to_date=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to view the executive overview."), frappe.PermissionError)

	companies = _get_permitted_companies()
	if not companies:
		return {
			"companies": [],
			"message": _("You do not have access to a company."),
		}

	company_by_name = {row.name: row for row in companies}
	company = company or frappe.defaults.get_user_default("Company") or companies[0].name
	if company not in company_by_name:
		frappe.throw(_("You do not have access to company {0}.").format(frappe.bold(company)), frappe.PermissionError)

	to_date = getdate(to_date or nowdate())
	from_date = getdate(from_date or add_months(to_date, -5))
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date."))
	if date_diff(to_date, from_date) > MAX_PERIOD_DAYS:
		frappe.throw(_("Select a period of one year or less."))

	currency = company_by_name[company].default_currency
	financials = _get_financials(company, from_date, to_date, currency)

	return {
		"companies": companies,
		"filters": {
			"company": company,
			"from_date": from_date,
			"to_date": to_date,
			"currency": currency,
		},
		"metrics": {
			"revenue": financials.get("income"),
			"expenses": financials.get("expense"),
			"pipeline": _get_pipeline(company, from_date, to_date),
			"overdue_receivables": _get_overdue_receivables(company, to_date),
		},
		"trend": financials.get("trend", []),
		"tasks": _get_tasks(company, to_date),
		"business_areas": _get_business_areas(),
		"activity": _get_recent_activity(company),
		"definitions": {
			"revenue": _("Total Income from the Profit and Loss report for the selected period."),
			"expenses": _("Total Expense from the Profit and Loss report for the selected period."),
			"pipeline": _("Open opportunity amount in company currency for opportunities dated in the selected period."),
			"overdue_receivables": _("Submitted sales invoice outstanding amount with a due date before the selected end date."),
		},
	}


def _get_permitted_companies():
	return frappe.get_list(
		"Company",
		fields=["name", "default_currency"],
		order_by="name asc",
		limit_page_length=100,
	)


def _get_financials(company, from_date, to_date, currency):
	if not frappe.has_permission("GL Entry", "read"):
		return {"income": None, "expense": None, "trend": []}

	from_fiscal_year = get_fiscal_year(from_date, company=company)[0]
	to_fiscal_year = get_fiscal_year(to_date, company=company)[0]
	filters = frappe._dict(
		company=company,
		filter_based_on="Date Range",
		period_start_date=from_date,
		period_end_date=to_date,
		from_fiscal_year=from_fiscal_year,
		to_fiscal_year=to_fiscal_year,
		periodicity="Monthly",
		accumulated_values=0,
		include_default_book_entries=1,
		presentation_currency=currency,
	)
	_columns, _data, _message, chart, report_summary, _primitive_summary = profit_and_loss_statement.execute(
		filters
	)
	income = report_summary[0].get("value") if report_summary else 0
	expense = report_summary[2].get("value") if len(report_summary or []) > 2 else 0
	datasets = {row.get("name"): row.get("values", []) for row in (chart or {}).get("data", {}).get("datasets", [])}
	labels = (chart or {}).get("data", {}).get("labels", [])
	trend = []
	for index, label in enumerate(labels):
		trend.append(
			{
				"label": label,
				"income": (datasets.get(_("Income")) or [0] * len(labels))[index] or 0,
				"expense": (datasets.get(_("Expense")) or [0] * len(labels))[index] or 0,
			}
		)
	return {"income": income or 0, "expense": expense or 0, "trend": trend}


def _get_pipeline(company, from_date, to_date):
	if not frappe.has_permission("Opportunity", "read"):
		return None
	result = frappe.get_list(
		"Opportunity",
		filters={
			"company": company,
			"transaction_date": ["between", [from_date, to_date]],
			"status": ["not in", ["Lost", "Closed"]],
		},
		fields=["sum(base_opportunity_amount) as value", "count(name) as count"],
		limit_page_length=1,
	)
	return {
		"value": (result[0].value or 0) if result else 0,
		"count": (result[0].count or 0) if result else 0,
	}


def _get_overdue_receivables(company, to_date):
	if not frappe.has_permission("Sales Invoice", "read"):
		return None
	result = frappe.get_list(
		"Sales Invoice",
		filters={
			"company": company,
			"docstatus": 1,
			"due_date": ["<", to_date],
			"outstanding_amount": [">", 0],
		},
		fields=["sum(outstanding_amount) as value", "count(name) as count"],
		limit_page_length=1,
	)
	return {
		"value": (result[0].value or 0) if result else 0,
		"count": (result[0].count or 0) if result else 0,
	}


def _get_tasks(company, to_date):
	tasks = []
	if frappe.has_permission("Workflow Action", "read"):
		workflow_actions = frappe.get_list(
			"Workflow Action",
			filters={"user": frappe.session.user, "status": "Open"},
			fields=["reference_doctype", "reference_name", "workflow_state", "modified"],
			order_by="modified desc",
			limit_page_length=8,
		)
		for action in workflow_actions:
			if not action.reference_doctype or not action.reference_name:
				continue
			if not frappe.has_permission(action.reference_doctype, "read", doc=action.reference_name):
				continue
			tasks.append(
				{
					"category": "approval",
					"title": _("{0} awaiting review").format(_(action.reference_doctype)),
					"meta": " · ".join(filter(None, [action.reference_name, action.workflow_state])),
					"action": _("Review"),
					"doctype": action.reference_doctype,
					"name": action.reference_name,
				}
			)
			if len(tasks) == 4:
				return tasks

	if frappe.has_permission("Sales Invoice", "read"):
		overdue = frappe.get_list(
			"Sales Invoice",
			filters={
				"company": company,
				"docstatus": 1,
				"due_date": ["<", to_date],
				"outstanding_amount": [">", 0],
			},
			fields=["name", "customer_name", "due_date", "outstanding_amount", "currency"],
			order_by="due_date asc",
			limit_page_length=4,
		)
		for invoice in overdue:
			days = date_diff(to_date, invoice.due_date)
			tasks.append(
				{
					"category": "alert",
					"title": _("Payment follow-up due"),
					"meta": _("{0} · {1} · {2} days overdue").format(
						invoice.name, invoice.customer_name or _("Customer"), days
					),
					"amount": invoice.outstanding_amount,
					"currency": invoice.currency,
					"action": _("View"),
					"doctype": "Sales Invoice",
					"name": invoice.name,
				}
			)
			if len(tasks) == 4:
				break
	return tasks


def _get_business_areas():
	areas = (
		("Procurement", "Buying", "Purchase Order", "shopping-cart"),
		("Sales", "Selling", "Sales Order", "trend-up"),
		("Finance", "Accounting", "GL Entry", "accounting"),
		("Inventory", "Stock", "Stock Entry", "stock"),
	)
	return [
		{"label": _(label), "route": route.lower(), "icon": icon}
		for label, route, reference_doctype, icon in areas
		if frappe.has_permission(reference_doctype, "read")
	]


def _get_recent_activity(company):
	definitions = (
		("Sales Invoice", "posting_date", "customer_name"),
		("Purchase Order", "transaction_date", "supplier_name"),
		("Delivery Note", "posting_date", "customer_name"),
	)
	activity = []
	for doctype, date_field, party_field in definitions:
		if not frappe.has_permission(doctype, "read"):
			continue
		for row in frappe.get_list(
			doctype,
			filters={"company": company, "docstatus": [">", 0]},
			fields=["name", "modified", "status", date_field, party_field],
			order_by="modified desc",
			limit_page_length=3,
		):
			activity.append(
				{
					"title": _("{0} updated").format(_(doctype)),
					"meta": " · ".join(filter(None, [row.get(party_field), row.name, row.status])),
					"modified": row.modified,
					"doctype": doctype,
					"name": row.name,
				}
			)
	activity.sort(key=lambda row: row["modified"], reverse=True)
	return activity[:3]
