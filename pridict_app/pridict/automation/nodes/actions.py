"""Action node types: change data or tell people. They run as the automation's Run As user."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import validate_email_address

from pridict.automation import expressions
from pridict.automation.nodes import NodeResult, NodeType, register

MAX_RECIPIENTS = 50
MAX_ASSIGNEES = 20


def _split(value) -> list[str]:
	if isinstance(value, list | tuple):
		items = value
	else:
		items = str(value or "").replace(";", ",").split(",")
	return list(dict.fromkeys(item.strip() for item in items if item and str(item).strip()))


def _check_templates(config: dict, keys: tuple[str, ...]) -> list[str]:
	messages = []
	for key in keys:
		problem = expressions.check_template(config.get(key))
		if problem:
			messages.append(f"{key}: {problem}")
	return messages


def _target(config: dict, scope: dict) -> tuple[str, str]:
	"""Document a node acts on: configured, or the trigger document by default."""
	doctype = expressions.render(config.get("doctype"), scope) or scope["trigger"].get("doctype")
	name = expressions.render(config.get("name"), scope) or scope["trigger"].get("name")
	if not doctype or not name:
		raise ValueError(_("No document to act on: set DocType and name."))
	return doctype, name


@register
class SendEmail(NodeType):
	type = "action.send_email"
	label = "Send email"
	category = "action"
	icon = "✉"
	description = "Sends an email, linked to the trigger document's timeline."
	outputs = ("recipients", "subject")
	config_schema = {
		"type": "object",
		"required": ["to", "subject", "message"],
		"properties": {
			"to": {"type": "string", "title": "To", "format": "template"},
			"cc": {"type": "string", "title": "CC", "format": "template"},
			"subject": {"type": "string", "title": "Subject", "format": "template"},
			"message": {"type": "string", "title": "Message", "format": "template"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		return super().check_config(config) + _check_templates(config, ("to", "cc", "subject", "message"))

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		recipients = _split(expressions.render(config["to"], scope))
		cc = _split(expressions.render(config.get("cc"), scope))
		if not recipients:
			raise ValueError(_("The email has no recipient."))
		if len(recipients) + len(cc) > MAX_RECIPIENTS:
			raise ValueError(_("The email has more than {0} recipients.").format(MAX_RECIPIENTS))
		for address in recipients + cc:
			validate_email_address(address, throw=True)
		subject = expressions.render(config["subject"], scope)
		message = expressions.render(config["message"], scope)
		output = {"recipients": recipients, "cc": cc, "subject": subject}
		if scope["run"].get("is_test"):
			# Test runs show what would be sent instead of sending it.
			return NodeResult(
				output={**output, "message": message, "sent": False},
				summary=_("Would email {0}: {1}").format(", ".join(recipients), subject),
			)
		trigger = scope["trigger"]
		frappe.sendmail(
			recipients=recipients,
			cc=cc,
			subject=subject,
			message=message,
			reference_doctype=trigger.get("doctype"),
			reference_name=trigger.get("name"),
		)
		return NodeResult(
			output={**output, "sent": True},
			summary=_("Emailed {0}: {1}").format(", ".join(recipients), subject),
		)


def users_with_role(role: str) -> list[str]:
	holders = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	holders = [user for user in holders if user not in ("Administrator", "Guest")]
	if not holders:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", holders], "enabled": 1, "user_type": "System User"},
		pluck="name",
		order_by="name",
	)


@register
class Assign(NodeType):
	type = "action.assign"
	label = "Assign"
	category = "action"
	icon = "☑"
	description = "Assigns a document to users, or to everyone with a role, as a ToDo."
	outputs = ("assigned_to",)
	config_schema = {
		"type": "object",
		"required": ["description"],
		"properties": {
			"doctype": {"type": "string", "title": "DocType", "format": "template"},
			"name": {"type": "string", "title": "Document", "format": "template"},
			"users": {"type": "string", "title": "Users", "format": "template"},
			"role": {"type": "string", "title": "Role", "format": "role"},
			"description": {"type": "string", "title": "What to do", "format": "template"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config)
		if not config.get("users") and not config.get("role"):
			messages.append("Choose users or a role to assign to.")
		return messages + _check_templates(config, ("doctype", "name", "users", "description"))

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		from frappe.desk.form.assign_to import add

		doctype, name = _target(config, scope)
		users = _split(expressions.render(config.get("users"), scope))
		if config.get("role"):
			users += users_with_role(config["role"])
		users = list(dict.fromkeys(users))
		if not users:
			raise ValueError(
				_("Nobody to assign to: no enabled user has role {0}.").format(config.get("role"))
			)
		if len(users) > MAX_ASSIGNEES:
			raise ValueError(_("Refusing to assign to more than {0} users.").format(MAX_ASSIGNEES))
		description = expressions.render(config["description"], scope)
		add({"assign_to": users, "doctype": doctype, "name": name, "description": description})
		return NodeResult(
			output={"assigned_to": users, "doctype": doctype, "name": name},
			summary=_("Assigned {0} {1} to {2}").format(doctype, name, ", ".join(users)),
		)
