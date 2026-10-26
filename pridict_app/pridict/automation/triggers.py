"""Start automation runs from ERPNext events, schedules and manual clicks.

hooks.py sends every document event here. A cached index of active automations keyed by
(doctype, event) keeps non-matching saves to one dictionary lookup. Matching automations
get a Queued Agent Run inside the same transaction and a job enqueued after commit, so a
save that rolls back never starts a run. The scheduler calls dispatch_schedules() every
minute.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_to_date, get_datetime, now_datetime

from pridict.automation import engine, expressions, guards
from pridict.automation import spec as specs

INDEX_CACHE_KEY = "pridict_automation_trigger_index"

# Internal DocTypes whose saves never trigger automations (runs write to most of them).
IGNORED_DOCTYPES = frozenset(
	{
		"Automation",
		"Automation Version",
		"Automation Change",
		"Automation Settings",
		"Agent Run",
		"Agent Run Step",
		"Agent Chat Message",
		"Agent Checkpoint",
		"Agent Checkpoint Blob",
		"Agent Checkpoint Write",
		"Error Log",
		"Scheduled Job Log",
		"Version",
		"Access Log",
		"Activity Log",
		"Route History",
		"Email Queue",
		"Email Queue Recipient",
		"Notification Log",
	}
)


def _build_index() -> dict[str, list[dict]]:
	"""(doctype::event) -> [{name, config}] for active automations, from their active versions.

	Carrying the trigger config here keeps a matching save free of database reads. The index
	lives in Redis and is cleared whenever an automation is activated, paused or changed; if it
	is ever stale, the engine still refuses to run an automation that is not active.
	"""
	index: dict[str, list[dict]] = {}
	for row in frappe.get_all(
		"Automation",
		filters={
			"status": "Active",
			"trigger_type": ["in", ["trigger.document_event", "trigger.inbound_email"]],
		},
		fields=["name", "trigger_doctype", "trigger_event", "active_version"],
		order_by="name",
	):
		spec = specs.load(frappe.db.get_value("Automation Version", row.active_version, "spec") or "{}")
		config = (spec.get("trigger") or {}).get("config") or {}
		index.setdefault(f"{row.trigger_doctype}::{row.trigger_event}", []).append(
			{"name": row.name, "config": config}
		)
	return index


def get_index() -> dict[str, list[dict]]:
	return frappe.cache().get_value(INDEX_CACHE_KEY, generator=_build_index)


def clear_index():
	frappe.cache().delete_value(INDEX_CACHE_KEY)


# ---------------------------------------------------------------------------
# Document events


def on_doc_event(doc, method: str):
	if doc.doctype in IGNORED_DOCTYPES:
		return
	flags = frappe.flags
	if flags.in_install or flags.in_migrate or flags.in_patch or flags.in_import or flags.in_uninstall:
		return
	if flags.automation_test_run:
		# Documents a test run creates are rolled back; they must not start real runs.
		return
	index = get_index()
	candidates = [(entry, method) for entry in index.get(f"{doc.doctype}::{method}") or []]
	if doc.doctype == "Communication" and method == "after_insert":
		candidates += [(entry, "inbound_email") for entry in index.get("Communication::inbound_email") or []]
	if not candidates or not guards.enabled():
		return
	chain = list(flags.automation_chain or [])
	scope = {}  # the document as condition data, built once per save and only if needed
	for entry, event in candidates:
		name = entry["name"]
		# A run never re-triggers its own automation, and chains of automations stay short.
		if name in chain or len(chain) >= guards.max_chain_depth():
			continue
		if not _matches(name, entry["config"], doc, event, scope):
			continue
		if not guards.allow_run(name):
			continue
		engine.start_run(name, {"event": event, "doctype": doc.doctype, "name": doc.name}, chain=chain)


def _matches(automation: str, config: dict, doc, event: str, scope: dict) -> bool:
	if event == "inbound_email":
		from pridict.automation.nodes.triggers import InboundEmail

		return InboundEmail.matches(config, doc)
	condition = config.get("condition")
	if not condition:
		return True
	if "doc" not in scope:
		scope["doc"] = expressions.attr_dicts(expressions.to_data(doc.as_dict()))
	try:
		return bool(expressions.evaluate(condition, scope))
	except Exception:
		frappe.log_error(title=f"Automation {automation}: trigger condition failed")
		return False


# ---------------------------------------------------------------------------
# Schedules


def dispatch_schedules():
	"""Scheduler entry (every minute): start every schedule automation that is due."""
	if not guards.enabled():
		return
	resume_due()
	now = now_datetime()
	for row in frappe.get_all(
		"Automation",
		filters={"status": "Active", "trigger_type": "trigger.schedule", "trigger_cron": ["is", "set"]},
		fields=["name", "trigger_cron", "last_fired_at", "modified"],
	):
		if is_due(row.trigger_cron, row.last_fired_at or row.modified, now):
			_fire_schedule(row.name, now)


def resume_due():
	"""Resume runs whose wait is over, and expire approvals nobody decided in time."""
	due = frappe.get_all(
		"Agent Run",
		filters={
			"automation": ["is", "set"],
			"is_test": 0,
			"status": ["in", ["Waiting", "Awaiting approval"]],
			"resume_at": ["<=", now_datetime()],
		},
		fields=["name", "status"],
	)
	for run in due:
		try:
			if run.status == "Awaiting approval":
				for approval in frappe.get_all(
					"Agent Approval", filters={"run": run.name, "status": "Pending"}, pluck="name"
				):
					frappe.db.set_value(
						"Agent Approval",
						approval,
						{"status": "Expired", "decision_note": _("No decision in time")},
					)
				engine.resume(run.name, {"decision": "expired"})
			else:
				engine.resume(run.name, {"waited": True})
		except Exception:
			frappe.log_error(title=f"Automation run {run.name}: resume failed")
	if due:
		frappe.db.commit()


def is_due(cron: str, since, now) -> bool:
	"""True if the cron schedule has a fire time in (since, now]."""
	from croniter import croniter

	since = get_datetime(since)
	# Never catch up more than a day of missed runs after downtime; fire once instead.
	since = max(since, add_to_date(now, days=-1))
	return croniter(cron, since).get_next(type(now)) <= now


def _fire_schedule(automation: str, now):
	# Record the slot before starting, so a failed start is not retried every minute.
	frappe.db.set_value("Automation", automation, "last_fired_at", now, update_modified=False)
	try:
		if guards.allow_run(automation):
			engine.start_run(automation, {"event": "schedule", "fired_at": str(now)})
	except Exception:
		frappe.log_error(title=f"Automation {automation}: scheduled start failed")
	frappe.db.commit()


# ---------------------------------------------------------------------------
# Manual runs


@frappe.whitelist(methods=["POST"])
def run_now(automation: str, doctype: str | None = None, name: str | None = None, input=None) -> dict:  # noqa: A002
	"""Start an active automation by hand, optionally on one document."""
	doc = frappe.get_doc("Automation", automation)
	doc.check_permission("write")
	if not guards.enabled():
		frappe.throw(_("Automations are switched off on this site."))
	if doc.status != "Active":
		frappe.throw(_("Activate the automation before running it."))
	if doctype or name:
		if not (doctype and name):
			frappe.throw(_("Choose both the DocType and the document."))
		frappe.get_doc(doctype, name).check_permission("read")
	trigger = {"event": "manual", "doctype": doctype, "name": name, "input": frappe.parse_json(input)}
	run = engine.start_run(automation, trigger, requested_by=frappe.session.user)
	return {"run": run}


# ---------------------------------------------------------------------------
# Webhooks

WEBHOOK_MAX_BYTES = 1_000_000
SIGNATURE_HEADER = "X-Pridict-Signature"


def webhook_url(key: str) -> str:
	return frappe.utils.get_url(f"/api/method/pridict.automation.triggers.webhook?key={key}")


def sign(secret: str, body: bytes) -> str:
	import hashlib
	import hmac

	return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="key", limit=120, seconds=60, ip_based=False)
def webhook(key: str) -> dict:
	"""Start a webhook automation. The body must be signed: X-Pridict-Signature: sha256=<hmac>."""
	import hmac

	from frappe.utils.password import get_decrypted_password

	body = frappe.request.get_data(cache=True) or b""
	if len(body) > WEBHOOK_MAX_BYTES:
		frappe.throw(_("The body is larger than 1 MB."), frappe.ValidationError)
	automation = (
		frappe.db.get_value(
			"Automation",
			{"webhook_key": key, "trigger_type": "trigger.webhook"},
			["name", "status"],
			as_dict=True,
		)
		if key
		else None
	)
	# Unknown keys and bad signatures get the same answer, so keys cannot be probed.
	refused = _("Unknown webhook or bad signature.")
	if not automation:
		frappe.throw(refused, frappe.PermissionError)
	secret = get_decrypted_password("Automation", automation.name, "webhook_secret", raise_exception=False)
	given = frappe.request.headers.get(SIGNATURE_HEADER) or ""
	if not secret or not hmac.compare_digest(given, sign(secret, body)):
		frappe.throw(refused, frappe.PermissionError)
	if automation.status != "Active" or not guards.enabled():
		frappe.throw(_("This automation is not active."), frappe.ValidationError)
	try:
		payload = frappe.parse_json(body.decode("utf-8")) if body else {}
	except Exception:
		frappe.throw(_("The body must be JSON."))
	headers = {
		name: value
		for name, value in frappe.request.headers.items()
		if name.lower() in ("content-type", "user-agent")
		or (name.lower().startswith("x-") and name != SIGNATURE_HEADER)
	}
	if not guards.allow_run(automation.name):
		frappe.throw(_("Too many runs this hour."), frappe.ValidationError)
	run = engine.start_run(
		automation.name, {"event": "webhook", "input": {"body": payload, "headers": headers}}
	)
	return {"run": run}


def ensure_webhook_secret(doc, rotate: bool = False) -> str | None:
	"""Give a webhook automation its key and secret (new ones when rotating). Returns a new secret."""
	if doc.trigger_type != "trigger.webhook":
		return None
	if doc.webhook_key and doc.get_password("webhook_secret", raise_exception=False) and not rotate:
		return None
	secret = frappe.generate_hash(length=40)
	doc.webhook_key = doc.webhook_key if (doc.webhook_key and not rotate) else frappe.generate_hash(length=32)
	doc.webhook_secret = secret
	return secret
