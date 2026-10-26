"""Approval decisions for agent proposals.

An Agent Approval lists the roles that must approve (one distinct person per role).
decide() records each person's decision; the first rejection, or the approval that
covers the last role, closes the approval and resumes the paused run. All checks run
here on the server: the approver's role, self-approval, and duplicate decisions.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from pridict.agent_studio import runtime


def required_roles(approval) -> list[str]:
	try:
		roles = json.loads(approval.required_roles or "[]")
	except ValueError:
		roles = []
	return roles or ["Purchase Manager"]


def coverage(approval) -> dict[str, str]:
	"""Role -> approver, for approvals recorded so far."""
	return {row.approver_role: row.approver for row in approval.decisions if row.decision == "Approved"}


def role_for(approval, user: str) -> str | None:
	"""First still-uncovered required role this user holds, or None."""
	covered = coverage(approval)
	held = set(frappe.get_roles(user))
	return next((role for role in required_roles(approval) if role not in covered and role in held), None)


def blockers(approval, user: str) -> list[str]:
	"""Reasons this user may not decide on the approval right now (empty = may decide)."""
	reasons = []
	if approval.status != "Pending":
		reasons.append(_("This approval is already {0}.").format(_(approval.status).lower()))
		return reasons
	run = frappe.db.get_value("Agent Run", approval.run, ["requested_by", "status", "agent"], as_dict=True)
	if run.status != "Awaiting approval":
		reasons.append(_("The run is not waiting for approval (status: {0}).").format(_(run.status)))
	if run.requested_by == user and runtime.load_policies(run.agent).get("no_self_approval"):
		reasons.append(_("You started this run, so you cannot approve it."))
	if any(row.approver == user for row in approval.decisions):
		reasons.append(_("You have already recorded a decision."))
	if not role_for(approval, user):
		missing = [r for r in required_roles(approval) if r not in coverage(approval)]
		reasons.append(
			_("This needs approval from: {0}. You do not hold a role that is still needed.").format(
				", ".join(missing)
			)
		)
	return reasons


def _notify(users, subject: str, approval: str):
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	users = [u for u in dict.fromkeys(users) if u and u not in ("Guest", frappe.session.user)]
	if users:
		enqueue_create_notification(
			users,
			{
				"type": "Alert",
				"subject": subject,
				"document_type": "Agent Approval",
				"document_name": approval,
				"from_user": frappe.session.user,
			},
		)


def notify_approvers(approval) -> None:
	"""Tell holders of the required roles that a proposal is waiting (called when it is created)."""
	if frappe.flags.agent_eval:
		return
	users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", required_roles(approval)], "parenttype": "User"},
		pluck="parent",
		limit=50,
	)
	enabled = set(
		frappe.get_all(
			"User",
			filters={"name": ["in", users or [""]], "enabled": 1, "user_type": "System User"},
			pluck="name",
		)
	)
	requester = frappe.db.get_value("Agent Run", approval.run, "requested_by")
	_notify(
		[u for u in users if u in enabled and u not in ("Administrator", requester)],
		_("Agent proposal {0} needs your approval: {1}").format(
			approval.name, approval.summary or approval.action
		),
		approval.name,
	)


def _automation_approver(approval: str) -> bool:
	"""Automation approvals can name any role; holders of a required role may decide them."""
	action, roles = frappe.db.get_value("Agent Approval", approval, ["action", "required_roles"]) or (
		None,
		None,
	)
	if not (action or "").startswith("automation:"):
		return False
	try:
		required = set(json.loads(roles or "[]"))
	except ValueError:
		return False
	return bool(required & set(frappe.get_roles()))


@frappe.whitelist(methods=["POST"])
def decide(approval: str, decision: str, note: str = "") -> dict:
	"""Record the current user's decision ("approve" or "reject") on an Agent Approval."""
	if decision not in ("approve", "reject"):
		frappe.throw(_("Decision must be approve or reject."))
	note = (note or "").strip()[:1000]
	if decision == "reject" and not note:
		frappe.throw(_("Please say why you are rejecting, so the agent can be improved."))
	if not frappe.has_permission("Agent Approval", "write", approval) and not _automation_approver(approval):
		frappe.throw(_("You are not allowed to decide on agent proposals."), frappe.PermissionError)

	# Lock the row so two approvers deciding at once cannot both close it.
	frappe.db.get_value("Agent Approval", approval, "status", for_update=True)
	doc = frappe.get_doc("Agent Approval", approval)
	user = frappe.session.user
	problems = blockers(doc, user)
	if problems:
		frappe.throw(" ".join(problems), frappe.PermissionError)

	role = role_for(doc, user)
	doc.append(
		"decisions",
		{
			"approver": user,
			"approver_role": role,
			"decision": "Approved" if decision == "approve" else "Rejected",
			"decided_at": now_datetime(),
			"note": note,
		},
	)
	remaining = [r for r in required_roles(doc) if r not in coverage(doc)]
	if decision == "reject" or not remaining:
		doc.status = "Approved" if decision == "approve" else "Rejected"
		doc.decided_by = user
		doc.decided_at = now_datetime()
		doc.decision_note = note
	doc.save(ignore_permissions=True)

	run, requester = frappe.db.get_value("Agent Run", doc.run, ["name", "requested_by"])
	if doc.status in ("Approved", "Rejected"):
		runtime.resume_run(
			run,
			{
				"decision": "approved" if doc.status == "Approved" else "rejected",
				"by": user,
				"note": note,
				"approval": doc.name,
			},
		)
		_notify(
			[requester],
			_("Your agent run {0} was {1} by {2}").format(run, _(doc.status).lower(), user),
			doc.name,
		)
	else:
		runtime.post_message(
			run,
			"assistant",
			_("{0} approved. Still waiting for: {1}.").format(
				frappe.utils.get_fullname(user), ", ".join(_(r) for r in remaining)
			),
			"notice",
		)
		runtime._publish(run, "Awaiting approval")
		_notify(
			[requester],
			_("{0} approved {1}; still waiting for: {2}").format(user, doc.name, ", ".join(remaining)),
			doc.name,
		)
	return {"status": doc.status, "remaining": remaining}
