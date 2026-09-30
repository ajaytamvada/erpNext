from __future__ import annotations

from pridict.process_intelligence.models import ProcessModel


def build_process_graph(model: ProcessModel) -> dict:
	nodes = [
		{
			"id": step.step_id,
			"type": "document_activity",
			"label": step.name,
			"native_states": list(step.native_states),
			"evidence_ids": list(step.evidence_ids),
		}
		for step in model.steps
	]
	edges = [
		{
			"id": transition.transition_id,
			"source": transition.from_step_id,
			"target": transition.to_step_id,
			"type": transition.transition_type,
			"from_state": transition.from_state,
			"to_state": transition.to_state,
			"condition": transition.condition,
			"condition_support": transition.condition_support,
			"assertion_kind": transition.assertion_kind,
			"confidence": transition.confidence,
			"evidence_ids": list(transition.evidence_ids),
		}
		for transition in model.transitions
	]
	return {"process_id": model.process_id, "directed": True, "nodes": nodes, "edges": edges}
