"""Procurement Assistant: the buyer-facing chat over Agent Studio runs.

One conversation is one Agent Run. The buyer only sees its Agent Chat Message rows;
steps, tools and policies stay in Agent Studio for administrators. Sending a message
starts a new run, or answers the run's pending question.
"""

from __future__ import annotations

import json

import frappe
from frappe import _

from pridict.agent_studio import registry, runtime

ASSISTANT_AGENT = registry.PROCUREMENT_AGENT
SUGGESTIONS = [
	"I need 2 laptops by next Friday",
	"Source 500 kg of aluminium sheet for Stores by the end of the month",
	"Do we need to buy more office chairs?",
]


def _loads(value):
	try:
		return json.loads(value) if value else None
	except ValueError:
		return None


def _can_use() -> bool:
	return bool(runtime.STARTER_ROLES & set(frappe.get_roles()))


def _availability() -> tuple[bool, str]:
	if not _can_use():
		return False, _("You need a purchasing role to use the Procurement Assistant.")
	status = frappe.db.get_value("Agent Definition", ASSISTANT_AGENT, "status")
	if not status or status in ("Disabled", "Planned"):
		return False, _("The Procurement Assistant is switched off. Please contact your administrator.")
	if status != "Active" and "System Manager" not in frappe.get_roles():
		return False, _("The Procurement Assistant is not live yet. Please contact your administrator.")
	return True, ""


def _get_run(name: str):
	run = frappe.get_doc("Agent Run", name)
	if run.requested_by != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("This conversation belongs to someone else."), frappe.PermissionError)
	return run


@frappe.whitelist()
def get_assistant() -> dict:
	available, reason = _availability()
	status = frappe.db.get_value("Agent Definition", ASSISTANT_AGENT, "status")
	return {
		"available": available,
		"reason": reason,
		"test_mode": available and status != "Active",
		"suggestions": [_(s) for s in SUGGESTIONS],
		"conversations": get_conversations() if _can_use() else [],
	}


@frappe.whitelist()
def get_conversations(limit: int = 40) -> list[dict]:
	return frappe.get_all(
		"Agent Run",
		filters={"requested_by": frappe.session.user, "agent": ASSISTANT_AGENT},
		fields=["name", "request_summary as title", "status", "creation"],
		order_by="creation desc",
		limit=min(int(limit or 40), 100),
	)


@frappe.whitelist()
def get_conversation(name: str) -> dict:
	run = _get_run(name)
	messages = frappe.get_all(
		"Agent Chat Message",
		filters={"parent": run.name, "parenttype": "Agent Run"},
		fields=["role", "kind", "content", "card_json", "choices_json", "posted_at"],
		order_by="idx asc",
	)
	waiting = run.status == "Waiting for buyer"
	return {
		"name": run.name,
		"title": run.request_summary,
		"status": run.status,
		"working": run.status in ("Queued", "Running"),
		"can_reply": waiting,
		"can_cancel": run.status not in runtime.FINISHED and run.status != "Running",
		"messages": [
			{
				"role": m.role,
				"kind": m.kind,
				"content": m.content,
				"card": _loads(m.card_json),
				# Quick replies belong to the question still waiting for an answer.
				"choices": (_loads(m.choices_json) or []) if waiting and i == len(messages) - 1 else [],
				"at": m.posted_at,
			}
			for i, m in enumerate(messages)
		],
	}


@frappe.whitelist(methods=["POST"])
def send_message(text: str, conversation: str | None = None) -> dict:
	text = (text or "").strip()
	if not text:
		frappe.throw(_("Type a message first."))
	if conversation:
		run = _get_run(conversation)
		if run.status == "Waiting for buyer":
			runtime.answer_run(run.name, text)
			return {"conversation": run.name}
		if run.status in ("Queued", "Running"):
			frappe.throw(_("I'm still working on your last message. One moment please."))
		if run.status == "Awaiting approval":
			frappe.throw(
				_("This request is waiting for approval. Start a new conversation for something else.")
			)
	available, reason = _availability()
	if not available:
		frappe.throw(reason)
	return {"conversation": runtime.start_run(ASSISTANT_AGENT, text)["run"]}


@frappe.whitelist(methods=["POST"])
def cancel_conversation(conversation: str) -> dict:
	runtime.cancel_run(_get_run(conversation).name)
	return {"conversation": conversation}
