from __future__ import annotations

from pridict.process_intelligence.transaction_models import ReconstructionResult


def build_reconstruction_graph(result: ReconstructionResult) -> dict:
	document_types = {
		event.document_id: event.document_type
		for event in result.events
		if event.event_type == "CURRENT_DOCUMENT_STATE_OBSERVED"
	}
	in_scope = {document_id: True for document_id in document_types}
	for edge in result.edges:
		document_types.setdefault(edge.source_document_id, edge.source_doctype)
		document_types.setdefault(edge.target_document_id, edge.target_doctype)
		in_scope[edge.source_document_id] = in_scope.get(edge.source_document_id, False) or edge.source_in_scope
		in_scope[edge.target_document_id] = in_scope.get(edge.target_document_id, False) or edge.target_in_scope
	return {
		"reconstruction_id": result.reconstruction_id,
		"directed": True,
		"nodes": [
			{
				"id": document_id,
				"type": "document",
				"document_type": document_type,
				"in_scope": in_scope[document_id],
			}
			for document_id, document_type in sorted(document_types.items())
		],
		"edges": [item.to_dict() for item in result.edges],
	}
