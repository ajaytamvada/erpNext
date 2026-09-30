from __future__ import annotations

from pridict.process_intelligence.transaction_models import ReconstructionResult


def render_reconstruction_report(result: ReconstructionResult) -> str:
	lines = [
		"PROCESS",
		"",
		f"Process ID: {result.reconstruction_id}",
		"Process Name: Purchasing Transaction Reconstruction",
		"Business Domain: Purchasing",
		"Business Objective: Describe explicit transaction activity without inferring an unproven sequence.",
		"Process Owner: UNKNOWN",
		f"Configured Process Model: {result.process_model_id}",
		f"Pseudonymous Company: {result.company_id}",
		f"Evidence Window: {result.start_date} through {result.end_date}",
		"",
		"TRIGGER",
		"",
		"Trigger: UNKNOWN",
		"Trigger Source: Transaction history establishes document creation, not the initiating business event.",
		"Start Condition: A document creation timestamp falls within the authorized company and date scope.",
		"",
		"PROCESS FLOW",
		"",
		f"Process Instances: {len(result.instances)}",
		f"Events: {len(result.events)}",
		f"Explicit Correlation Edges: {len(result.edges)}",
		"",
	]
	if not result.edges:
		lines.append("No explicit cross-document transaction links were found in scope.")
	for index, edge in enumerate(result.edges, start=1):
		lines.extend(
			[
				f"{index}. Step: Explicit {edge.relation_type}",
				"   Type: SYSTEM",
				"   Actor: UNKNOWN",
				f"Source: {edge.source_doctype} ({edge.source_document_id})",
				f"Target: {edge.target_doctype} ({edge.target_document_id})",
				f"   Output: Correlation {edge.edge_id}; allocation {edge.allocation_status}",
				"   Next Step: UNKNOWN",
				f"   Evidence: {', '.join(edge.evidence_ids)}; confidence {edge.confidence}",
				"",
			]
		)
	lines.extend(
		[
			"DECISION POINTS",
			"",
			"NOT_ANALYZED: Transaction evidence does not prove decision criteria or decision ownership.",
			"",
			"EXCEPTIONS",
			"",
			(
				"Cancellation, return and amendment records are reported as observations. Their business meaning, "
				"owner and "
				"resolution remain UNKNOWN unless separate evidence establishes them."
			),
			"",
			"HUMAN INVOLVEMENT",
			"",
			(
				"Pseudonymous actors are retained only where creation, Version or Workflow Action records identify "
				"a user. "
				"Permissions and record ownership do not prove business responsibility."
			),
			"",
			"PROCESS STATES",
			"",
			(
				"Native document states are preserved in evidence and events. No cross-document lifecycle is "
				"inferred, and "
				"current state observations have no inferred transition timestamp."
			),
			"",
			"PROCESS GRAPH",
			"",
			f"Directed document nodes: {len({event.document_id for event in result.events})}",
			f"Evidence-backed edges: {len(result.edges)}",
			"The machine-readable graph is emitted separately from this report.",
			"",
			"AUTOMATION ANALYSIS",
			"",
			"NOT_ANALYZED: Recommendations and agent candidates are deferred until process evidence is sufficient.",
			"",
			"PROCESS METRICS",
			"",
		]
	)
	for key, value in result.metrics.items():
		lines.extend([f"Metric: {key}", f"Value: {value}", ""])
	lines.extend(
		[
			"OBSERVED VS INFERRED",
			"",
			"Observed: Documents, explicit links, Version changes and Workflow Action records returned by the source.",
			"Inferred: Connected components group explicitly linked documents; no business sequence is inferred.",
			"Unknown: Trigger, ownership, decision rules, exception resolution and completion semantics.",
			"",
			"PROCESS GAPS",
			"",
		]
	)
	for gap in result.gaps:
		lines.append(f"- {gap}")
	lines.extend(
		[
			"",
			"PROCESS SUMMARY",
			"",
			(
				"This report reconstructs only explicit, authorized local transaction evidence. Creation timestamps are "
				"creation events, current states are observations, and no modification timestamp is treated as approval "
				"or completion time."
			),
		]
	)
	return "\n".join(lines) + "\n"
