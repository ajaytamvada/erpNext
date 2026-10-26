"""Live evaluation of the AI architect against the real model.

Each scenario is a prompt, canned answers for the architect's questions, and what a good
result contains. A run builds each automation in a draft, answering questions until the
architect stops asking (at most MAX_TURNS), scores the draft, and rolls everything back.

	bench --site <site> execute pridict.automation.evals.run
	bench --site <site> execute pridict.automation.evals.run --kwargs "{'keys': ['s1']}"
"""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import frappe

from pridict.automation import api, architect
from pridict.automation import spec as specs

MAX_TURNS = 5
MAX_QUESTIONS = 3
DEFAULT_ANSWER = "Use your best judgement and go ahead."

SCENARIOS = [
	{
		"key": "s1",
		"prompt": "When a purchase Material Request is submitted, check stock for its items; "
		"if anything is short, "
		"create and submit a Request for Quotation for the items' approved suppliers and email them.",
		"answers": ["Submit the RFQ.", "Use the default email account."],
		"expect": {
			"trigger": ("trigger.document_event", "Material Request"),
			"types": ["logic.if", "action.create_document", "action.send_email"],
			"doctypes": ["Request for Quotation"],
		},
	},
	{
		"key": "s2",
		"prompt": "Every day at 9, email customers whose sales invoice became 7 days overdue "
		"and notify their "
		"account manager.",
		"answers": [
			"Remind once, at 7 days.",
			"Use the default email account.",
			"The customer's account manager field.",
		],
		"expect": {
			"trigger": ("trigger.schedule", None),
			"types": ["data.find_documents", "logic.loop", "action.send_email", "action.notify"],
			"doctypes": ["Sales Invoice"],
		},
	},
	{
		"key": "s3",
		"prompt": "When a new Supplier is created, email them our onboarding checklist and assign a check to "
		"the purchase team.",
		"answers": [
			"Assign it to everyone with the Purchase Manager role.",
			"Use the default email account.",
		],
		"expect": {
			"trigger": ("trigger.document_event", "Supplier"),
			"types": ["action.send_email", "action.assign"],
			"doctypes": [],
		},
	},
	{
		"key": "po_comment",
		"prompt": "When a Purchase Order over 5 lakh is submitted, notify the Purchase Manager "
		"role and add a "
		"comment on the order saying it needs a second look.",
		"answers": ["5 lakh means grand total above 500000."],
		"expect": {
			"trigger": ("trigger.document_event", "Purchase Order"),
			"types": ["action.notify", "action.add_comment"],
			"doctypes": [],
		},
	},
	{
		"key": "weekly_digest",
		"prompt": "Every Monday at 9:00, email the purchase manager a list of purchase orders that are still "
		"waiting to be received more than 14 days after their schedule date.",
		"answers": ["Send it to everyone with the Purchase Manager role.", "Use the default email account."],
		"expect": {
			"trigger": ("trigger.schedule", None),
			"types": ["data.find_documents", "action.send_email"],
			"doctypes": ["Purchase Order"],
		},
	},
	{
		"key": "issue_assign",
		"prompt": "When a new Issue is created with priority High, assign it to the Support Team role and "
		"notify them.",
		"answers": ["Everyone with the Support Team role."],
		"expect": {
			"trigger": ("trigger.document_event", "Issue"),
			"types": ["action.assign"],
			"doctypes": [],
		},
	},
]


def _doctypes(spec: dict) -> set[str]:
	found = set()
	for node in [spec.get("trigger") or {}, *spec.get("nodes", [])]:
		config = node.get("config") or {}
		for key in ("doctype", "parent_doctype"):
			if isinstance(config.get(key), str) and not config[key].startswith("{"):
				found.add(config[key])
	return found


