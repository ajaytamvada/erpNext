from __future__ import annotations

import frappe
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.utils import cint

from pridict.schema_intelligence.reviews import highest_severity, meets_threshold


def notification_recipients(settings) -> list[str]:
	users = set(_lines(settings.notification_users))
	roles = _lines(settings.notification_roles)
	if roles:
		users.update(
			frappe.get_all(
				"Has Role",
				filters={"role": ["in", roles], "parenttype": "User"},
				pluck="parent",
			)
		)
	if not users:
		users.update(frappe.get_all("Has Role", filters={"role": "Schema Reviewer", "parenttype": "User"}, pluck="parent"))
	return sorted(
		user
		for user in users
		if user != "Guest" and frappe.db.get_value("User", user, "enabled")
	)


def notify_review(review_name: str) -> dict:
	settings = frappe.get_single("Schema Intelligence Settings")
	if not cint(settings.notification_enabled):
		return {"sent": False, "reason": "disabled"}
	review = frappe.get_doc("Schema Change Review", review_name)
	if review.notification_state == "Sent":
		return {"sent": False, "reason": "already-sent"}
	severity = highest_severity(review)
	if not meets_threshold(severity, settings.notification_minimum_severity or "Warning"):
		return {"sent": False, "reason": "below-threshold"}
	recipients = notification_recipients(settings)
	if not recipients:
		return {"sent": False, "reason": "no-recipients"}
	try:
		make_notification_logs(
			{
				"subject": f"Schema review {review.name} has {severity} changes",
				"type": "Schema Intelligence",
				"document_type": "Schema Change Review",
				"document_name": review.name,
				"from_user": "Administrator",
			},
			recipients,
		)
		frappe.db.set_value("Schema Change Review", review.name, "notification_state", "Sent")
		return {"sent": True, "recipients": recipients}
	except Exception:
		frappe.db.set_value("Schema Change Review", review.name, "notification_state", "Failed")
		frappe.log_error(title="Schema Intelligence notification failure")
		return {"sent": False, "reason": "failed"}


def notify_operational_warning(subject: str, message: str) -> dict:
	settings = frappe.get_single("Schema Intelligence Settings")
	if not cint(settings.notification_enabled):
		return {"sent": False, "reason": "disabled"}
	recipients = notification_recipients(settings)
	if not recipients:
		return {"sent": False, "reason": "no-recipients"}
	make_notification_logs(
		{"subject": subject, "email_content": message, "type": "Schema Intelligence"},
		recipients,
	)
	return {"sent": True, "recipients": recipients}


def _lines(value: str | None) -> list[str]:
	return sorted({item.strip() for item in (value or "").replace(",", "\n").splitlines() if item.strip()})
