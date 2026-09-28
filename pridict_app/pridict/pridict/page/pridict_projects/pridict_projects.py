import frappe
from frappe import _
from frappe.utils import nowdate


PROJECT_DOCTYPES = ("Project", "Task", "Timesheet", "Activity Type")


def _count(doctype, filters):
	if not frappe.has_permission(doctype, "read"):
		return None
	rows = frappe.get_list(doctype, filters=filters, fields=["count(name) as count"], limit_page_length=1)
	return (rows[0].count or 0) if rows else 0


@frappe.whitelist()
def get_overview(company=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to view Projects."), frappe.PermissionError)
	companies = frappe.get_list("Company", fields=["name", "default_currency"], order_by="name asc", limit_page_length=100)
	if not companies:
		return {"companies": [], "message": _("You do not have access to a company.")}
	company_by_name = {row.name: row for row in companies}
	company = company or frappe.defaults.get_user_default("Company") or companies[0].name
	if company not in company_by_name:
		frappe.throw(_("You do not have access to company {0}.").format(frappe.bold(company)), frappe.PermissionError)
	today = nowdate()
	return {
		"companies": companies,
		"filters": {"company": company, "currency": company_by_name[company].default_currency},
		"metrics": {
			"open_projects": _count("Project", {"company": company, "status": ["in", ["Open", "On hold"]]}),
			"overdue_tasks": _count("Task", {"company": company, "status": ["not in", ["Completed", "Cancelled"]], "exp_end_date": ["<", today]}),
			"draft_timesheets": _count("Timesheet", {"company": company, "docstatus": 0}),
			"unbilled_timesheets": _count("Timesheet", {"company": company, "docstatus": 1, "status": ["in", ["Submitted", "Partially Billed"]]}),
		},
		"attention": _get_attention(company, today),
		"activity": _get_activity(company),
		"create_permissions": {doctype: frappe.has_permission(doctype, "create") for doctype in PROJECT_DOCTYPES},
		"reports": [
			{"label": _("Project Summary"), "route": "query-report/Project Summary"},
			{"label": _("Project Billing Summary"), "route": "query-report/Project Billing Summary"},
			{"label": _("Delayed Tasks Summary"), "route": "query-report/Delayed Tasks Summary"},
			{"label": _("Daily Timesheet Summary"), "route": "query-report/Daily Timesheet Summary"},
		],
		"definitions": {
			"open_projects": _("Open or on-hold Projects for the selected company."),
			"overdue_tasks": _("Incomplete Tasks with expected end dates before today."),
			"draft_timesheets": _("Draft Timesheets for the selected company."),
			"unbilled_timesheets": _("Submitted or partially billed Timesheets."),
		},
	}


def _get_attention(company, today):
	rows = []
	definitions = (
		("Task", {"company": company, "status": ["not in", ["Completed", "Cancelled"]], "exp_end_date": ["<", today]}, ["name", "subject", "project", "status", "priority", "exp_end_date", "modified"], _("Task past expected end date")),
		("Project", {"company": company, "status": ["in", ["Open", "On hold"]], "expected_end_date": ["<", today]}, ["name", "project_name", "customer", "status", "expected_end_date", "percent_complete", "modified"], _("Project past expected end date")),
		("Timesheet", {"company": company, "docstatus": 0}, ["name", "employee", "start_date", "end_date", "total_hours", "modified"], _("Timesheet awaiting submission")),
	)
	for doctype, filters, fields, title in definitions:
		if not frappe.has_permission(doctype, "read"):
			continue
		for row in frappe.get_list(doctype, filters=filters, fields=fields, order_by="modified desc", limit_page_length=5):
			rows.append({"doctype": doctype, "name": row.name, "title": title, "detail": row.get("subject") or row.get("project_name") or row.get("employee") or row.name, "status": row.get("status") or row.get("priority"), "date": row.get("exp_end_date") or row.get("expected_end_date") or row.get("end_date"), "progress": row.get("percent_complete"), "hours": row.get("total_hours"), "modified": row.modified})
	rows.sort(key=lambda row: row["modified"], reverse=True)
	return rows[:8]


def _get_activity(company):
	rows = []
	definitions = {
		"Project": ["name", "project_name", "status", "percent_complete", "modified"],
		"Task": ["name", "subject", "project", "status", "progress", "modified"],
		"Timesheet": ["name", "employee", "status", "total_hours", "modified"],
	}
	for doctype, fields in definitions.items():
		if not frappe.has_permission(doctype, "read"):
			continue
		for row in frappe.get_list(doctype, filters={"company": company}, fields=fields, order_by="modified desc", limit_page_length=4):
			rows.append({"doctype": doctype, "name": row.name, "detail": row.get("project_name") or row.get("subject") or row.get("employee"), "status": row.get("status"), "progress": row.get("percent_complete") if row.get("percent_complete") is not None else row.get("progress"), "hours": row.get("total_hours"), "modified": row.modified})
	rows.sort(key=lambda row: row["modified"], reverse=True)
	return rows[:8]
