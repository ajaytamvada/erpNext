from __future__ import annotations

import hashlib
from typing import Any

from pridict.schema_intelligence.models import DocTypeSchema, FieldSchema, PermissionSchema, SchemaSnapshot
from pridict.schema_intelligence.normalization import canonical_json

SEVERITY_ORDER = {"information": 0, "warning": 1, "critical": 2}
CRITICAL_PERMISSION_ACTIONS = {"create", "read", "write", "submit", "cancel"}


def classify_changes(before: SchemaSnapshot, after: SchemaSnapshot) -> dict[str, Any]:
	findings: list[dict[str, Any]] = []
	before_doctypes = {item.name: item for item in before.doctypes}
	after_doctypes = {item.name: item for item in after.doctypes}

	for name in sorted(before_doctypes.keys() - after_doctypes.keys()):
		findings.append(_finding("doctype.removed", "critical", "doctype", name, before_doctypes[name].to_dict(), None))
	for name in sorted(after_doctypes.keys() - before_doctypes.keys()):
		findings.append(_finding("doctype.added", "information", "doctype", name, None, after_doctypes[name].to_dict()))
	for name in sorted(before_doctypes.keys() & after_doctypes.keys()):
		findings.extend(_classify_doctype(before_doctypes[name], after_doctypes[name]))

	findings.sort(key=lambda item: (-SEVERITY_ORDER[item["severity"]], item["path"], item["rule_id"]))
	comparison = {
		"before_snapshot_id": before.snapshot_id,
		"after_snapshot_id": after.snapshot_id,
		"before_metadata_hash": before.metadata_hash,
		"after_metadata_hash": after.metadata_hash,
		"equivalent": before.metadata_hash == after.metadata_hash,
		"severity_totals": {
			severity: sum(item["severity"] == severity for item in findings)
			for severity in ("critical", "warning", "information")
		},
		"findings": findings,
	}
	comparison["comparison_hash"] = hashlib.sha256(canonical_json(comparison).encode()).hexdigest()
	return comparison


def _classify_doctype(before: DocTypeSchema, after: DocTypeSchema) -> list[dict[str, Any]]:
	findings: list[dict[str, Any]] = []
	before_fields = {item.fieldname: item for item in before.fields}
	after_fields = {item.fieldname: item for item in after.fields}
	for fieldname in sorted(before_fields.keys() - after_fields.keys()):
		findings.append(_field_finding("field.removed", "critical", before.name, fieldname, before_fields[fieldname], None))
	for fieldname in sorted(after_fields.keys() - before_fields.keys()):
		field = after_fields[fieldname]
		severity = "warning" if field.required else "information"
		rule = "field.required_added" if field.required else "field.optional_added"
		findings.append(_field_finding(rule, severity, after.name, fieldname, None, field))
	for fieldname in sorted(before_fields.keys() & after_fields.keys()):
		findings.extend(_classify_field(before_fields[fieldname], after_fields[fieldname]))

	if [item.fieldname for item in before.fields] != [item.fieldname for item in after.fields]:
		findings.append(
			_finding(
				"field.order_changed",
				"warning",
				"field",
				f"{before.name}.__field_order__",
				[item.fieldname for item in before.fields],
				[item.fieldname for item in after.fields],
				doctype=before.name,
			)
		)

	findings.extend(_classify_permissions(before, after))
	if canonical_json(before.properties) != canonical_json(after.properties):
		findings.append(
			_finding(
				"doctype.properties_changed",
				"information",
				"doctype",
				before.name,
				before.properties,
				after.properties,
				doctype=before.name,
				provenance=[item.to_dict() for item in after.provenance],
			)
		)
	return findings


