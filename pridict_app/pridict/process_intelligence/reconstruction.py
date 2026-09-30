from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from dataclasses import replace
from datetime import datetime
from typing import Any

from pridict.schema_intelligence.normalization import canonical_json

from pridict.process_intelligence.models import ProcessModel
from pridict.process_intelligence.schema_adapter import PurchasingSchemaView
from pridict.process_intelligence.transaction_models import (
	RECONSTRUCTION_VERSION,
	CorrelationEdge,
	ProcessInstance,
	ReconstructionResult,
	TransactionEvent,
	TransactionEvidence,
	TransactionScope,
)


LINK_SPECS = {
	"Request for Quotation Item": (("material_request", "Material Request", "material_request_item"),),
	"Supplier Quotation Item": (
		("request_for_quotation", "Request for Quotation", None),
		("material_request", "Material Request", "material_request_item"),
	),
	"Purchase Order Item": (
		("material_request", "Material Request", "material_request_item"),
		("supplier_quotation", "Supplier Quotation", "supplier_quotation_item"),
	),
	"Purchase Receipt Item": (
		("purchase_order", "Purchase Order", "purchase_order_item"),
		("material_request", "Material Request", "material_request_item"),
	),
	"Purchase Invoice Item": (
		("purchase_order", "Purchase Order", "po_detail"),
		("purchase_receipt", "Purchase Receipt", "pr_detail"),
		("material_request", "Material Request", "material_request_item"),
	),
}


def _identifier(site_hash: str, kind: str, *parts: object) -> str:
	value = ":".join(str(part or "") for part in parts)
	return f"{kind}-{hashlib.sha256(f'{site_hash}:{value}'.encode()).hexdigest()[:24]}"


def _iso(value: Any) -> str | None:
	if value is None or value == "":
		return None
	if isinstance(value, datetime):
		return value.isoformat()
	return str(value)


def _number(value: Any) -> float | None:
	if value in (None, ""):
		return None
	try:
		return float(value)
	except (TypeError, ValueError):
		return None


