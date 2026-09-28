import frappe
from frappe import _


ADMINISTRATION_DOCTYPES = (
	"User",
	"Role",
	"Role Profile",
	"User Permission",
	"Workflow",
	"Workflow State",
	"Notification",
	"Email Account",
	"Email Template",
	"Auto Email Report",
	"Data Import",
	"Data Export",
	"Print Format",
	"Print Settings",
	"System Settings",
	"Global Defaults",
	"Website Settings",
	"Employee",
)


def _count(doctype, filters=None):
	if not frappe.has_permission(doctype, "read"):
		return None
	rows = frappe.get_list(
		doctype,
		filters=filters or {},
		fields=["count(name) as count"],
		limit_page_length=1,
	)
	return (rows[0].count or 0) if rows else 0


@frappe.whitelist()
def get_overview():
	frappe.only_for("System Manager")
	return {
		"metrics": {
			"enabled_users": _count("User", {"enabled": 1}),
			"workflows": _count("Workflow"),
			"notifications": _count("Notification"),
			"email_accounts": _count("Email Account"),
		},
		"definitions": {
			"enabled_users": _("Enabled user accounts."),
			"workflows": _("Configured document workflows."),
			"notifications": _("Configured native notifications."),
			"email_accounts": _("Configured incoming and outgoing email accounts."),
		},
		"groups": [
			{
				"label": _("People and access"),
				"description": _("Users, roles, role profiles, user permissions, and the core Employee master."),
				"items": ["User", "Role", "Role Profile", "User Permission", "Employee"],
			},
			{
				"label": _("Workflow and communication"),
				"description": _("Approvals, notifications, email accounts, templates, and scheduled reports."),
				"items": ["Workflow", "Workflow State", "Notification", "Email Account", "Email Template", "Auto Email Report"],
			},
			{
				"label": _("Data and printing"),
				"description": _("Native import, export, print-format, and print-setting tools."),
				"items": ["Data Import", "Data Export", "Print Format", "Print Settings"],
			},
			{
				"label": _("System configuration"),
				"description": _("Site-wide defaults and settings, kept in their native protected forms."),
				"items": ["System Settings", "Global Defaults", "Website Settings"],
			},
		],
		"create_permissions": {
			doctype: frappe.has_permission(doctype, "create") for doctype in ADMINISTRATION_DOCTYPES
		},
		"compatibility_routes": [
			{"label": _("ERPNext Settings workspace"), "route": "erpnext-settings"},
			{"label": _("Users workspace"), "route": "users"},
			{"label": _("Tools workspace"), "route": "tools"},
		],
	}
