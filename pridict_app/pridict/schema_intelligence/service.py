from __future__ import annotations

from pathlib import Path

import frappe

from pridict.schema_intelligence.comparison import compare_snapshots
from pridict.schema_intelligence.extraction import MetadataSource, extract_schema
from pridict.schema_intelligence.frappe_source import FrappeMetadataSource
from pridict.schema_intelligence.models import SchemaSnapshot
from pridict.schema_intelligence.persistence import FilesystemSnapshotRepository, SnapshotRepository


def capture_snapshot(source: MetadataSource | None = None) -> SchemaSnapshot:
	return extract_schema(source or FrappeMetadataSource())


def persist_snapshot(
	snapshot: SchemaSnapshot,
	repository: SnapshotRepository | None = None,
	*,
	require_complete: bool = True,
) -> SchemaSnapshot:
	(repository or get_default_repository()).save(snapshot, require_complete=require_complete)
	return snapshot


def capture_and_persist_snapshot(*, require_complete: bool = True) -> SchemaSnapshot:
	snapshot = capture_snapshot()
	return persist_snapshot(snapshot, require_complete=require_complete)


def compare_persisted_snapshots(
	before_snapshot_id: str,
	after_snapshot_id: str,
	repository: SnapshotRepository | None = None,
):
	repository = repository or get_default_repository()
	return compare_snapshots(repository.load(before_snapshot_id), repository.load(after_snapshot_id))


def list_snapshot_summaries(repository: SnapshotRepository | None = None) -> list[dict]:
	repository = repository or get_default_repository()
	summaries = [snapshot_summary(repository.load(snapshot_id)) for snapshot_id in repository.list_ids()]
	return sorted(summaries, key=lambda item: item["captured_at"], reverse=True)


def get_snapshot_overview(
	snapshot_id: str,
	repository: SnapshotRepository | None = None,
) -> dict:
	repository = repository or get_default_repository()
	snapshot = repository.load(snapshot_id)
	relationship_counts: dict[str, int] = {}
	for relationship in snapshot.relationships:
		relationship_counts[relationship.source_doctype] = (
			relationship_counts.get(relationship.source_doctype, 0) + 1
		)
	diagnostic_counts: dict[str, dict[str, int]] = {}
	for diagnostic in snapshot.diagnostics:
		if not diagnostic.doctype:
			continue
		counts = diagnostic_counts.setdefault(diagnostic.doctype, {"warning": 0, "error": 0})
		counts[diagnostic.severity] += 1

	return {
		"summary": snapshot_summary(snapshot),
		"doctypes": [
			{
				"name": doctype.name,
				"module": doctype.module,
				"flags": doctype.flags,
				"field_count": len(doctype.fields),
				"permission_count": len(doctype.permissions),
				"relationship_count": relationship_counts.get(doctype.name, 0),
				"warning_count": diagnostic_counts.get(doctype.name, {}).get("warning", 0),
				"error_count": diagnostic_counts.get(doctype.name, {}).get("error", 0),
			}
			for doctype in snapshot.doctypes
		],
		"diagnostics": [item.to_dict() for item in snapshot.diagnostics],
	}


def get_doctype_schema(
	snapshot_id: str,
	doctype_name: str,
	repository: SnapshotRepository | None = None,
) -> dict:
	from pridict.schema_intelligence.artifacts import doctype_schema_payload

	repository = repository or get_default_repository()
	return doctype_schema_payload(repository.load(snapshot_id), doctype_name)


def snapshot_summary(snapshot: SchemaSnapshot) -> dict:
	return {
		"snapshot_id": snapshot.snapshot_id,
		"captured_at": snapshot.captured_at,
		"schema_format_version": snapshot.schema_format_version,
		"frappe_version": snapshot.frappe_version,
		"erpnext_version": snapshot.erpnext_version,
		"site_identifier_hash": snapshot.site_identifier_hash,
		"metadata_hash": snapshot.metadata_hash,
		"completeness": snapshot.completeness,
		"doctype_count": len(snapshot.doctypes),
		"field_count": sum(len(item.fields) for item in snapshot.doctypes),
		"relationship_count": len(snapshot.relationships),
		"permission_count": sum(len(item.permissions) for item in snapshot.doctypes),
		"warning_count": sum(item.severity == "warning" for item in snapshot.diagnostics),
		"error_count": sum(item.severity == "error" for item in snapshot.diagnostics),
	}


def get_default_repository() -> FilesystemSnapshotRepository:
	root = Path(frappe.get_site_path("private", "files", "pridict-schema-intelligence"))
	return FilesystemSnapshotRepository(root)
