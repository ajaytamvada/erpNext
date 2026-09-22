from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pridict.schema_intelligence.comparison import compare_snapshots
from pridict.schema_intelligence.models import RelationshipSchema, SchemaSnapshot


def doctype_schema_payload(snapshot: SchemaSnapshot, doctype: str) -> dict:
	item = next((item for item in snapshot.doctypes if item.name == doctype), None)
	if item is None:
		raise KeyError(f"DocType {doctype} is not present in snapshot {snapshot.snapshot_id}")
	return {
		"snapshot_id": snapshot.snapshot_id,
		"captured_at": snapshot.captured_at,
		"schema_format_version": snapshot.schema_format_version,
		"metadata_hash": snapshot.metadata_hash,
		"completeness": snapshot.completeness,
		"doctype": item.to_dict(),
		"relationships": [
			relationship.to_dict()
			for relationship in snapshot.relationships
			if relationship.source_doctype == doctype
		],
	}


def relationship_graph(snapshot: SchemaSnapshot, root_doctype: str, depth: int = 0) -> str:
	if depth < 0:
		raise ValueError("depth must not be negative")
	known_doctypes = {item.name for item in snapshot.doctypes}
	if root_doctype not in known_doctypes:
		raise KeyError(f"DocType {root_doctype} is not present in snapshot {snapshot.snapshot_id}")

	selected: list[RelationshipSchema] = []
	frontier = {root_doctype}
	visited = set()
	for _level in range(depth + 1):
		if not frontier:
			break
		next_frontier = set()
		for relationship in snapshot.relationships:
			if relationship.source_doctype not in frontier:
				continue
			selected.append(relationship)
			if relationship.target_doctype in known_doctypes:
				next_frontier.add(relationship.target_doctype)
		visited.update(frontier)
		frontier = next_frontier - visited

	lines = ["flowchart LR"]
	nodes = {root_doctype}
	for relationship in selected:
		nodes.add(relationship.source_doctype)
		if relationship.target_doctype:
			nodes.add(relationship.target_doctype)
		else:
			nodes.add(_dynamic_node_name(relationship))
	for node in sorted(nodes):
		lines.append(f'    {_node_id(node)}["{_escape_label(node)}"]')
	for relationship in sorted(selected, key=lambda item: item.relationship_id):
		target = relationship.target_doctype or _dynamic_node_name(relationship)
		label = f"{relationship.source_field} · {relationship.relationship_type}"
		lines.append(
			f'    {_node_id(relationship.source_doctype)} -->|"{_escape_label(label)}"| {_node_id(target)}'
		)
	return "\n".join(lines) + "\n"


def write_example_bundle(
	snapshot: SchemaSnapshot,
	doctype: str,
	output_directory: str | Path,
	*,
	before: SchemaSnapshot | None = None,
) -> dict[str, str]:
	output_directory = Path(output_directory)
	output_directory.mkdir(parents=True, exist_ok=True)
	stem = doctype.lower().replace(" ", "-")
	schema_path = output_directory / f"{stem}-schema.json"
	graph_path = output_directory / f"{stem}-relationships.mmd"
	schema_path.write_text(
		json.dumps(doctype_schema_payload(snapshot, doctype), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
		encoding="utf-8",
	)
	graph_path.write_text(relationship_graph(snapshot, doctype), encoding="utf-8")
	result = {"schema": str(schema_path), "graph": str(graph_path)}
	if before is not None:
		diff_path = output_directory / f"{stem}-schema-diff.json"
		diff_path.write_text(
			json.dumps(compare_snapshots(before, snapshot), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
			encoding="utf-8",
		)
		result["diff"] = str(diff_path)
	return result


def _dynamic_node_name(relationship: RelationshipSchema) -> str:
	return f"Dynamic target selected by {relationship.source_doctype}.{relationship.selector_field}"


def _node_id(label: str) -> str:
	return f"n_{hashlib.sha256(label.encode()).hexdigest()[:12]}"


def _escape_label(label: str) -> str:
	return label.replace("\\", "\\\\").replace('"', '\\"')
