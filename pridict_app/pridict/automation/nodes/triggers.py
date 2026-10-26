"""Trigger node types. They start runs (see automation/triggers.py) and never execute."""

from __future__ import annotations

from pridict.automation import expressions
from pridict.automation.nodes import Issue, NodeType, meta, register

DOCUMENT_EVENTS = ("after_insert", "on_update", "on_submit", "on_cancel", "on_trash", "on_change")
FREQUENCIES = ("hourly", "daily", "weekly", "monthly")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


@register
class DocumentEvent(NodeType):
	type = "trigger.document_event"
	label = "Document event"
	category = "trigger"
	icon = "⚡"
	description = (
		"Starts when a document of a chosen type is created, saved, submitted, cancelled or deleted."
	)
	outputs = ("trigger.doc", "trigger.event")
	config_schema = {
		"type": "object",
		"required": ["doctype", "event"],
		"properties": {
			"doctype": {"type": "string", "title": "DocType", "format": "doctype"},
			"event": {"type": "string", "title": "Event", "enum": list(DOCUMENT_EVENTS)},
			"condition": {"type": "string", "title": "Only when", "format": "condition"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config)
		if config.get("event") and config["event"] not in DOCUMENT_EVENTS:
			messages.append(f"Unknown event {config['event']!r}.")
		if config.get("condition"):
			problem = expressions.check_condition(config["condition"])
			if problem:
				messages.append(problem)
		return messages

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		doctype = config.get("doctype")
		issues = meta.doctype_issues(doctype, run_as, "read")
		if not issues and config.get("event") in ("on_submit", "on_cancel") and not meta.submittable(doctype):
			issues.append(
				Issue("error", f"{doctype} is not submittable, so it is never submitted or cancelled.")
			)
		return issues


def to_cron(config: dict) -> str:
	"""Cron expression for a schedule config: an explicit cron or a friendly frequency."""
	if config.get("cron"):
		return str(config["cron"]).strip()
	frequency = config.get("frequency")
	hour, minute = (int(part) for part in str(config.get("time") or "09:00").split(":")[:2])
	if frequency == "hourly":
		return f"{minute} * * * *"
	if frequency == "daily":
		return f"{minute} {hour} * * *"
	if frequency == "weekly":
		weekday = WEEKDAYS.index(str(config.get("weekday") or "monday").lower())
		return f"{minute} {hour} * * {(weekday + 1) % 7}"
	if frequency == "monthly":
		return f"{minute} {hour} {int(config.get('day') or 1)} * *"
	raise ValueError(f"Unknown frequency {frequency!r}.")


@register
class Schedule(NodeType):
	type = "trigger.schedule"
	label = "Schedule"
	category = "trigger"
	icon = "⏰"
	description = "Starts on a schedule (every day at 09:00, every Monday…) in the site's time zone."
	outputs = ("trigger.fired_at",)
	config_schema = {
		"type": "object",
		"properties": {
			"frequency": {"type": "string", "title": "Every", "enum": list(FREQUENCIES)},
			"time": {"type": "string", "title": "At (HH:MM)"},
			"weekday": {"type": "string", "title": "Weekday", "enum": [d.title() for d in WEEKDAYS]},
			"day": {"type": "integer", "title": "Day of month", "minimum": 1, "maximum": 28},
			"cron": {"type": "string", "title": "Cron expression (advanced)"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		from croniter import croniter

		if not config.get("cron") and not config.get("frequency"):
			return ["Choose how often it runs, or give a cron expression."]
		if config.get("frequency") and config["frequency"] not in FREQUENCIES:
			return [f"frequency must be one of {', '.join(FREQUENCIES)}."]
		if config.get("weekday") and str(config["weekday"]).lower() not in WEEKDAYS:
			return [f"Unknown weekday {config['weekday']!r}."]
		try:
			cron = to_cron(config)
		except (ValueError, TypeError):
			return ["time must look like 09:00."]
		if not croniter.is_valid(cron):
			return [f"Invalid schedule {cron!r}."]
		if cron.split()[0] in ("*", "*/1"):
			return ["Schedules need a fixed minute; running every minute is not allowed."]
		return []


@register
class Manual(NodeType):
	type = "trigger.manual"
	label = "Manual"
	category = "trigger"
	icon = "▶"
	description = "Starts when someone clicks Run, optionally on a chosen document."
	outputs = ("trigger.input", "trigger.doc")
	config_schema = {
		"type": "object",
		"properties": {"doctype": {"type": "string", "title": "Runs on DocType", "format": "doctype"}},
	}

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		return meta.doctype_issues(config.get("doctype"), run_as, "read")
