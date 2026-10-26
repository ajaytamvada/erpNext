"""Steps that wait: for an approval, for an answer, or for time to pass.

In a live run they pause with a LangGraph interrupt: the engine saves the checkpoint, records
what the run is waiting for (and creates the Agent Approval or the notifications), and the
run resumes later with the person's decision. A paused step runs again from the top on
resume, so the steps themselves have no side effects before the pause.

In a test run nothing waits: the step uses the decision the admin simulated for it, or
stops the test (SimulationNeeded) so the builder can offer Simulate buttons.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

from pridict.automation import expressions
from pridict.automation.nodes import Issue, NodeResult, NodeType, register
from pridict.automation.nodes.actions import _check_templates, _people, _role_issues, users_with_role

MAX_WAIT_DAYS = 90


class SimulationNeeded(Exception):
	"""A test run reached a waiting step that has no simulated decision yet."""

	def __init__(self, pause: dict):
		super().__init__(pause.get("message") or pause.get("question") or pause["type"])
		self.pause = pause


def pause(scope: dict, payload: dict):
	"""Wait for a person or for time (live), or use the simulated decision (test)."""
	node_id = scope["node"]["id"]
	payload = {**payload, "node": node_id}
	run = scope["run"]
	if run.get("is_test"):
		decisions = run.get("decisions") or {}
		if node_id not in decisions:
			raise SimulationNeeded(payload)
		return decisions[node_id]
	from langgraph.types import interrupt

	return interrupt(payload)


@register
class Approval(NodeType):
	type = "human.approval"
	label = "Approval"
	category = "human"
	icon = "✋"
	description = (
		"Asks everyone with a role to approve or reject (in the Agent Approvals inbox), then follows "
		"'approved', 'rejected', or 'expired' if nobody decides in time."
	)
	branches = ("approved", "rejected", "expired")
	outputs = ("decision", "decided_by", "note")
	config_schema = {
		"type": "object",
		"required": ["role", "message"],
		"properties": {
			"role": {"type": "string", "title": "Approver role", "format": "role"},
			"message": {"type": "string", "title": "What to approve", "format": "template"},
			"timeout_hours": {
				"type": "integer",
				"title": "Expire after (hours)",
				"minimum": 1,
				"maximum": 24 * MAX_WAIT_DAYS,
			},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		return super().check_config(config) + _check_templates(config, ("message",))

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		issues = _role_issues(config.get("role"))
		if not issues and config.get("role") and not users_with_role(config["role"]):
			issues.append(Issue("warning", f"No enabled user has role {config['role']} to approve.", "setup"))
		return issues

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		message = expressions.render(config["message"], scope)
		value = pause(
			scope,
			{
				"type": "approval",
				"roles": [config["role"]],
				"message": message,
				"timeout_hours": config.get("timeout_hours"),
				"choices": list(self.branches),
			},
		)
		if isinstance(value, str):
			value = {"decision": value}
		decision = (value or {}).get("decision") or "rejected"
		if decision not in self.branches:
			decision = "rejected"
		output = {"decision": decision, "decided_by": value.get("by"), "note": value.get("note") or ""}
		who = f" by {output['decided_by']}" if output["decided_by"] else ""
		return NodeResult(output=output, route=decision, summary=_("{0}{1}").format(decision.title(), who))


@register
class Ask(NodeType):
	type = "human.ask"
	label = "Ask"
	category = "human"
	icon = "❓"
	description = (
		"Asks users (or everyone with a role) a question and waits for the answer (nodes.<id>.answer)."
	)
	outputs = ("answer", "answered_by")
	config_schema = {
		"type": "object",
		"required": ["question"],
		"properties": {
			"users": {"type": "string", "title": "Users", "format": "template"},
			"role": {"type": "string", "title": "Role", "format": "role"},
			"question": {"type": "string", "title": "Question", "format": "template"},
			"choices": {"type": "array", "title": "Answer choices", "items": {"type": "string"}},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config)
		if not config.get("users") and not config.get("role"):
			messages.append("Choose users or a role to ask.")
		return messages + _check_templates(config, ("users", "question"))

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		return _role_issues(config.get("role"))

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		users = [] if scope["run"].get("is_test") else _people(config, scope)
		if not scope["run"].get("is_test") and not users:
			raise ValueError(_("Nobody to ask."))
		question = expressions.render(config["question"], scope)
		value = pause(
			scope,
			{
				"type": "ask",
				"question": question,
				"message": question,
				"users": users,
				"choices": config.get("choices") or [],
			},
		)
		if isinstance(value, str):
			value = {"answer": value}
		answer = str((value or {}).get("answer") or "")
		return NodeResult(
			output={"answer": answer, "answered_by": (value or {}).get("by")},
			summary=_("Answer: {0}").format(answer[:120]),
		)


@register
class Wait(NodeType):
	type = "logic.wait"
	label = "Wait"
	category = "logic"
	icon = "⏳"
	description = "Pauses the run for a while (minutes, hours, days) or until a date and time."
	outputs = ("waited_until",)
	config_schema = {
		"type": "object",
		"properties": {
			"minutes": {"type": "integer", "title": "Minutes", "minimum": 0},
			"hours": {"type": "integer", "title": "Hours", "minimum": 0},
			"days": {"type": "integer", "title": "Days", "minimum": 0, "maximum": MAX_WAIT_DAYS},
			"until": {"type": "string", "title": "Until (date and time)", "format": "template"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		duration = any(config.get(key) for key in ("minutes", "hours", "days"))
		if duration == bool(config.get("until")):
			return ["Give either a duration (minutes, hours, days) or an 'until' date, not both."]
		return _check_templates(config, ("until",))

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		if config.get("until"):
			until = get_datetime(expressions.resolve(config["until"], scope))
		else:
			until = add_to_date(
				now_datetime(),
				minutes=int(config.get("minutes") or 0),
				hours=int(config.get("hours") or 0),
				days=int(config.get("days") or 0),
			)
		if until > add_to_date(now_datetime(), days=MAX_WAIT_DAYS):
			raise ValueError(_("Waits are limited to {0} days.").format(MAX_WAIT_DAYS))
		if until > now_datetime():
			pause(
				scope,
				{
					"type": "wait",
					"resume_at": str(until),
					"message": _("Waiting until {0}").format(until),
					"choices": ["skip"],
				},
			)
		return NodeResult(output={"waited_until": str(until)}, summary=_("Waited until {0}").format(until))


def approvers(roles: list[str]) -> list[str]:
	users = set()
	for role in roles:
		users.update(users_with_role(role))
	return sorted(users)


def can_answer(pending: dict, user: str) -> bool:
	"""May this user answer an Ask the run is waiting on?"""
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True
	return user in (pending.get("users") or [])
