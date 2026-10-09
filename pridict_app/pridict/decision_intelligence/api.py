"""Whitelisted public API endpoints for Decision Intelligence."""
from __future__ import annotations

import frappe

from pridict.decision_intelligence.screen import (
	get_decision_analysis as _get_decision_analysis,
	get_options as _get_options,
)


@frappe.whitelist()
def get_options():
	"""Returns accessible companies, date defaults, and configured rules."""
	return _get_options()


@frappe.whitelist()
def get_decision_analysis(company: str, start_date: str = "", end_date: str = "", limit: int = 500):
	"""Returns comprehensive decision evaluation, anomalies, vendor scorecard, and recommendations."""
	return _get_decision_analysis(company=company, start_date=start_date, end_date=end_date, limit=limit)
