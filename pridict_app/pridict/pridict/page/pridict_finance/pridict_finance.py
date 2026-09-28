import frappe
from frappe import _
from frappe.utils import add_months, getdate, nowdate

from pridict.pridict.page.pridict_home.pridict_home import MAX_PERIOD_DAYS, _get_financials


FINANCE_DOCTYPES = ("Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry")


@frappe.whitelist()
def get_overview(company=None, from_date=None, to_date=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to view Finance."), frappe.PermissionError)

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

	to_date = getdate(to_date or nowdate())
	from_date = getdate(from_date or add_months(to_date, -5))
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date."))
	if (to_date - from_date).days > MAX_PERIOD_DAYS:
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
			"overdue_receivables": _count_overdue("Sales Invoice", company, to_date),
			"overdue_payables": _count_overdue("Purchase Invoice", company, to_date),
		},
		"attention": _get_attention(company, to_date),
		"activity": _get_recent_activity(company, currency),
		"create_permissions": {doctype: frappe.has_permission(doctype, "create") for doctype in FINANCE_DOCTYPES},
		"reports": [
			{"label": _("Profit and Loss Statement"), "route": "query-report/Profit and Loss Statement"},
			{"label": _("Balance Sheet"), "route": "query-report/Balance Sheet"},
			{"label": _("Cash Flow"), "route": "query-report/Cash Flow"},
			{"label": _("General Ledger"), "route": "query-report/General Ledger"},
			{"label": _("Accounts Receivable"), "route": "query-report/Accounts Receivable"},
			{"label": _("Accounts Payable"), "route": "query-report/Accounts Payable"},
		],
		"definitions": {
			"revenue": _("Total Income from the Profit and Loss report for the selected period."),
			"expenses": _("Total Expense from the Profit and Loss report for the selected period."),
			"overdue_receivables": _("Submitted Sales Invoices due before the selected end date with an outstanding balance."),
			"overdue_payables": _("Submitted Purchase Invoices due before the selected end date with an outstanding balance."),
		},
	}


def _count_overdue(doctype, company, to_date):
	if not frappe.has_permission(doctype, "read"):
		return None
	result = frappe.get_list(
		doctype,
		filters={"company": company, "docstatus": 1, "due_date": ["<", to_date], "outstanding_amount": [">", 0]},
		fields=["count(name) as count"],
		limit_page_length=1,
	)
	return (result[0].count or 0) if result else 0


def _get_attention(company, to_date):
	rows = []
	for doctype, party_field in (("Sales Invoice", "customer_name"), ("Purchase Invoice", "supplier_name")):
		if not frappe.has_permission(doctype, "read"):
			continue
		for row in frappe.get_list(
			doctype,
			filters={"company": company, "docstatus": 1, "due_date": ["<", to_date], "outstanding_amount": [">", 0]},
			fields=["name", party_field, "due_date", "outstanding_amount", "currency", "status", "modified"],
			order_by="due_date asc",
			limit_page_length=5,
		):
			rows.append(
				{
					"doctype": doctype,
					"name": row.name,
					"party": row.get(party_field),
					"due_date": row.due_date,
					"amount": row.outstanding_amount,
					"currency": row.currency,
					"status": row.status,
					"modified": row.modified,
				}
			)
	rows.sort(key=lambda row: (row["due_date"], row["modified"]))
	return rows[:8]


def _get_recent_activity(company, company_currency):
	activity = []
	for doctype in FINANCE_DOCTYPES:
		if not frappe.has_permission(doctype, "read"):
			continue
		fields = ["name", "modified", "docstatus"]
		if doctype in {"Sales Invoice", "Purchase Invoice"}:
			fields.extend(["status", "grand_total", "currency"])
		elif doctype == "Payment Entry":
			fields.extend(["payment_type", "paid_amount", "paid_from_account_currency"])
		else:
			fields.extend(["voucher_type", "total_debit", "company"])
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
					"status": row.get("status") or row.get("payment_type") or row.get("voucher_type"),
					"amount": row.get("grand_total") or row.get("paid_amount") or row.get("total_debit"),
					"currency": row.get("currency") or row.get("paid_from_account_currency") or company_currency,
					"modified": row.modified,
				}
			)
	activity.sort(key=lambda row: row["modified"], reverse=True)
	return activity[:6]
