import frappe
from frappe import _
from frappe.utils import now_datetime


SUPPORT_DOCTYPES = ("Issue", "Service Level Agreement", "Warranty Claim")


def _count(doctype, filters):
	if not frappe.has_permission(doctype, "read"):
		return None
	rows = frappe.get_list(doctype, filters=filters, fields=["count(name) as count"], limit_page_length=1)
	return (rows[0].count or 0) if rows else 0


@frappe.whitelist()
def get_overview(company=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to view Support."), frappe.PermissionError)

	companies = frappe.get_list("Company", fields=["name"], order_by="name asc", limit_page_length=100)
	company = company or frappe.defaults.get_user_default("Company") or (companies[0].name if companies else None)
	if company and company not in {row.name for row in companies}:
		frappe.throw(_("You do not have access to this company."), frappe.PermissionError)
	filters = {"company": company} if company else {}

	return {
		"companies": companies,
		"company": company,
		"metrics": {
			"open_issues": _count("Issue", {**filters, "status": ["not in", ["Closed", "Resolved"]]}),
			"sla_due": _count(
				"Issue",
				{
					**filters,
					"status": ["not in", ["Closed", "Resolved"]],
					"sla_resolution_by": ["<", now_datetime()],
				},
			),
			"open_warranty_claims": _count(
				"Warranty Claim", {**filters, "status": ["not in", ["Closed", "Cancelled"]]}
			),
			"active_slas": _count("Service Level Agreement", {"enabled": 1}),
		},
		"create_permissions": {
			doctype: frappe.has_permission(doctype, "create") for doctype in SUPPORT_DOCTYPES
		},
		"reports": [
			{"label": _("Issue Analytics"), "route": "query-report/Issue Analytics"},
			{"label": _("Issue Summary"), "route": "query-report/Issue Summary"},
			{"label": _("First Response Time for Issues"), "route": "query-report/First Response Time for Issues"},
		],
		"definitions": {
			"open_issues": _("Issues not closed or resolved."),
			"sla_due": _("Open Issues whose native SLA resolution deadline has passed."),
			"open_warranty_claims": _("Warranty Claims not closed or cancelled."),
			"active_slas": _("Enabled Service Level Agreements."),
		},
	}
