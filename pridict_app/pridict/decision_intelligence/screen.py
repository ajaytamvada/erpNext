"""Screen API handler for the Decision Intelligence Desk page."""
from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from pridict.decision_intelligence.rules import DEFAULT_RULES
from pridict.decision_intelligence.service import evaluate_decisions

SCREEN_ROLES = ("System Manager", "Process Analyst", "Purchase Manager")
DEFAULT_LIMIT = 500


def require_access():
	if frappe.session.user == "Guest" or not set(SCREEN_ROLES).intersection(frappe.get_roles()):
		frappe.throw(
			_("Decision Intelligence requires the Purchase Manager, Process Analyst, or System Manager role."),
			frappe.PermissionError,
		)


@frappe.whitelist()
def get_options() -> dict[str, Any]:
	require_access()
	companies = frappe.get_list("Company", pluck="name", order_by="name asc", limit_page_length=0)
	default_company = frappe.defaults.get_user_default("Company")
	if not default_company and companies:
		default_company = companies[0]

	today = frappe.utils.today()
	# Default to last 90 days
	start_date = frappe.utils.add_days(today, -90)

	return {
		"companies": companies,
		"default_company": default_company,
		"today": today,
		"start_date": start_date,
		"timezone": frappe.utils.get_system_timezone(),
		"record_limit": DEFAULT_LIMIT,
		"rules": [r.to_dict() for r in DEFAULT_RULES],
	}


@frappe.whitelist()
def get_decision_analysis(
	company: str,
	start_date: str = "",
	end_date: str = "",
	limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
	require_access()
	if not company:
		frappe.throw(_("Company is required to evaluate decisions."), frappe.ValidationError)

	if not frappe.has_permission("Purchase Order", "read"):
		frappe.throw(_("Read permission for Purchase Orders is required."), frappe.PermissionError)

	result = evaluate_decisions(company, start_date, end_date, limit=int(limit or DEFAULT_LIMIT))
	return result.to_dict()
