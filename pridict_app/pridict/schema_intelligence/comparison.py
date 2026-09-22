from __future__ import annotations

from typing import Any

from pridict.schema_intelligence.models import DocTypeSchema, SchemaSnapshot
from pridict.schema_intelligence.normalization import canonical_json
from pridict.schema_intelligence.snapshots import _without_source_names


def compare_snapshots(before: SchemaSnapshot, after: SchemaSnapshot) -> dict[str, Any]:
	before_doctypes = {item.name: item for item in before.doctypes}
	after_doctypes = {item.name: item for item in after.doctypes}
	common_doctypes = sorted(before_doctypes.keys() & after_doctypes.keys())

	return {
		"before_snapshot_id": before.snapshot_id,
		"after_snapshot_id": after.snapshot_id,
		"before_metadata_hash": before.metadata_hash,
		"after_metadata_hash": after.metadata_hash,
		"equivalent": before.metadata_hash == after.metadata_hash,
		"added_doctypes": sorted(after_doctypes.keys() - before_doctypes.keys()),
		"removed_doctypes": sorted(before_doctypes.keys() - after_doctypes.keys()),
		"changed_doctypes": [
			name
			for name in common_doctypes
			if _doctype_properties(before_doctypes[name]) != _doctype_properties(after_doctypes[name])
		],
		"field_order_changed": [
			name
			for name in common_doctypes
			if [field.fieldname for field in before_doctypes[name].fields]
			!= [field.fieldname for field in after_doctypes[name].fields]
		],
		"fields": _compare_nested(
			before_doctypes,
			after_doctypes,
			lambda item: {field.fieldname: _field_value(field.to_dict()) for field in item.fields},
		),
		"permissions": _compare_nested(
			before_doctypes,
			after_doctypes,
			lambda item: {
				_permission_key(permission): _without_source_names(permission.to_dict())
				for permission in item.permissions
			},
		),
		"relationships": _compare_flat(
			{item.relationship_id: _without_source_names(item.to_dict()) for item in before.relationships},
			{item.relationship_id: _without_source_names(item.to_dict()) for item in after.relationships},
		),
	}


def _doctype_properties(doctype: DocTypeSchema) -> str:
	return canonical_json(
		{
			"module": doctype.module,
			"flags": doctype.flags,
			"properties": doctype.properties,
			"provenance": [_without_source_names(item.to_dict()) for item in doctype.provenance],
		}
	)


def _permission_key(permission) -> str:
	return f"{permission.role}:{permission.permlevel}:{int(bool(permission.if_owner))}"


def _field_value(value: dict[str, Any]) -> dict[str, Any]:
	value = _without_source_names(value)
	value.pop("idx", None)
	return value


def _compare_nested(before_doctypes, after_doctypes, item_map):
	result: dict[str, dict[str, list[str]]] = {}
	for doctype_name in sorted(before_doctypes.keys() & after_doctypes.keys()):
		before_items = item_map(before_doctypes[doctype_name])
		after_items = item_map(after_doctypes[doctype_name])
		changes = _compare_flat(before_items, after_items)
		if any(changes.values()):
			result[doctype_name] = changes
	return result


def _compare_flat(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[str]]:
	common = before.keys() & after.keys()
	return {
		"added": sorted(after.keys() - before.keys()),
		"removed": sorted(before.keys() - after.keys()),
		"changed": sorted(key for key in common if canonical_json(before[key]) != canonical_json(after[key])),
	}
