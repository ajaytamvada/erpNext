"""Trigger node types. They start runs (see automation/triggers.py) and never execute."""

from __future__ import annotations

from pridict.automation import expressions
from pridict.automation.nodes import NodeType, register

DOCUMENT_EVENTS = ("after_insert", "on_update", "on_submit", "on_cancel", "on_trash", "on_change")


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
