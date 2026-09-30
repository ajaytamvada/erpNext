from __future__ import annotations

from pridict.process_intelligence.models import ProcessModel


def render_process_report(model: ProcessModel) -> str:
	lines = [
		"PROCESS",
		"",
		f"Process ID: {model.process_id}",
		f"Process Name: {model.name}",
		f"Business Domain: {model.business_domain}",
		f"Business Objective: {model.business_objective}",
		f"Process Owner: {model.process_owner}",
		"",
		"TRIGGER",
		"",
		f"Trigger: {model.trigger}",
		f"Trigger Source: {model.trigger_source}",
		f"Start Condition: {model.start_condition}",
		"",
		"PROCESS FLOW",
		"",
		"Numbering below is an activity inventory, not an asserted cross-document sequence.",
		"",
	]
	for index, step in enumerate(model.steps, start=1):
		lines.extend(
			[
				f"{index}. Step: {step.name}",
				f"   Type: {step.step_type}",
				f"   Actor: {step.actor}",
				f"   Input: {', '.join(step.inputs) or 'UNKNOWN'}",
				f"   Action: {step.action}",
				f"   Output: {', '.join(step.outputs) or 'UNKNOWN'}",
				"   Next Step: Not proven by schema relationships alone",
				"",
			]
		)
	lines.extend(["DECISION POINTS", ""])
	if not model.decisions:
		lines.extend(["Decision ID: NONE_CONFIGURED", "Decision: No evidence-backed decision point was found.", ""])
	for decision in model.decisions:
		lines.extend(
			[
				f"Decision ID: {decision.decision_id}",
				f"Decision: {decision.name}",
				f"Inputs: {', '.join(decision.inputs) or 'UNKNOWN'}",
				f"Rules: {', '.join(decision.rules) or 'UNKNOWN RULE'}",
				f"Possible Outcomes: {', '.join(decision.possible_outcomes)}",
				f"Actor: {decision.owner}",
				f"Evidence: {', '.join(decision.evidence_ids)}",
				f"Confidence: {decision.confidence}",
				"",
			]
		)
	lines.extend(["EXCEPTIONS", ""])
	if not model.exceptions:
		lines.extend(["Exception: NONE_CONFIGURED", "Resolution: UNDEFINED", ""])
	for item in model.exceptions:
		lines.extend(
			[
				f"Exception: {item.name}",
				f"Trigger: {item.trigger}",
				f"Detection: {item.detection}",
				f"Resolution: {item.resolution}",
				f"Owner: {item.owner}",
				f"Evidence: {', '.join(item.evidence_ids)}",
				f"Confidence: {item.confidence}",
				"",
			]
		)
	lines.extend(["HUMAN INVOLVEMENT", ""])
	for step in model.steps:
		lines.extend(
			[
				f"Step: {step.name}",
				f"Human Role: {step.actor}",
				"Reason: Permissions establish capability but not actual participation.",
				"",
			]
		)
	lines.extend(["PROCESS STATES", ""])
	for step in model.steps:
		lines.extend(
			[
				f"State: {step.name}: {', '.join(step.native_states) or 'UNKNOWN'}",
				"Entry Condition: UNKNOWN",
				"Exit Condition: UNKNOWN",
				"Allowed Actions: Native permissions, validations and configured workflow transitions",
				"Next States: See machine-readable graph",
				"",
			]
		)
	lines.extend(
		[
			"PROCESS GRAPH",
			"",
			"See the JSON graph artifact generated with this report.",
			"",
			"AUTOMATION ANALYSIS",
			"",
		]
	)
	for step in model.steps:
		lines.extend(
			[
				f"Step: {step.name}",
				f"Classification: {step.step_type}",
				"Reason: Classification is limited to installed metadata and configured workflow evidence.",
				"Automation Opportunity: NOT_ASSESSED",
				"Risk: UNKNOWN",
				"Human Control: REQUIRED_UNTIL_ANALYZED",
				"",
			]
		)
	lines.extend(["PROCESS METRICS", ""])
	for metric, value in model.metrics.items():
		lines.extend(
			[
				f"Metric: {metric}",
				f"Value: {value}",
				"Source: Transaction history deferred",
				"Confidence: LOW",
				"",
			]
		)
	lines.extend(
		[
			"OBSERVED VS INFERRED",
			"",
			"Observed: Installed DocTypes, fields, permissions and stored configuration records.",
			"Inferred: Schema references are structural associations only and do not prove process order.",
			"Unknown: Trigger, owner, mandatory sequence, completion condition and actual behavior.",
			"",
			"PROCESS GAPS",
			"",
		]
	)
	for gap in model.gaps:
		lines.append(f"- {gap.category}: {gap.description}")
	lines.extend(
		[
			"",
			"PROCESS SUMMARY",
			"",
			(
				"The installed system exposes a purchasing document network with native document lifecycles and any "
				"explicitly configured workflows. Cross-document business sequence, ownership, approvals and actual "
				"execution remain unknown unless directly supported by collected evidence."
			),
		]
	)
	return "\n".join(lines) + "\n"