def reconstruct_purchasing(
	process_model: ProcessModel,
	schema: PurchasingSchemaView,
	scope: TransactionScope,
	dataset: dict[str, Any],
) -> ReconstructionResult:
	observed_at = dataset["collected_at"]
	company_id = _identifier(schema.site_identifier_hash, "company", scope.company)
	evidence: list[TransactionEvidence] = []
	events: list[TransactionEvent] = []
	edges: list[CorrelationEdge] = []
	gaps: list[str] = []
	document_ids: dict[tuple[str, str], str] = {}
	document_rows: dict[str, dict[str, Any]] = {}
	child_rows: dict[tuple[str, str], dict[str, Any]] = {}

	for doctype, rows in dataset["documents"].items():
		if len(rows) >= scope.max_records_per_doctype:
			gaps.append(f"POSSIBLE_TRUNCATION: {doctype} reached the configured record limit.")
		for row in rows:
			document_id = _identifier(schema.site_identifier_hash, "doc", doctype, row["name"])
			document_ids[(doctype, row["name"])] = document_id
			document_rows[document_id] = {**row, "_doctype": doctype}
			evidence_id = _identifier(schema.site_identifier_hash, "evidence", doctype, row["name"])
			evidence.append(
				TransactionEvidence(
					evidence_id,
					"Document",
					f"database:{doctype}/{document_id}",
					observed_at,
					f"Read {doctype} within the authorized scope.",
					{
						"document_type": doctype,
						"docstatus": row.get("docstatus"),
						"status": row.get("status"),
						"workflow_state": row.get("workflow_state"),
						"is_return": bool(row.get("is_return")),
					},
				)
			)
			actor_id = (
				_identifier(schema.site_identifier_hash, "actor", row.get("owner"))
				if row.get("owner")
				else None
			)
			events.extend(
				[
					TransactionEvent(
						_identifier(schema.site_identifier_hash, "event", doctype, row["name"], "created"),
						"DOCUMENT_CREATED",
						document_id,
						doctype,
						_iso(row.get("creation")),
						observed_at,
						"creation timestamp",
						actor_id,
						{},
						(evidence_id,),
						"HIGH",
					),
					TransactionEvent(
						_identifier(schema.site_identifier_hash, "event", doctype, row["name"], "state"),
						"CURRENT_DOCUMENT_STATE_OBSERVED",
						document_id,
						doctype,
						None,
						observed_at,
						"observation time; not a state-change timestamp",
						None,
						{
							"docstatus": row.get("docstatus"),
							"status": row.get("status"),
							"workflow_state": row.get("workflow_state"),
						},
						(evidence_id,),
						"HIGH",
					),
				]
			)

	for child_doctype, rows in dataset["children"].items():
		for row in rows:
			child_rows[(child_doctype, row["name"])] = row

	def add_document_edge(
		*,
		source_doctype: str,
		source_name: str,
		target_doctype: str,
		target_name: str,
		relation_type: str,
		target_row: dict[str, Any] | None = None,
		target_row_doctype: str | None = None,
		source_row_name: str | None = None,
		source_row_doctype: str | None = None,
		quantity: float | None = None,
		allocated_amount: float | None = None,
		allocation_status: str = "UNKNOWN",
	):
		source_document_id = document_ids.get(
			(source_doctype, source_name),
			_identifier(schema.site_identifier_hash, "doc", source_doctype, source_name),
		)
		target_document_id = document_ids.get(
			(target_doctype, target_name),
			_identifier(schema.site_identifier_hash, "doc", target_doctype, target_name),
		)
		target_row_id = (
			_identifier(schema.site_identifier_hash, "row", target_row_doctype, target_row.get("name"))
			if target_row
			else None
		)
		source_row_id = (
			_identifier(schema.site_identifier_hash, "row", source_row_doctype, source_row_name)
			if source_row_name and source_row_doctype
			else None
		)
		evidence_id = _identifier(
			schema.site_identifier_hash,
			"evidence",
			relation_type,
			source_doctype,
			source_name,
			target_doctype,
			target_name,
			target_row.get("name") if target_row else "",
		)
		evidence.append(
			TransactionEvidence(
				evidence_id,
				"Explicit Transaction Link",
				f"database:{target_doctype}/{target_document_id}",
				observed_at,
				f"{target_doctype} explicitly references {source_doctype}.",
				{"relation_type": relation_type, "target_row_id": target_row_id},
			)
		)
		edges.append(
			CorrelationEdge(
				_identifier(schema.site_identifier_hash, "edge", evidence_id),
				source_document_id,
				target_document_id,
				source_doctype,
				target_doctype,
				source_row_id,
				target_row_id,
				relation_type,
				quantity,
				allocated_amount,
				allocation_status,
				(source_doctype, source_name) in document_ids,
				(target_doctype, target_name) in document_ids,
				(evidence_id,),
				"HIGH",
			)
		)
		if (source_doctype, source_name) not in document_ids:
			gaps.append(f"OUT_OF_SCOPE_SOURCE: {source_doctype} referenced by {target_doctype}.")
		if (target_doctype, target_name) not in document_ids:
			gaps.append(f"OUT_OF_SCOPE_TARGET: {target_doctype} references {source_doctype}.")

	for target_doctype, rows in dataset["documents"].items():
		for row in rows:
			for fieldname, relation_type in (("amended_from", "AMENDS"), ("return_against", "RETURNS")):
				if row.get(fieldname):
					add_document_edge(
						source_doctype=target_doctype,
						source_name=row[fieldname],
						target_doctype=target_doctype,
						target_name=row["name"],
						relation_type=relation_type,
					)

	for child_doctype, link_specs in LINK_SPECS.items():
		for row in dataset["children"].get(child_doctype, []):
			for link_field, source_doctype, source_row_field in link_specs:
				if not row.get(link_field):
					continue
				add_document_edge(
					source_doctype=source_doctype,
					source_name=row[link_field],
					target_doctype=row["parenttype"],
					target_name=row["parent"],
					relation_type="ITEM_LEVEL_REFERENCE",
					target_row=row,
					target_row_doctype=child_doctype,
					source_row_name=row.get(source_row_field) if source_row_field else None,
					source_row_doctype=_child_doctype_for(source_doctype) if source_row_field else None,
					quantity=_number(row.get("stock_qty") if row.get("stock_qty") is not None else row.get("qty")),
				)

	for row in dataset["children"].get("Payment Entry Reference", []):
		if (
			row.get("reference_doctype") not in document_ids_by_doctype(document_ids)
			or not row.get("reference_name")
		):
			continue
		add_document_edge(
			source_doctype=row["reference_doctype"],
			source_name=row["reference_name"],
			target_doctype="Payment Entry",
			target_name=row["parent"],
			relation_type="PAYMENT_ALLOCATION",
			target_row=row,
			target_row_doctype="Payment Entry Reference",
			allocated_amount=_number(row.get("allocated_amount")),
			allocation_status="AMOUNT_RECORDED",
		)

	for row in dataset.get("versions", []):
		try:
			payload = row.get("data") or {}
			if isinstance(payload, str):
				payload = json.loads(payload)
		except (TypeError, ValueError):
			gaps.append("UNPARSEABLE_VERSION_DATA: a Version record could not be parsed.")
			continue
		for change in payload.get("changed", []):
			if len(change) < 3 or change[0] not in {"docstatus", "status", "workflow_state"}:
				continue
			document_id = document_ids.get((row.get("ref_doctype"), row.get("docname")))
			if not document_id:
				continue
			evidence_id = _identifier(
				schema.site_identifier_hash,
				"evidence",
				"version",
				row.get("name"),
				change[0],
			)
			evidence.append(
				TransactionEvidence(
					evidence_id,
					"Version",
					f"database:Version/{_identifier(schema.site_identifier_hash, 'version', row.get('name'))}",
					observed_at,
					f"Version records a change to {change[0]}.",
					{"field": change[0], "old": change[1], "new": change[2]},
				)
			)
			events.append(
				TransactionEvent(
					_identifier(schema.site_identifier_hash, "event", "version", row.get("name"), change[0]),
					"DOCUMENT_STATE_CHANGED",
					document_id,
					row.get("ref_doctype"),
					_iso(row.get("creation")),
					observed_at,
					"Version creation timestamp",
					(
						_identifier(schema.site_identifier_hash, "actor", row.get("owner"))
						if row.get("owner")
						else None
					),
					{"field": change[0], "old": change[1], "new": change[2]},
					(evidence_id,),
					"HIGH",
				)
			)

	for row in dataset.get("workflow_actions", []):
		document_id = document_ids.get((row.get("reference_doctype"), row.get("reference_name")))
		if not document_id:
			continue
		evidence_id = _identifier(
			schema.site_identifier_hash,
			"evidence",
			"workflow-action",
			row.get("name"),
		)
		evidence.append(
			TransactionEvidence(
				evidence_id,
				"Workflow Action",
				(
					"database:Workflow Action/"
					+ _identifier(schema.site_identifier_hash, "workflow-action", row.get("name"))
				),
				observed_at,
				"A Workflow Action record exists for the document.",
				{"workflow_state": row.get("workflow_state"), "status": row.get("status")},
			)
		)
		events.append(
			TransactionEvent(
				_identifier(schema.site_identifier_hash, "event", "workflow-action", row.get("name")),
				"WORKFLOW_ACTION_RECORDED",
				document_id,
				row.get("reference_doctype"),
				_iso(row.get("creation")),
				observed_at,
				"Workflow Action record creation timestamp; not assumed to be completion time",
				(
					_identifier(schema.site_identifier_hash, "actor", row.get("completed_by"))
					if row.get("completed_by")
					else None
				),
				{"workflow_state": row.get("workflow_state"), "status": row.get("status")},
				(evidence_id,),
				"MEDIUM",
			)
		)

	edges = _classify_allocations(edges, child_rows, schema.site_identifier_hash)
	gaps.extend(_correlation_quality_gaps(edges))
	for child_doctype, rows in dataset.get("children", {}).items():
		if len(rows) >= scope.max_records_per_doctype:
			gaps.append(f"POSSIBLE_TRUNCATION: {child_doctype} reached the configured record limit.")
	for evidence_type, rows in (
		("Version", dataset.get("versions", [])),
		("Workflow Action", dataset.get("workflow_actions", [])),
	):
		if len(rows) >= scope.max_records_per_doctype:
			gaps.append(f"POSSIBLE_TRUNCATION: {evidence_type} reached the configured record limit.")
	instances = _build_instances(document_rows, events, edges, schema.site_identifier_hash)
	metrics = build_reconstruction_metrics(document_rows, edges, instances)
	if not dataset.get("workflow_actions"):
		gaps.append("APPROVAL_TIMES: DATA_NOT_AVAILABLE")
	gaps.append("COMPLETION_TIMES: DATA_NOT_AVAILABLE unless explicit auditable terminal events exist.")
	stable_basis = {
		"process_model_id": process_model.process_id,
		"company_id": company_id,
		"start_date": scope.start_date,
		"end_date": scope.end_date,
		"events": [event.event_id for event in sorted(events, key=lambda item: item.event_id)],
		"edges": [edge.edge_id for edge in sorted(edges, key=lambda item: item.edge_id)],
	}
	return ReconstructionResult(
		reconstruction_id=_identifier(schema.site_identifier_hash, "reconstruction", canonical_json(stable_basis)),
		version=RECONSTRUCTION_VERSION,
		process_model_id=process_model.process_id,
		company_id=company_id,
		start_date=scope.start_date,
		end_date=scope.end_date,
		collected_at=observed_at,
		evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
		events=tuple(sorted(events, key=lambda item: item.event_id)),
		edges=tuple(sorted(edges, key=lambda item: item.edge_id)),
		instances=tuple(sorted(instances, key=lambda item: item.instance_id)),
		metrics=metrics,
		gaps=tuple(sorted(set(gaps))),
	)


