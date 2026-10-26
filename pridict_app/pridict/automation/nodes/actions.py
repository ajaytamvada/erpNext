"""Action node types: change data or tell people. They run as the automation's Run As user,
without ignore_permissions, so every write is checked like a person's would be."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import validate_email_address

from pridict.automation import expressions
from pridict.automation.nodes import Issue, NodeResult, NodeType, meta, register

MAX_RECIPIENTS = 50
MAX_ASSIGNEES = 20
MAX_NOTIFY = 50


def _split(value) -> list[str]:
	if isinstance(value, list | tuple):
		items = value
	else:
		items = str(value or "").replace(";", ",").split(",")
	return list(dict.fromkeys(str(item).strip() for item in items if item and str(item).strip()))


def _check_templates(config: dict, keys: tuple[str, ...]) -> list[str]:
	messages = []
	for key in keys:
		for problem in expressions.check_templates(config.get(key)):
			messages.append(f"{key}: {problem}")
	return messages


def _target(config: dict, scope: dict) -> tuple[str, str]:
	"""Document a node acts on: configured, or the trigger document by default."""
	doctype = expressions.resolve(config.get("doctype"), scope) or scope["trigger"].get("doctype")
	name = expressions.resolve(config.get("name"), scope) or scope["trigger"].get("name")
	if not doctype or not name:
		raise ValueError(_("No document to act on: set DocType and name."))
	return doctype, str(name)


def _role_issues(role) -> list[Issue]:
	if role and not meta.is_expression(role) and not frappe.db.exists("Role", role):
		return [Issue("error", f"Role {role!r} does not exist.")]
	return []


def _attribute(doc, scope: dict, verb: str):
	"""Timeline note on documents an automation creates or changes."""
	run = scope["run"]
	doc.add_comment(
		"Info",
		_("{0} by automation {1} (run {2})").format(
			verb, run.get("title") or run.get("automation"), run.get("name")
		),
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


def _people(config: dict, scope: dict) -> list[str]:
	users = _split(expressions.resolve(config.get("users"), scope))
	if config.get("role"):
		users += users_with_role(config["role"])
	return list(dict.fromkeys(users))


# ---------------------------------------------------------------------------
# Documents


class _DocumentAction(NodeType):
	category = "action"

	def _values(self, config: dict, scope: dict) -> dict:
		values = expressions.resolve_all(config.get("values") or {}, scope)
		if not isinstance(values, dict):
			raise ValueError(_("Values must be a mapping of field names to values."))
		return values

	def _submit_issues(self, config: dict, run_as: str | None) -> list[Issue]:
		doctype = config.get("doctype")
		if not config.get("submit") or not doctype or meta.is_expression(doctype):
			return []
		if not frappe.db.exists("DocType", doctype):
			return []
		if not meta.submittable(doctype):
			return [Issue("error", f"{doctype} cannot be submitted.")]
		if run_as and not frappe.has_permission(doctype, "submit", user=run_as):
			return [Issue("error", f"Run As user {run_as} has no submit permission on {doctype}.")]
		return []


@register
class CreateDocument(_DocumentAction):
	type = "action.create_document"
	label = "Create document"
	icon = "➕"
	description = "Creates a document from field values; optionally submits it."
	outputs = ("doc",)
	config_schema = {
		"type": "object",
		"required": ["doctype", "values"],
		"properties": {
			"doctype": {"type": "string", "title": "DocType", "format": "doctype"},
			"values": {"type": "object", "title": "Values"},
			"submit": {"type": "boolean", "title": "Submit"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config) + _check_templates(config, ("values",))
		if config.get("doctype") and meta.is_expression(config["doctype"]):
			messages.append("The DocType must be a fixed name, not an expression.")
		return messages

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		doctype = config.get("doctype")
		values = config.get("values") if isinstance(config.get("values"), dict) else {}
		return (
			meta.doctype_issues(doctype, run_as, "create", for_create=True)
			+ meta.field_issues(doctype, list(values))
			+ self._submit_issues(config, run_as)
		)

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		doc = frappe.get_doc({**self._values(config, scope), "doctype": config["doctype"]})
		doc.insert()
		if config.get("submit"):
			doc.submit()
		_attribute(doc, scope, _("Created"))
		verb = _("Created and submitted") if config.get("submit") else _("Created")
		return NodeResult(output={"doc": doc.as_dict()}, summary=f"{verb} {doc.doctype} {doc.name}")


@register
class UpdateDocument(_DocumentAction):
	defaults_to_trigger_doc = True
	type = "action.update_document"
	label = "Update document"
	icon = "✎"
	description = "Sets fields on a document (the trigger document by default); optionally submits it."
	outputs = ("doc",)
	config_schema = {
		"type": "object",
		"required": ["values"],
		"properties": {
			"doctype": {"type": "string", "title": "DocType", "format": "doctype"},
			"name": {"type": "string", "title": "Document", "format": "template"},
			"values": {"type": "object", "title": "Values"},
			"submit": {"type": "boolean", "title": "Submit"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		return super().check_config(config) + _check_templates(config, ("name", "values"))

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		doctype = config.get("doctype")
		values = config.get("values") if isinstance(config.get("values"), dict) else {}
		return (
			meta.doctype_issues(doctype, run_as, "write")
			+ meta.field_issues(doctype, list(values))
			+ self._submit_issues(config, run_as)
		)

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		doctype, name = _target(config, scope)
		doc = frappe.get_doc(doctype, name)
		doc.update(self._values(config, scope))
		doc.save()
		if config.get("submit"):
			doc.submit()
		_attribute(doc, scope, _("Updated"))
		return NodeResult(output={"doc": doc.as_dict()}, summary=_("Updated {0} {1}").format(doctype, name))


@register
class SubmitDocument(_DocumentAction):
	defaults_to_trigger_doc = True
	type = "action.submit_document"
	label = "Submit document"
	icon = "✔"
	description = "Submits a draft document (the trigger document by default)."
	outputs = ("doc",)
	config_schema = {
		"type": "object",
		"properties": {
			"doctype": {"type": "string", "title": "DocType", "format": "doctype"},
			"name": {"type": "string", "title": "Document", "format": "template"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		return super().check_config(config) + _check_templates(config, ("name",))

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		return self._submit_issues({**config, "submit": True}, run_as)

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		doctype, name = _target(config, scope)
		doc = frappe.get_doc(doctype, name)
		if doc.docstatus != 0:
			raise ValueError(_("{0} {1} is not a draft.").format(doctype, name))
		doc.submit()
		_attribute(doc, scope, _("Submitted"))
		return NodeResult(output={"doc": doc.as_dict()}, summary=_("Submitted {0} {1}").format(doctype, name))


@register
class AddComment(NodeType):
	defaults_to_trigger_doc = True
	type = "action.add_comment"
	label = "Add comment"
	category = "action"
	icon = "💬"
	description = "Adds a comment to a document's timeline (the trigger document by default)."
	config_schema = {
		"type": "object",
		"required": ["comment"],
		"properties": {
			"doctype": {"type": "string", "title": "DocType", "format": "doctype"},
			"name": {"type": "string", "title": "Document", "format": "template"},
			"comment": {"type": "string", "title": "Comment", "format": "template"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		return super().check_config(config) + _check_templates(config, ("name", "comment"))

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		return meta.doctype_issues(config.get("doctype"), run_as, "read")

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		doctype, name = _target(config, scope)
		doc = frappe.get_doc(doctype, name)
		doc.check_permission("read")
		text = expressions.render(config["comment"], scope)
		comment = doc.add_comment("Comment", text)
		return NodeResult(
			output={"comment": comment.name}, summary=_("Commented on {0} {1}").format(doctype, name)
		)


# ---------------------------------------------------------------------------
# People


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
			"email_account": {"type": "string", "title": "Send from", "format": "email_account"},
			"attach_print": {"type": "string", "title": "Attach print format", "format": "print_format"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		return super().check_config(config) + _check_templates(config, ("to", "cc", "subject", "message"))

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		account = config.get("email_account")
		if account:
			row = frappe.db.get_value("Email Account", account, ["enable_outgoing"], as_dict=True)
			if not row:
				return [Issue("error", f"Email Account {account!r} does not exist.")]
			if not row.enable_outgoing:
				return [Issue("error", f"Email Account {account} cannot send email (outgoing is off).")]
		elif not frappe.db.exists("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}):
			return [Issue("error", "No default outgoing Email Account. Set one up or choose an account.")]
		print_format = config.get("attach_print")
		if print_format and not frappe.db.exists("Print Format", print_format) and print_format != "Standard":
			return [Issue("error", f"Print Format {print_format!r} does not exist.")]
		return []

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		from pridict.automation import guards

		recipients = _split(expressions.resolve(config["to"], scope))
		cc = _split(expressions.resolve(config.get("cc"), scope))
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
		guards.count_email(scope["run"]["automation"])
		trigger = scope["trigger"]
		kwargs = {}
		if config.get("email_account"):
			kwargs["sender"] = frappe.db.get_value("Email Account", config["email_account"], "email_id")
		if config.get("attach_print") and trigger.get("doctype") and trigger.get("name"):
			kwargs["attachments"] = [
				frappe.attach_print(
					trigger["doctype"],
					trigger["name"],
					print_format=config["attach_print"],
					file_name=trigger["name"],
				)
			]
		frappe.sendmail(
			recipients=recipients,
			cc=cc,
			subject=subject,
			message=message,
			reference_doctype=trigger.get("doctype"),
			reference_name=trigger.get("name"),
			**kwargs,
		)
		return NodeResult(
			output={**output, "sent": True},
			summary=_("Emailed {0}: {1}").format(", ".join(recipients), subject),
		)


@register
class Notify(NodeType):
	type = "action.notify"
	label = "Notify"
	category = "action"
	icon = "🔔"
	description = "Sends an in-app notification to users or to everyone with a role."
	config_schema = {
		"type": "object",
		"required": ["subject"],
		"properties": {
			"users": {"type": "string", "title": "Users", "format": "template"},
			"role": {"type": "string", "title": "Role", "format": "role"},
			"subject": {"type": "string", "title": "Subject", "format": "template"},
			"message": {"type": "string", "title": "Message", "format": "template"},
			"doctype": {"type": "string", "title": "Link to DocType", "format": "doctype"},
			"name": {"type": "string", "title": "Link to document", "format": "template"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config)
		if not config.get("users") and not config.get("role"):
			messages.append("Choose users or a role to notify.")
		return messages + _check_templates(config, ("users", "subject", "message", "name"))

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		return _role_issues(config.get("role"))

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

		users = _people(config, scope)
		if not users:
			raise ValueError(_("Nobody to notify."))
		if len(users) > MAX_NOTIFY:
			raise ValueError(_("Refusing to notify more than {0} users.").format(MAX_NOTIFY))
		doctype = expressions.resolve(config.get("doctype"), scope) or scope["trigger"].get("doctype")
		name = expressions.resolve(config.get("name"), scope) or scope["trigger"].get("name")
		subject = expressions.render(config["subject"], scope)
		# Frappe matches recipients by email address, which differs from the name for Administrator.
		emails = frappe.get_all("User", filters={"name": ["in", users], "enabled": 1}, pluck="email")
		if not emails:
			raise ValueError(_("None of these users exist or are enabled: {0}").format(", ".join(users)))
		enqueue_create_notification(
			emails,
			{
				"type": "Alert",
				"subject": subject,
				"email_content": expressions.render(config.get("message") or "", scope),
				"document_type": doctype,
				"document_name": name,
				"from_user": frappe.session.user,
			},
		)
		return NodeResult(
			output={"users": users}, summary=_("Notified {0}: {1}").format(", ".join(users), subject)
		)


@register
class Assign(NodeType):
	defaults_to_trigger_doc = True
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

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		return _role_issues(config.get("role")) + meta.doctype_issues(config.get("doctype"), run_as, "read")

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		from frappe.desk.form.assign_to import add

		doctype, name = _target(config, scope)
		users = _people(config, scope)
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
