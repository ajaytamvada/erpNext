"""Seed automation roles, the automation user and settings (runs after install/migrate)."""

from __future__ import annotations

import frappe
from frappe.utils import validate_email_address

ROLES = ("Automation Manager", "Automation Viewer")
FALLBACK_DOMAIN = "pridict.local"


def ensure_automation_setup():
	if not frappe.db.exists("DocType", "Automation Settings"):
		return
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)
	settings = frappe.get_single("Automation Settings")
	changed = False
	if not settings.default_run_as:
		settings.default_run_as = ensure_automation_user()
		changed = True
	if not settings.roles_granted:
		# Once per site: admins can build automations from day one. Later removals stick.
		grant_manager_role()
		settings.roles_granted = 1
		changed = True
	if changed:
		settings.flags.ignore_permissions = True
		settings.save()


def automation_user_email() -> str:
	site = (frappe.local.site or "").strip()
	email = f"automation@{site}"
	return email if site and validate_email_address(email) else f"automation@{FALLBACK_DOMAIN}"


def ensure_automation_user() -> str:
	"""A dedicated Run As user with no roles; admins grant it exactly what automations need."""
	email = automation_user_email()
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Automation",
				"user_type": "System User",
				"send_welcome_email": 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
	return email


def grant_manager_role():
	holders = frappe.get_all(
		"Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent"
	)
	for user in set(holders) - {"Administrator", "Guest"}:
		if frappe.db.get_value("User", user, "enabled"):
			frappe.get_doc("User", user).add_roles("Automation Manager")