def _classify_field(before: FieldSchema, after: FieldSchema) -> list[dict[str, Any]]:
	findings: list[dict[str, Any]] = []
	if before.fieldtype != after.fieldtype:
		findings.append(_field_finding("field.type_changed", "critical", before.doctype, before.fieldname, before.fieldtype, after.fieldtype, after))
	if canonical_json(before.options) != canonical_json(after.options):
		if before.fieldtype in {"Table", "Table MultiSelect"} or after.fieldtype in {"Table", "Table MultiSelect"}:
			rule, severity = "field.child_target_changed", "critical"
		elif before.fieldtype == "Link" or after.fieldtype == "Link":
			rule, severity = "field.link_target_changed", "warning"
		elif before.fieldtype == "Dynamic Link" or after.fieldtype == "Dynamic Link":
			rule, severity = "field.dynamic_selector_changed", "warning"
		else:
			rule, severity = "field.options_changed", "information"
		findings.append(_field_finding(rule, severity, before.doctype, before.fieldname, before.options, after.options, after))
	if not before.required and after.required:
		findings.append(_field_finding("field.became_required", "warning", before.doctype, before.fieldname, before.required, after.required, after))
	if before.label != after.label:
		findings.append(_field_finding("field.label_changed", "information", before.doctype, before.fieldname, before.label, after.label, after))
	before_description = before.properties.get("description")
	after_description = after.properties.get("description")
	if before_description != after_description:
		findings.append(_field_finding("field.description_changed", "information", before.doctype, before.fieldname, before_description, after_description, after))
	return findings


def _classify_permissions(before: DocTypeSchema, after: DocTypeSchema) -> list[dict[str, Any]]:
	findings: list[dict[str, Any]] = []
	before_permissions = {_permission_key(item): item for item in before.permissions}
	after_permissions = {_permission_key(item): item for item in after.permissions}
	for key in sorted(before_permissions.keys() - after_permissions.keys()):
		item = before_permissions[key]
		severity = "critical" if _has_critical_permission(item) else "information"
		findings.append(_permission_finding("permission.removed", severity, before.name, key, item, None))
	for key in sorted(after_permissions.keys() - before_permissions.keys()):
		findings.append(_permission_finding("permission.added", "warning", after.name, key, None, after_permissions[key]))
	for key in sorted(before_permissions.keys() & after_permissions.keys()):
		old = before_permissions[key]
		new = after_permissions[key]
		removed_actions = [action for action in CRITICAL_PERMISSION_ACTIONS if old.permissions.get(action) and not new.permissions.get(action)]
		added_actions = [action for action in CRITICAL_PERMISSION_ACTIONS if not old.permissions.get(action) and new.permissions.get(action)]
		if removed_actions:
			findings.append(_permission_finding("permission.capability_removed", "critical", before.name, key, old, new))
		elif added_actions:
			findings.append(_permission_finding("permission.capability_added", "warning", before.name, key, old, new))
		elif canonical_json(old.to_dict()) != canonical_json(new.to_dict()):
			findings.append(_permission_finding("permission.changed", "information", before.name, key, old, new))
	return findings


def _permission_key(permission: PermissionSchema) -> str:
	return f"{permission.role}:{permission.permlevel}:{int(bool(permission.if_owner))}"


def _has_critical_permission(permission: PermissionSchema) -> bool:
	return any(permission.permissions.get(action) for action in CRITICAL_PERMISSION_ACTIONS)


def _field_finding(rule_id, severity, doctype, fieldname, before, after, source: FieldSchema | None = None):
	if isinstance(before, FieldSchema):
		source = before
		before = before.to_dict()
	if isinstance(after, FieldSchema):
		source = after
		after = after.to_dict()
	return _finding(
		rule_id,
		severity,
		"field",
		f"{doctype}.{fieldname}",
		before,
		after,
		doctype=doctype,
		fieldname=fieldname,
		provenance=[item.to_dict() for item in source.provenance] if source else [],
	)


def _permission_finding(rule_id, severity, doctype, key, before, after):
	source = after or before
	return _finding(
		rule_id,
		severity,
		"permission",
		f"{doctype}.permissions.{key}",
		before.to_dict() if before else None,
		after.to_dict() if after else None,
		doctype=doctype,
		provenance=[item.to_dict() for item in source.provenance],
	)


def _finding(rule_id, severity, category, path, before, after, *, doctype=None, fieldname=None, provenance=None):
	payload = {
		"rule_id": rule_id,
		"severity": severity,
		"category": category,
		"path": path,
		"doctype": doctype,
		"fieldname": fieldname,
		"before": before,
		"after": after,
		"explanation": f"Deterministic rule {rule_id} detected a schema change at {path}.",
		"provenance": provenance or [],
	}
	payload["finding_id"] = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
	return payload