def document_ids_by_doctype(document_ids: dict[tuple[str, str], str]) -> set[str]:
	return {doctype for doctype, _name in document_ids}


def _child_doctype_for(parent_doctype: str) -> str:
	return {
		"Material Request": "Material Request Item",
		"Request for Quotation": "Request for Quotation Item",
		"Supplier Quotation": "Supplier Quotation Item",
		"Purchase Order": "Purchase Order Item",
		"Purchase Receipt": "Purchase Receipt Item",
		"Purchase Invoice": "Purchase Invoice Item",
		"Payment Entry": "Payment Entry Reference",
	}[parent_doctype]


def _classify_allocations(
	edges: list[CorrelationEdge],
	child_rows: dict[tuple[str, str], dict[str, Any]],
	site_hash: str,
) -> list[CorrelationEdge]:
	totals: dict[str, float] = defaultdict(float)
	for edge in edges:
		if edge.source_row_id and edge.quantity is not None:
			totals[edge.source_row_id] += edge.quantity
	result = []
	for edge in edges:
		status = edge.allocation_status
		if edge.source_row_id and edge.quantity is not None:
			source_child_doctype = _child_doctype_for(edge.source_doctype)
			raw_source = next(
				(
					row
					for (child_doctype, name), row in child_rows.items()
					if child_doctype == source_child_doctype
					and _identifier(site_hash, "row", child_doctype, name) == edge.source_row_id
				),
				None,
			)
			source_qty = _number(raw_source.get("stock_qty") if raw_source else None)
			if source_qty is None and raw_source:
				source_qty = _number(raw_source.get("qty"))
			if source_qty is not None:
				allocated = totals[edge.source_row_id]
				if abs(allocated - source_qty) < 1e-9:
					status = "FULL"
				elif allocated < source_qty:
					status = "PARTIAL"
				else:
					status = "OVER_ALLOCATED"
		result.append(replace(edge, allocation_status=status))
	return result


