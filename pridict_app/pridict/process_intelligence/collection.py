from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Protocol

from pridict.schema_intelligence.normalization import canonical_json, normalize_value

from pridict.process_intelligence.schema_adapter import PurchasingSchemaView


CONFIGURATION_FORMAT_VERSION = "1.0.0"


class ConfigurationSource(Protocol):
	def get_records(
		self,
		doctype: str,
		*,
		filters: dict[str, Any] | None = None,
		fields: tuple[str, ...] = (),
		order_by: str = "name asc",
	) -> list[dict[str, Any]]: ...

	def has_doctype(self, doctype: str) -> bool: ...


class FrappeConfigurationSource:
	def get_records(
		self,
		doctype: str,
		*,
		filters: dict[str, Any] | None = None,
		fields: tuple[str, ...] = (),
		order_by: str = "name asc",
	) -> list[dict[str, Any]]:
		import frappe

		if not frappe.db.table_exists(doctype):
			return []
		available = {field.fieldname for field in frappe.get_meta(doctype).fields} | {
			"name",
			"owner",
			"creation",
			"modified",
			"modified_by",
			"docstatus",
			"idx",
			"parent",
			"parentfield",
			"parenttype",
		}
		selected = [field for field in fields if field in available] or ["name"]
		return [
			dict(row)
			for row in frappe.get_all(
				doctype,
				filters=filters or {},
				fields=selected,
				order_by=order_by,
				ignore_permissions=True,
			)
		]

	def has_doctype(self, doctype: str) -> bool:
		import frappe

		return bool(frappe.db.table_exists(doctype))


def _now() -> str:
	return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _script_digest(value: Any) -> str | None:
	if value is None or not str(value):
		return None
	return hashlib.sha256(str(value).encode()).hexdigest()


def collect_purchasing_configuration(
	schema: PurchasingSchemaView,
	source: ConfigurationSource,
	*,
	collected_at: str | None = None,
) -> dict[str, Any]:
	doctypes = list(schema.doctype_names)
	collected = collected_at or _now()
	workflows = source.get_records(
		"Workflow",
		filters={"document_type": ["in", doctypes]},
		fields=("name", "document_type", "workflow_name", "is_active", "workflow_state_field", "send_email_alert"),
	)
	workflow_names = [item["name"] for item in workflows]
	states = source.get_records(
		"Workflow Document State",
		filters={"parent": ["in", workflow_names]},
		fields=(
			"name",
			"parent",
			"state",
			"doc_status",
			"allow_edit",
			"is_optional_state",
			"avoid_status_override",
		),
		order_by="parent asc, idx asc, name asc",
	) if workflow_names else []
	transitions = source.get_records(
		"Workflow Transition",
		filters={"parent": ["in", workflow_names]},
		fields=("name", "parent", "state", "action", "next_state", "allowed", "condition", "allow_self_approval"),
		order_by="parent asc, idx asc, name asc",
	) if workflow_names else []
	assignment_rules = source.get_records(
		"Assignment Rule",
		filters={"document_type": ["in", doctypes]},
		fields=("name", "document_type", "status", "priority", "rule", "condition"),
	)
	notifications = source.get_records(
		"Notification",
		filters={"document_type": ["in", doctypes]},
		fields=("name", "document_type", "enabled", "event", "channel", "condition", "subject"),
	)
	client_scripts = source.get_records(
		"Client Script",
		filters={"dt": ["in", doctypes]},
		fields=("name", "dt", "view", "enabled", "script"),
	)
	server_scripts = source.get_records(
		"Server Script",
		filters={"reference_doctype": ["in", doctypes]},
		fields=("name", "reference_doctype", "script_type", "doctype_event", "disabled", "script"),
	) if source.has_doctype("Server Script") else []
	for item in (*client_scripts, *server_scripts):
		item["script_hash"] = _script_digest(item.pop("script", None))
	payload = normalize_value(
		{
			"configuration_format_version": CONFIGURATION_FORMAT_VERSION,
			"schema_snapshot_id": schema.snapshot_id,
			"schema_metadata_hash": schema.metadata_hash,
			"collected_at": collected,
			"workflows": workflows,
			"workflow_states": states,
			"workflow_transitions": transitions,
			"assignment_rules": assignment_rules,
			"notifications": notifications,
			"client_scripts": client_scripts,
			"server_scripts": server_scripts,
		}
	)
	hash_payload = dict(payload)
	hash_payload.pop("collected_at", None)
	hash_payload.pop("schema_snapshot_id", None)
	payload["configuration_hash"] = hashlib.sha256(canonical_json(hash_payload).encode()).hexdigest()
	return payload
