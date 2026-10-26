"""Procurement Assistant: the buyer-facing chat API.

A conversation is an Assistant Conversation. The user only sees chat messages: the
conversation's own and those of the sourcing runs it started. Steps, tools and policies
stay in Agent Studio for administrators. Each message is answered by
conversation.respond() in a background job.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from pridict.agent_studio import conversation as chat
from pridict.agent_studio import registry, runtime

ASSISTANT_AGENT = registry.ASSISTANT_AGENT
SUGGESTIONS = [
	"Show my open purchase orders",
	"Which purchase orders are overdue?",
	"Who are our top suppliers this year?",
	"I need 2 laptops by next Friday",
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


def _get(name: str):
	doc = frappe.get_doc(chat.DOCTYPE, name)
	if doc.user != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("This conversation belongs to someone else."), frappe.PermissionError)
	return doc


def _state(doc, run_status: str | None) -> str:
	"""One word for the conversation list: what, if anything, is the user waiting on."""
	if doc.working or run_status in ("Queued", "Running"):
		return "working"
	if doc.pending_action_json or run_status == "Waiting for buyer":
		return "needs_reply"
	if run_status == "Awaiting approval":
		return "approval"
	return "open"


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
	rows = frappe.get_all(
		chat.DOCTYPE,
		# Automation Builder chats live with their automation, not in the assistant.
		filters={"user": frappe.session.user, "purpose": ["!=", "Automation Builder"]},
		fields=["name", "title", "working", "pending_action_json", "active_run", "last_activity"],
		order_by="last_activity desc",
		limit=min(int(limit or 40), 100),
	)
	runs = dict(
		frappe.get_all(
			"Agent Run",
			filters={"name": ["in", [r.active_run for r in rows if r.active_run] or [""]]},
			fields=["name", "status"],
			as_list=True,
		)
	)
	return [
		{
			"name": r.name,
			"title": r.title,
			"state": _state(r, runs.get(r.active_run)),
			"last_activity": r.last_activity,
		}
		for r in rows
	]


@frappe.whitelist()
def get_conversation(name: str) -> dict:
	doc = _get(name)
	run = (
		frappe.db.get_value("Agent Run", doc.active_run, ["name", "status"], as_dict=True)
		if doc.active_run
		else None
	)
	run_status = run.status if run else None
	messages = chat.merged_messages(doc.name)
	working = bool(doc.working) or run_status in ("Queued", "Running")
	last = messages[-1] if messages else None
	# Quick replies belong to the question still waiting for an answer.
	show_choices = bool(
		last
		and not working
		and last.role == "assistant"
		and (
			(last.parenttype == "Agent Run" and run_status == "Waiting for buyer")
			or (last.parenttype == chat.DOCTYPE and doc.pending_action_json)
		)
	)
	# A purchase request still waiting on the user, when its question is no longer the last message
	# (the user asked something else meanwhile): the page pins it above the message box.
	pinned = None
	if run_status == "Waiting for buyer" and not working and not show_choices:
		question = next(
			(m for m in reversed(messages) if m.parent == run.name and m.role == "assistant"), None
		)
		if question:
			pinned = {"text": question.content, "choices": _loads(question.choices_json) or []}
	return {
		"name": doc.name,
		"title": doc.title,
		"state": _state(doc, run_status),
		"pinned_question": pinned,
		"working": working,
		"run": run,
		"can_cancel_run": bool(run and run_status not in runtime.FINISHED and run_status != "Running"),
		"messages": [
			{
				"role": m.role,
				"kind": m.kind,
				"content": m.content,
				"card": _loads(m.card_json),
				"choices": (_loads(m.choices_json) or []) if show_choices and m is last else [],
				"at": m.posted_at,
			}
			for m in messages
		],
	}


@frappe.whitelist(methods=["POST"])
def send_message(text: str, conversation: str | None = None) -> dict:
	text = (text or "").strip()[:4000]
	if not text:
		frappe.throw(_("Type a message first."))
	available, reason = _availability()
	if not available:
		frappe.throw(reason)
	if conversation:
		doc = _get(conversation)
		if doc.working:
			frappe.throw(_("I'm still working on your last message. One moment please."))
	else:
		doc = frappe.get_doc(
			{
				"doctype": chat.DOCTYPE,
				"title": text if len(text) <= 80 else text[:77] + "...",
				"user": frappe.session.user,
				"agent": ASSISTANT_AGENT,
			}
		)
		doc.insert(ignore_permissions=True)
	chat.post(doc.name, text, role="user")
	frappe.db.set_value(
		chat.DOCTYPE, doc.name, {"working": 1, "last_activity": now_datetime()}, update_modified=False
	)
	chat.enqueue_respond(doc.name)
	return {"conversation": doc.name}


@frappe.whitelist(methods=["POST"])
def cancel_sourcing(conversation: str) -> dict:
	doc = _get(conversation)
	if not doc.active_run:
		frappe.throw(_("There is no open sourcing request."))
	runtime.cancel_run(doc.active_run)
	return {"conversation": conversation}