def _correlation_quality_gaps(edges: list[CorrelationEdge]) -> list[str]:
	gaps = []
	edge_counts: dict[str, int] = defaultdict(int)
	target_sources: dict[tuple[str, str, str], set[tuple[str, str | None]]] = defaultdict(set)
	adjacency: dict[str, set[str]] = defaultdict(set)

	for edge in edges:
		edge_counts[edge.edge_id] += 1
		if edge.target_row_id:
			target_sources[(edge.target_row_id, edge.relation_type, edge.source_doctype)].add(
				(edge.source_document_id, edge.source_row_id)
			)
		if edge.source_in_scope and edge.target_in_scope:
			adjacency[edge.source_document_id].add(edge.target_document_id)

	duplicate_count = sum(count - 1 for count in edge_counts.values() if count > 1)
	if duplicate_count:
		gaps.append(f"DUPLICATE_CORRELATION: {duplicate_count} duplicate explicit link(s) detected.")

	conflict_count = sum(len(sources) - 1 for sources in target_sources.values() if len(sources) > 1)
	if conflict_count:
		gaps.append(f"CONFLICTING_CORRELATION: {conflict_count} conflicting explicit link(s) detected.")

	if _has_directed_cycle(adjacency):
		gaps.append("CIRCULAR_CORRELATION: a cycle exists in explicit transaction links.")

	return gaps


