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
	if not settings.architect_model:
		settings.architect_model = ensure_architect_model()
		changed = changed or bool(settings.architect_model)
	if not settings.ai_step_model and frappe.db.exists("LLM Model Config", BASE_MODEL):
		# AI steps do short, bounded jobs: the cheaper procurement model is enough.
		settings.ai_step_model = BASE_MODEL
		changed = True
	if not settings.roles_granted:
		# Once per site: admins can build automations from day one. Later removals stick.
		grant_manager_role()
		settings.roles_granted = 1
		changed = True
	if changed:
		settings.flags.ignore_permissions = True
		settings.save()
	from pridict.automation.maintenance import revalidate_active

	revalidate_active()


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


ARCHITECT_MODEL = "automation-architect"
BASE_MODEL = "procurement-reasoning"


def ensure_architect_model() -> str | None:
	"""LLM Model Config for the AI architect, cloned from the procurement model on first setup.

	Same deployment, more reasoning, the procurement config as fallback. Production sites can
	point it at a full-size model later (design Section 8.4).
	"""
	if frappe.db.exists("LLM Model Config", ARCHITECT_MODEL):
		return ARCHITECT_MODEL
	base = frappe.db.get_value(
		"LLM Model Config", BASE_MODEL, ["provider", "model_id", "status", "timeout_s"], as_dict=True
	)
	if not base:
		return None
	frappe.get_doc(
		{
			"doctype": "LLM Model Config",
			"config_name": ARCHITECT_MODEL,
			"provider": base.provider,
			"model_id": base.model_id,
			"status": base.status,
			"reasoning_effort": "medium",
			"max_tokens": 16000,
			"timeout_s": max(base.timeout_s or 60, 120),
			"fallback": BASE_MODEL,
			"description": "AI architect for the Automation Builder.",
		}
	).insert(ignore_permissions=True)
	return ARCHITECT_MODEL


def grant_manager_role():
	holders = frappe.get_all(
		"Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent"
	)
	for user in set(holders) - {"Administrator", "Guest"}:
		if frappe.db.get_value("User", user, "enabled"):
			frappe.get_doc("User", user).add_roles("Automation Manager")
