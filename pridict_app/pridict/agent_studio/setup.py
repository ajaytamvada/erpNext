"""Sync code-defined Agent Studio defaults into the database (runs after install/migrate)."""

from __future__ import annotations

import json

import frappe

from pridict.agent_studio import registry

# Tool fields owned by code; overwritten on every sync. Status is admin-owned except
# for tools that code marks "Blocked for agents".
CODE_OWNED_TOOL_FIELDS = ("access", "target", "scope", "timeout_s", "description")


def ensure_agent_studio_setup():
	if not frappe.db.table_exists("Agent Tool"):
		return
	sync_tools()
	seed_policies()
	seed_procurement_agent()


def _dump(value) -> str:
	return json.dumps(value, indent=2, ensure_ascii=False)


def sync_tools():
	for spec in registry.TOOLS:
		values = {field: spec[field] for field in CODE_OWNED_TOOL_FIELDS}
		values["input_schema"] = _dump(spec["input_schema"])
		values["output_schema"] = _dump(spec["output_schema"])
		values["python_method"] = f"pridict.agent_studio.tools.{spec['tool_name']}"

		if not frappe.db.exists("Agent Tool", spec["tool_name"]):
			frappe.get_doc(
				{"doctype": "Agent Tool", "tool_name": spec["tool_name"], "status": spec["status"], **values}
			).insert(ignore_permissions=True)
			continue

		doc = frappe.get_doc("Agent Tool", spec["tool_name"])
		# Force the block on, and lift it only when code no longer blocks the tool.
		if "Blocked for agents" in (spec["status"], doc.status):
			values["status"] = spec["status"]
		if any(doc.get(field) != value for field, value in values.items()):
			doc.update(values)
			doc.save(ignore_permissions=True)


def seed_policies():
	for order, spec in enumerate(registry.POLICIES, start=1):
		if frappe.db.exists("Agent Policy", spec["policy_name"]):
			continue
		doc = frappe.get_doc({"doctype": "Agent Policy", "sort_order": order, **spec})
		doc.parameters = _dump(spec["parameters"]) if spec.get("parameters") else None
		doc.insert(ignore_permissions=True)


def seed_procurement_agent():
	if frappe.db.exists("Agent Definition", registry.PROCUREMENT_AGENT):
		return
	spec = dict(registry.PROCUREMENT_AGENT_DEFAULTS)
	tools = spec.pop("tools")
	doc = frappe.get_doc({"doctype": "Agent Definition", **spec})
	doc.output_schema = _dump(spec["output_schema"])
	doc.owner_user = "Administrator"
	for tool in tools:
		doc.append("tools", {"tool": tool})
	doc.insert(ignore_permissions=True)
