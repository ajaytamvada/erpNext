import frappe
from frappe import _


QUALITY_DOCTYPES = ("Quality Inspection", "Quality Goal", "Quality Review", "Quality Action", "Non Conformance")


def _count(doctype, filters):
	if not frappe.has_permission(doctype, "read"):
		return None
	rows = frappe.get_list(doctype, filters=filters, fields=["count(name) as count"], limit_page_length=1)
	return (rows[0].count or 0) if rows else 0


@frappe.whitelist()
def get_overview():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to view Quality."), frappe.PermissionError)

	return {
		"metrics": {
			"draft_inspections": _count("Quality Inspection", {"docstatus": 0}),
			"open_reviews": _count("Quality Review", {"status": "Open"}),
			"open_actions": _count("Quality Action", {"status": "Open"}),
			"open_non_conformance": _count("Non Conformance", {"status": "Open"}),
		},
		"create_permissions": {
			doctype: frappe.has_permission(doctype, "create") for doctype in QUALITY_DOCTYPES
		},
		"reports": [{"label": _("Quality Review"), "route": "query-report/Review"}],
		"definitions": {
			"draft_inspections": _("Quality Inspections awaiting submission."),
			"open_reviews": _("Open Quality Reviews."),
			"open_actions": _("Open Quality Actions."),
			"open_non_conformance": _("Open Non Conformance records."),
		},
	}