def score(spec: dict, run_as: str, questions: int, turns: int, expect: dict) -> dict:
	issues = specs.validate(spec, live=True, run_as=run_as)
	errors = [i["message"] for i in issues if i["level"] == "error"]
	design_errors = [i["message"] for i in issues if i["level"] == "error" and i.get("kind") != "setup"]
	trigger = spec.get("trigger") or {}
	trigger_type, trigger_doctype = expect["trigger"]
	types = {n.get("type") for n in spec.get("nodes", [])}
	checks = {
		"valid": not design_errors,
		"trigger": trigger.get("type") == trigger_type
		and (trigger_doctype is None or (trigger.get("config") or {}).get("doctype") == trigger_doctype),
		"steps": all(t in types for t in expect["types"]),
		"doctypes": all(d in _doctypes(spec) for d in expect["doctypes"]),
		"questions": questions <= MAX_QUESTIONS,
		"finished": turns <= MAX_TURNS,
	}
	return {
		"passed": all(checks.values()),
		"checks": checks,
		"errors": design_errors,
		"environment_errors": [e for e in errors if e not in design_errors],
		"step_types": sorted(t for t in types if t),
	}


def run_scenario(scenario: dict) -> dict:
	automation = api.create_automation(f"Eval {scenario['key']}", "trigger.manual")["name"]
	answers = list(scenario["answers"])
	message, questions, turns = scenario["prompt"], 0, 0
	started = time.monotonic()
	transcript = []
	while turns < MAX_TURNS:
		turns += 1
		transcript.append({"role": "user", "content": message})
		architect.send_message(automation, message)
		last = architect.get_chat(automation)["messages"][-1]
		transcript.append({"role": "assistant", "kind": last["kind"], "content": last["content"]})
		if last["kind"] == "error" or last["kind"] != "question":
			break
		questions += 1
		message = answers.pop(0) if answers else DEFAULT_ANSWER
	doc = frappe.get_doc("Automation", automation)
	conversation = frappe.get_doc("Assistant Conversation", doc.conversation)
	result = score(specs.load(doc.draft_spec), doc.run_as, questions, turns, scenario["expect"])
	result.update(
		{
			"key": scenario["key"],
			"questions": questions,
			"turns": turns,
			"llm_calls": conversation.llm_calls,
			"tokens": conversation.total_tokens,
			"seconds": round(time.monotonic() - started, 1),
			"transcript": transcript,
			"steps": [f"{s.node_id}: {s.summary}" for s in conversation.steps],
			"spec": architect.compact_spec(specs.load(doc.draft_spec)),
		}
	)
	return result


def run(keys: list[str] | None = None, save_to: str | None = None) -> dict:
	"""Run the live eval set and roll back everything it created. Returns the report."""
	chosen = [s for s in SCENARIOS if not keys or s["key"] in keys]
	results = []
	frappe.flags.agent_eval = True  # runtime._commit becomes a no-op
	frappe.flags.architect_inline = True  # each turn finishes before the next answer
	try:
		with patch.object(frappe.db, "commit"):
			# Client sites can send email; give the dev site an account for the run (rolled back).
			from pridict.automation.test_helpers import ensure_email_account

			for scenario in chosen:
				# in_test only around the insert: it skips the SMTP connection check.
				frappe.flags.in_test = True
				try:
					ensure_email_account()
				finally:
					frappe.flags.in_test = False
				try:
					results.append(run_scenario(scenario))
				except Exception as error:
					results.append({"key": scenario["key"], "passed": False, "crash": repr(error)})
				frappe.db.rollback()
	finally:
		frappe.flags.agent_eval = False
		frappe.flags.architect_inline = False
		frappe.db.rollback()
	report = {
		"model": frappe.db.get_single_value("Automation Settings", "architect_model"),
		"passed": sum(1 for r in results if r.get("passed")),
		"total": len(results),
		"tokens": sum(r.get("tokens") or 0 for r in results),
		"results": results,
	}
	if save_to:
		with open(save_to, "w", encoding="utf-8") as handle:
			json.dump(report, handle, indent=1, default=str, ensure_ascii=False)
	for r in results:
		print(
			f"{'PASS' if r.get('passed') else 'FAIL'} {r['key']}: "
			f"questions={r.get('questions')} turns={r.get('turns')} "
			f"tokens={r.get('tokens')} {r.get('checks') or r.get('crash')} {r.get('errors') or ''}"
		)
	print(f"{report['passed']}/{report['total']} passed, {report['tokens']} tokens")
	return report
