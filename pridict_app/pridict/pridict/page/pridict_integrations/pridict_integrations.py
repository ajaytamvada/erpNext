import frappe
from frappe import _


INTEGRATION_DOCTYPES = (
	"Webhook",
	"Social Login Key",
	"LDAP Settings",
	"OAuth Client",
	"OAuth Provider Settings",
	"SMS Settings",
	"Slack Webhook URL",
	"Google Settings",
	"Google Contacts",
	"Google Calendar",
	"Google Drive",
	"Dropbox Settings",
	"S3 Backup Settings",
	"Plaid Settings",
)


def _count(doctype):
	if not frappe.has_permission(doctype, "read"):
		return None
	rows = frappe.get_list(doctype, fields=["count(name) as count"], limit_page_length=1)
	return (rows[0].count or 0) if rows else 0


@frappe.whitelist()
def get_overview():
	frappe.only_for("System Manager")
	return {
		"metrics": {
			"webhooks": _count("Webhook"),
			"oauth_clients": _count("OAuth Client"),
			"social_login_providers": _count("Social Login Key"),
			"google_calendars": _count("Google Calendar"),
		},
		"definitions": {
			"webhooks": _("Configured native webhook records."),
			"oauth_clients": _("Registered OAuth clients."),
			"social_login_providers": _("Configured social login providers."),
			"google_calendars": _("Configured Google Calendar connections."),
		},
		"groups": [
			{
				"label": _("Authentication"),
				"description": _("Social login, LDAP, and OAuth configuration using native protected fields."),
				"items": ["Social Login Key", "LDAP Settings", "OAuth Client", "OAuth Provider Settings"],
			},
			{
				"label": _("Communication channels"),
				"description": _("Webhooks, SMS gateways, and Slack document notifications."),
				"items": ["Webhook", "SMS Settings", "Slack Webhook URL"],
			},
			{
				"label": _("Google services"),
				"description": _("Google authorization, contacts, calendars, and Drive integration."),
				"items": ["Google Settings", "Google Contacts", "Google Calendar", "Google Drive"],
			},
			{
				"label": _("Backup and banking"),
				"description": _("Backup providers and banking connections; secrets stay inside native controls."),
				"items": ["Dropbox Settings", "S3 Backup Settings", "Plaid Settings"],
			},
		],
		"create_permissions": {
			doctype: frappe.has_permission(doctype, "create") for doctype in INTEGRATION_DOCTYPES
		},
		"compatibility_routes": [
			{"label": _("ERPNext Integrations workspace"), "route": "erpnext-integrations"},
			{"label": _("Integrations workspace"), "route": "integrations"},
		],
	}
