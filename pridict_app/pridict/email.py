import frappe
from frappe import _


def get_welcome_email_subject():
	company = frappe.defaults.get_global_default("company")
	return _("Welcome to {0}").format(company or "Pridict")
