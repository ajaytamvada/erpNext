"""Whitelisted read endpoints for the Agent Studio Desk pages."""

from __future__ import annotations

import json
from collections import Counter

import frappe
from frappe import _
from frappe.utils import add_days, now_datetime

from pridict.agent_studio import registry
from pridict.agent_studio.graph import validate_workflow


def _loads(value, default=None):
	if not value:
		return default
	try:
		return json.loads(value)
	except ValueError:
		return default


def _require(doctype: str):
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not permitted to read {0}").format(_(doctype)), frappe.PermissionError)


@frappe.whitelist()
def get_models():
	_require("LLM Model Config")
	configs = frappe.get_list(
		"LLM Model Config",
		fields=[
			"name",
			"provider",
			"model_id",
			"status",
			"temperature",
			"max_tokens",
			"timeout_s",
			"retries",
			"fallback",
			"description",
		],
		order_by="config_name asc",
	)
	used_by = Counter(
		r.model_config for r in frappe.get_all("Agent Definition", fields=["model_config"]) if r.model_config
	)
	per_provider = Counter(c.provider for c in configs)
	for config in configs:
		config.used_by = used_by.get(config.name, 0)

	providers = []
	if frappe.has_permission("LLM Provider", "read"):
		for row in frappe.get_list(
			"LLM Provider",
			fields=[
				"name",
				"provider_type",
				"endpoint",
				"api_version",
				"enabled",
				"status",
				"last_tested_at",
				"last_latency_ms",
				"last_error",
			],
			order_by="provider_name asc",
		):
			# Never send the key itself; only whether one is stored.
			row.key_set = bool(
				frappe.utils.password.get_decrypted_password(
					"LLM Provider", row.name, "api_key", raise_exception=False
				)
			)
			row.models = per_provider.get(row.name, 0)
			providers.append(row)
	return {"providers": providers, "modelConfigs": configs}


def _agent_history(name: str) -> list[dict]:
	history = []
	for version in frappe.get_all(
		"Version",
		filters={"ref_doctype": "Agent Definition", "docname": name},
		fields=["owner", "creation", "data"],
		order_by="creation desc",
		limit=10,
	):
		data = _loads(version.data, {})
		changed = {row[0]: row[2] for row in data.get("changed", [])}
		note = changed.get("change_note") or (
			_("Changed: {0}").format(", ".join(sorted(changed))) if changed else ""
		)
		if data.get("row_changed") or data.get("added") or data.get("removed"):
			note = (note + "; " if note else "") + _("tools updated")
		history.append(
			{
				"version": changed.get("version", ""),
				"date": str(version.creation)[:16],
				"author": version.owner,
				"note": note,
			}
		)
	return history


@frappe.whitelist()
def get_agents():
	_require("Agent Definition")
	agents = []
	for name in frappe.get_list("Agent Definition", pluck="name", order_by="agent_name asc"):
		doc = frappe.get_doc("Agent Definition", name)
		agents.append(
			{
				"name": doc.name,
				"module": doc.agent_module,
				"type": doc.agent_type,
				"status": doc.status,
				"version": doc.version,
				"owner": doc.owner_user,
				"model_config": doc.model_config,
				"workflow_key": doc.workflow_key,
				"mode": doc.mode,
				"max_steps": doc.max_steps,
				"max_runtime_s": doc.max_runtime_s,
				"token_budget": doc.token_budget,
				"approval_required": doc.approval_required,
				"tools": [row.tool for row in doc.tools],
				"instructions": doc.instructions,
				"output_schema": _loads(doc.output_schema, {}),
				"history": _agent_history(doc.name),
			}
		)
	models = get_models()["modelConfigs"]
	return {"agents": agents, "modelConfigs": models, "tools": get_tools()["tools"]}


@frappe.whitelist()
def get_tools():
	_require("Agent Tool")
	tools = frappe.get_list(
		"Agent Tool",
		fields=[
			"name",
			"access",
			"status",
			"target",
			"scope",
			"timeout_s",
			"python_method",
			"description",
			"input_schema",
			"output_schema",
		],
		order_by="access asc, tool_name asc",
	)
	calls, errors = Counter(), Counter()
	if frappe.has_permission("Agent Run", "read"):
		since = add_days(now_datetime(), -7)
		for step in frappe.get_all(
			"Agent Run Step",
			filters={"parenttype": "Agent Run", "creation": [">=", since], "tool_calls": ["is", "set"]},
			fields=["tool_calls", "status"],
		):
			for tool in filter(None, (t.strip() for t in step.tool_calls.split(","))):
				calls[tool] += 1
				errors[tool] += step.status == "Failed"
	for tool in tools:
		tool.input = _loads(tool.pop("input_schema"), {})
		tool.output = _loads(tool.pop("output_schema"), {})
		tool.calls_7d = calls.get(tool.name, 0)
		tool.errors_7d = errors.get(tool.name, 0)
		tool.error_pct = round(100 * tool.errors_7d / tool.calls_7d, 1) if tool.calls_7d else 0
	return {"tools": tools}


