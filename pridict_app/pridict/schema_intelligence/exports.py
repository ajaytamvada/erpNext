from __future__ import annotations

import csv
import io
import json
from typing import Any

from pridict.schema_intelligence.artifacts import relationship_graph
from pridict.schema_intelligence.graph import relationship_subgraph
from pridict.schema_intelligence.governance import get_settings
from pridict.schema_intelligence.reviews import comparison_payload, get_review
from pridict.schema_intelligence.service import get_default_repository, snapshot_summary


def export_snapshot_summary(snapshot_id: str) -> dict[str, str]:
	snapshot = get_default_repository().load(snapshot_id)
	return _download(f"schema-snapshot-{snapshot_id}.json", snapshot_summary(snapshot), "application/json")


def export_comparison(review_name: str) -> dict[str, str]:
	return _download(f"schema-comparison-{review_name}.json", comparison_payload(review_name), "application/json")


def export_review(review_name: str) -> dict[str, str]:
	review = get_review(review_name)
	review.pop("comparison_repository_identifier", None)
	return _download(f"schema-review-{review_name}.json", review, "application/json")


def export_findings_csv(review_name: str) -> dict[str, str]:
	findings = comparison_payload(review_name)["findings"]
	stream = io.StringIO(newline="")
	writer = csv.writer(stream, lineterminator="\n")
	writer.writerow(["finding_id", "severity", "rule_id", "category", "path", "doctype", "fieldname", "explanation"])
	for item in findings:
		writer.writerow([item["finding_id"], item["severity"], item["rule_id"], item["category"], item["path"], item.get("doctype"), item.get("fieldname"), item["explanation"]])
	return {"filename": f"schema-findings-{review_name}.csv", "content": stream.getvalue(), "content_type": "text/csv"}


def export_subgraph(snapshot_id: str, root_doctype: str, *, hops: int = 1, direction: str = "both", relationship_types=None, format: str = "json"):
	settings = get_settings()
	snapshot = get_default_repository().load(snapshot_id)
	payload = relationship_subgraph(
		snapshot,
		root_doctype,
		hops=hops,
		direction=direction,
		relationship_types=set(relationship_types or []),
		node_limit=settings["graph_node_limit"],
		edge_limit=settings["graph_edge_limit"],
	)
	if format == "json":
		return _download(f"schema-graph-{root_doctype}.json", payload, "application/json")
	if format == "mermaid":
		return {"filename": f"schema-graph-{root_doctype}.mmd", "content": relationship_graph(_subgraph_snapshot(snapshot, payload)), "content_type": "text/plain"}
	raise ValueError("Unsupported subgraph export format.")


def future_analysis_payload(review_name: str, *, maximum_findings: int = 100, maximum_doctypes: int = 25) -> dict[str, Any]:
	comparison = comparison_payload(review_name)
	repository = get_default_repository()
	candidate = repository.load(comparison["after_snapshot_id"])
	affected = sorted({item.get("doctype") for item in comparison["findings"] if item.get("doctype")})[:maximum_doctypes]
	doctypes = {item.name: item.to_dict() for item in candidate.doctypes if item.name in affected}
	for value in doctypes.values():
		value.pop("raw_metadata", None)
	return {
		"contract_version": "1",
		"snapshot": snapshot_summary(candidate),
		"selected_doctypes": doctypes,
		"findings": comparison["findings"][:maximum_findings],
		"truncated": len(comparison["findings"]) > maximum_findings or len(affected) >= maximum_doctypes,
		"exclusions": ["raw_metadata", "business_records", "credentials", "server_scripts", "external_transmission"],
	}


def _download(filename: str, value: Any, content_type: str) -> dict[str, str]:
	return {"filename": filename, "content": json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", "content_type": content_type}


def _subgraph_snapshot(snapshot, payload):
	from dataclasses import replace

	edge_ids = {item["relationship_id"] for item in payload["edges"]}
	nodes = set(payload["nodes"])
	return replace(
		snapshot,
		doctypes=tuple(item for item in snapshot.doctypes if item.name in nodes),
		relationships=tuple(item for item in snapshot.relationships if item.relationship_id in edge_ids),
	)
