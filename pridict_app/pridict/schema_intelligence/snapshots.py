from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from pridict.schema_intelligence.models import (
	SCHEMA_FORMAT_VERSION,
	Diagnostic,
	DocTypeSchema,
	RelationshipSchema,
	SchemaSnapshot,
)
from pridict.schema_intelligence.normalization import canonical_json, normalize_value


VOLATILE_RAW_KEYS = frozenset(
	{
		"creation",
		"modified",
		"modified_by",
		"owner",
		"_last_update",
		"is_large_table",
	}
)


def hash_site_identifier(site: str) -> str:
	return hashlib.sha256(f"pridict-schema-site:{site}".encode()).hexdigest()


def _semantic_doctype(doctype: DocTypeSchema) -> dict[str, Any]:
	return _without_source_names(doctype.to_dict())


def semantic_payload(
	doctypes: tuple[DocTypeSchema, ...],
	relationships: tuple[RelationshipSchema, ...],
) -> dict[str, Any]:
	return {
		"schema_format_version": SCHEMA_FORMAT_VERSION,
		"doctypes": [_semantic_doctype(item) for item in doctypes],
		"relationships": [_without_source_names(item.to_dict()) for item in relationships],
	}


def _without_source_names(value: Any) -> Any:
	if isinstance(value, dict):
		return {
			key: _without_source_names(item)
			for key, item in value.items()
			if key != "source_name"
		}
	if isinstance(value, list):
		return [_without_source_names(item) for item in value]
	return value


def compute_metadata_hash(
	doctypes: tuple[DocTypeSchema, ...],
	relationships: tuple[RelationshipSchema, ...],
) -> str:
	payload = canonical_json(semantic_payload(doctypes, relationships)).encode("utf-8")
	return hashlib.sha256(payload).hexdigest()


def build_snapshot(
	*,
	frappe_version: str,
	erpnext_version: str | None,
	site: str,
	doctypes: list[DocTypeSchema],
	relationships: list[RelationshipSchema],
	raw_metadata: dict[str, Any],
	diagnostics: list[Diagnostic],
	captured_at: datetime | None = None,
	snapshot_id: str | None = None,
) -> SchemaSnapshot:
	sorted_doctypes = tuple(sorted(doctypes, key=lambda item: item.name))
	sorted_relationships = tuple(
		sorted(
			relationships,
			key=lambda item: (
				item.source_doctype,
				item.source_field,
				item.relationship_type,
				item.target_doctype or "",
			),
		)
	)
	sorted_diagnostics = tuple(
		sorted(
			diagnostics,
			key=lambda item: (
				item.severity,
				item.stage,
				item.doctype or "",
				item.fieldname or "",
				item.code,
			),
		)
	)
	captured = captured_at or datetime.now(timezone.utc)
	if captured.tzinfo is None:
		raise ValueError("captured_at must be timezone-aware")

	return SchemaSnapshot(
		snapshot_id=snapshot_id or str(uuid.uuid4()),
		captured_at=captured.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
		schema_format_version=SCHEMA_FORMAT_VERSION,
		frappe_version=frappe_version,
		erpnext_version=erpnext_version,
		site_identifier_hash=hash_site_identifier(site),
		doctypes=sorted_doctypes,
		relationships=sorted_relationships,
		raw_metadata=normalize_value(raw_metadata),
		metadata_hash=compute_metadata_hash(sorted_doctypes, sorted_relationships),
		completeness="incomplete" if any(item.severity == "error" for item in diagnostics) else "complete",
		diagnostics=sorted_diagnostics,
	)
