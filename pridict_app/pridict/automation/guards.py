"""Guardrails around automation runs: site switches, rate limits, email caps, auto-pause."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime

SETTINGS = "Automation Settings"
COUNTER_PREFIX = "pridict_automation"


class GuardError(Exception):
	"""A guardrail stopped a run or a step."""


def settings():
	return frappe.get_cached_doc(SETTINGS)


def enabled() -> bool:
	"""Automations may start: the feature is on and the kill switch is off."""
	current = settings()
	return bool(current.enabled) and not current.pause_all


def max_chain_depth() -> int:
	return settings().max_chain_depth or 3


def _counter(key: str, expires_in: int, amount: int = 1) -> int:
	cache = frappe.cache()
	full_key = cache.make_key(f"{COUNTER_PREFIX}:{key}")
	value = cache.incrby(full_key, amount)
	if value == amount:
		cache.expire(full_key, expires_in)
	return value


def _hour() -> str:
	return now_datetime().strftime("%Y%m%d%H")


def _day() -> str:
	return now_datetime().strftime("%Y%m%d")


def allow_run(automation: str) -> bool:
	"""Count one run against the automation's hourly limit. False means drop the event."""
	limit = frappe.db.get_value("Automation", automation, "max_runs_per_hour") or 0
	if not limit:
		return True
	count = _counter(f"runs:{automation}:{_hour()}", 3600)
	if count <= limit:
		return True
	if count == limit + 1:
		# Tell the owner once per hour, not once per dropped event.
		notify_owner(
			automation,
			_(
				"Automation {0} hit its limit of {1} runs per hour; further events this hour are ignored."
			).format(automation, limit),
		)
	return False


def count_email(automation: str, recipients: int = 1):
	"""Count one email against the automation's and the site's daily caps; raise when exceeded."""
	limit = frappe.db.get_value("Automation", automation, "max_emails_per_day") or 0
	if limit and _counter(f"emails:{automation}:{_day()}", 86400) > limit:
		raise GuardError(_("This automation reached its limit of {0} emails per day.").format(limit))
	site_limit = settings().site_max_emails_per_day or 0
	if site_limit and _counter(f"emails:site:{_day()}", 86400) > site_limit:
		raise GuardError(
			_("Automations on this site reached the limit of {0} emails per day.").format(site_limit)
		)


def record_result(automation: str, status: str, error: str | None = None) -> bool:
	"""Track consecutive failures; pause the automation when they reach the site limit.

	Returns True when this result paused the automation (the owner was told)."""
	values = {"last_run_at": now_datetime(), "last_run_status": status}
	if status != "Failed":
		values["consecutive_failures"] = 0
		frappe.db.set_value("Automation", automation, values, update_modified=False)
		return False
	failures = (frappe.db.get_value("Automation", automation, "consecutive_failures") or 0) + 1
	values["consecutive_failures"] = failures
	limit = settings().max_failures_before_pause or 0
	pause = (
		limit and failures >= limit and frappe.db.get_value("Automation", automation, "status") == "Active"
	)
	if pause:
		values["status"] = "Paused"
		values["paused_reason"] = _(
			"Paused automatically after {0} failed runs in a row. Last error: {1}"
		).format(failures, (error or "")[:500])
	frappe.db.set_value("Automation", automation, values, update_modified=False)
	if pause:
		from pridict.automation import triggers

		triggers.clear_index()
		notify_owner(automation, values["paused_reason"])
	return bool(pause)


def notify_owner(automation: str, message: str):
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	owner = frappe.db.get_value("Automation", automation, "owner")
	# Frappe matches recipients by email address (Administrator's name is not its email).
	email = owner and owner != "Guest" and frappe.db.get_value("User", owner, "email")
	if not email:
		return
	enqueue_create_notification(
		[email],
		{
			"type": "Alert",
			"subject": message[:140],
			"email_content": message,
			"document_type": "Automation",
			"document_name": automation,
			# Sent by the automation user (Frappe drops notifications people send themselves).
			"from_user": settings().default_run_as or "Administrator",
		},
	)