@frappe.whitelist()
def get_workflow(workflow_key: str = registry.PROCUREMENT_WORKFLOW):
	_require("Agent Definition")
	workflow = registry.WORKFLOWS.get(workflow_key)
	if not workflow:
		frappe.throw(_("Unknown workflow {0}").format(workflow_key))
	agents = frappe.get_all(
		"Agent Definition",
		filters={"workflow_key": workflow_key},
		fields=["name", "status", "version", "max_steps"],
	)
	tool_access = dict(frappe.get_all("Agent Tool", fields=["name", "access"], as_list=True))
	max_steps = min((a.max_steps for a in agents if a.max_steps), default=None)
	return {
		"workflow": {**workflow, "key": workflow_key},
		"agents": agents,
		"validation": validate_workflow(workflow, tool_access, max_steps),
	}


@frappe.whitelist()
def get_policies():
	_require("Agent Policy")
	rows = frappe.get_list(
		"Agent Policy",
		fields=[
			"name",
			"policy_group",
			"severity",
			"enabled",
			"agent",
			"rule_key",
			"description",
			"parameters",
		],
		order_by="sort_order asc, policy_name asc",
	)
	order = ["Suppliers", "Scope", "Data requirements", "Money & quantity limits", "Prohibited for agents"]
	groups = {group: [] for group in order}
	for row in rows:
		row.parameters = _loads(row.parameters, {})
		groups.setdefault(row.policy_group, []).append(row)
	latest = None
	if frappe.has_permission("Agent Approval", "read"):
		latest = next(
			iter(
				frappe.get_list(
					"Agent Approval",
					filters={"policy_results_json": ["is", "set"]},
					fields=["name", "action", "estimated_value", "status", "summary", "policy_results_json"],
					order_by="creation desc",
					limit=1,
				)
			),
			None,
		)
		if latest:
			latest.results = _loads(latest.pop("policy_results_json"), [])
	return {
		"policies": [{"group": group, "rules": rules} for group, rules in groups.items() if rules],
		"latestCheck": latest,
	}


@frappe.whitelist()
def get_runs(limit: int = 50):
	_require("Agent Run")
	runs = frappe.get_list(
		"Agent Run",
		fields=[
			"name",
			"agent",
			"agent_version",
			"status",
			"requested_by",
			"started_at",
			"duration_s",
			"total_tokens",
			"outcome",
			"request_summary",
			"creation",
		],
		order_by="creation desc",
		limit=min(int(limit), 200),
	)
	return {"runs": runs}


@frappe.whitelist()
def get_run(name: str):
	doc = frappe.get_doc("Agent Run", name)
	doc.check_permission("read")
	return {
		"name": doc.name,
		"agent": doc.agent,
		"agent_version": doc.agent_version,
		"status": doc.status,
		"requested_by": doc.requested_by,
		"request": doc.request,
		"started_at": doc.started_at,
		"duration_s": doc.duration_s,
		"outcome": doc.outcome,
		"error": doc.error,
		"model_config": doc.model_config,
		"llm_calls": doc.llm_calls,
		"total_tokens": doc.total_tokens,
		"result": _loads(doc.result_json, {}),
		"steps": [
			{
				"node": s.node_id,
				"kind": s.node_kind,
				"status": s.status,
				"ms": s.duration_ms,
				"tokens": s.tokens,
				"tool_calls": s.tool_calls,
				"summary": s.summary,
			}
			for s in doc.steps
		],
		"approvals": frappe.get_all(
			"Agent Approval", filters={"run": doc.name}, fields=["name", "status"], order_by="creation asc"
		),
	}


@frappe.whitelist()
def get_approvals(limit: int = 50):
	_require("Agent Approval")
	approvals = frappe.get_list(
		"Agent Approval",
		fields=[
			"name",
			"run",
			"agent",
			"requested_by",
			"status",
			"action",
			"estimated_value",
			"risk",
			"creation",
		],
		order_by="creation desc",
		limit=min(int(limit), 200),
	)
	approvals.sort(key=lambda a: a.status != "Pending")  # stable: pending first, newest first within each
	return {"approvals": approvals}


@frappe.whitelist()
def get_approval(name: str):
	doc = frappe.get_doc("Agent Approval", name)
	doc.check_permission("read")
	return {
		**{
			f: doc.get(f)
			for f in (
				"name",
				"run",
				"agent",
				"requested_by",
				"status",
				"action",
				"estimated_value",
				"risk",
				"required_approvals",
				"summary",
				"decided_by",
				"decided_at",
				"decision_note",
				"created_doctype",
				"created_docname",
				"creation",
			)
		},
		"proposal": _loads(doc.proposal_json, {}),
		"policy_results": _loads(doc.policy_results_json, []),
	}