def _has_directed_cycle(adjacency: dict[str, set[str]]) -> bool:
	visiting: set[str] = set()
	visited: set[str] = set()

	def visit(node: str) -> bool:
		if node in visiting:
			return True
		if node in visited:
			return False
		visiting.add(node)
		for neighbor in sorted(adjacency.get(node, ())):
			if visit(neighbor):
				return True
		visiting.remove(node)
		visited.add(node)
		return False

	return any(visit(node) for node in sorted(adjacency) if node not in visited)


def _build_instances(
	documents: dict[str, dict[str, Any]],
	events: list[TransactionEvent],
	edges: list[CorrelationEdge],
	site_hash: str,
) -> list[ProcessInstance]:
	adjacency: dict[str, set[str]] = {document_id: set() for document_id in documents}
	for edge in edges:
		if edge.source_document_id in documents and edge.target_document_id in documents:
			adjacency[edge.source_document_id].add(edge.target_document_id)
			adjacency[edge.target_document_id].add(edge.source_document_id)
	events_by_document: dict[str, list[TransactionEvent]] = defaultdict(list)
	for event in events:
		events_by_document[event.document_id].append(event)
	instances = []
	visited: set[str] = set()
	for document_id in sorted(documents):
		if document_id in visited:
			continue
		queue = deque([document_id])
		component = []
		visited.add(document_id)
		while queue:
			current = queue.popleft()
			component.append(current)
			for neighbor in adjacency[current]:
				if neighbor not in visited:
					visited.add(neighbor)
					queue.append(neighbor)
		component_events = [event for item in component for event in events_by_document[item]]
		occurred = sorted(event.occurred_at for event in component_events if event.occurred_at)
		component_edges = [
			edge.edge_id
			for edge in edges
			if edge.source_document_id in component and edge.target_document_id in component
		]
		instances.append(
			ProcessInstance(
				_identifier(site_hash, "instance", *sorted(component)),
				tuple(sorted(component)),
				tuple(sorted(event.event_id for event in component_events)),
				tuple(sorted(component_edges)),
				occurred[0] if occurred else None,
				None,
				"UNKNOWN",
			)
		)
	return instances


def build_reconstruction_metrics(
	documents: dict[str, dict[str, Any]],
	edges: list[CorrelationEdge],
	instances: list[ProcessInstance],
) -> dict[str, Any]:
	rows = list(documents.values())
	linked = {edge.source_document_id for edge in edges} | {edge.target_document_id for edge in edges}
	volume: dict[str, int] = defaultdict(int)
	for row in rows:
		volume[str(row.get("_doctype") or "UNKNOWN")] += 1
	return {
		"document_volume": dict(sorted(volume.items())),
		"process_instance_count": len(instances),
		"correlation_edge_count": len(edges),
		"unlinked_document_count": sum(document_id not in linked for document_id in documents),
		"cancellation_count": sum(int(row.get("docstatus") or 0) == 2 for row in rows),
		"return_count": sum(bool(row.get("is_return")) for row in rows),
		"amendment_count": sum(bool(row.get("amended_from")) for row in rows),
		"partial_allocation_edge_count": sum(edge.allocation_status == "PARTIAL" for edge in edges),
		"over_allocation_edge_count": sum(edge.allocation_status == "OVER_ALLOCATED" for edge in edges),
		"process_cycle_time": "DATA_NOT_AVAILABLE",
		"approval_time": "DATA_NOT_AVAILABLE",
		"waiting_time": "DATA_NOT_AVAILABLE",
		"handoff_count": "DATA_NOT_AVAILABLE",
	}
