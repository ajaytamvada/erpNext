from __future__ import annotations

import json

import frappe

from pridict.schema_intelligence.artifacts import doctype_schema_payload, relationship_graph
from pridict.schema_intelligence.comparison import compare_snapshots
from pridict.schema_intelligence.service import get_default_repository


def export_doctype(snapshot_id: str, doctype: str = "Sales Order"):
	"""Write a normalized DocType example and Mermaid graph beside persisted snapshots."""
	repository = get_default_repository()
	snapshot = repository.load(snapshot_id)
	output_directory = repository.root / "artifacts"
	output_directory.mkdir(parents=True, exist_ok=True)
	stem = doctype.lower().replace(" ", "-")
	schema_path = output_directory / f"{stem}-schema.json"
	graph_path = output_directory / f"{stem}-relationships.mmd"
	schema_path.write_text(
		json.dumps(doctype_schema_payload(snapshot, doctype), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
		encoding="utf-8",
	)
	graph_path.write_text(relationship_graph(snapshot, doctype), encoding="utf-8")
	return {"schema": str(schema_path), "graph": str(graph_path)}


def export_comparison(before_snapshot_id: str, after_snapshot_id: str, filename: str = "schema-diff.json"):
	"""Write a deterministic comparison beside persisted snapshots."""
	if "/" in filename or "\\" in filename or filename in ("", ".", ".."):
		raise ValueError("filename must be a plain local filename")
	repository = get_default_repository()
	before = repository.load(before_snapshot_id)
	after = repository.load(after_snapshot_id)
	output_directory = repository.root / "artifacts"
	output_directory.mkdir(parents=True, exist_ok=True)
	path = output_directory / filename
	path.write_text(
		json.dumps(compare_snapshots(before, after), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
		encoding="utf-8",
	)
	return str(path)


def snapshot_location():
	"""Return the private snapshot directory for trusted bench operators."""
	frappe.only_for("System Manager")
	return str(get_default_repository().root)
