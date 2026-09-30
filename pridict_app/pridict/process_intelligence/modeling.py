from __future__ import annotations

import hashlib

from pridict.schema_intelligence.normalization import canonical_json

from pridict.process_intelligence.models import (
	PROCESS_MODEL_VERSION,
	DecisionPoint,
	EvidenceRecord,
	ExceptionPath,
	ProcessGap,
	ProcessModel,
	ProcessStep,
	ProcessTransition,
)
from pridict.process_intelligence.rules import represent_condition
from pridict.process_intelligence.schema_adapter import PurchasingSchemaView


def _stable_id(prefix: str, *parts: object) -> str:
	payload = ":".join(str(part) for part in parts)
	return f"{prefix}-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _schema_evidence(schema: PurchasingSchemaView, collected_at: str) -> list[EvidenceRecord]:
	records: list[EvidenceRecord] = []
	for doctype in schema.doctypes:
		provenance = doctype.provenance[0]
		records.append(
			EvidenceRecord(
				evidence_id=_stable_id("ev", "doctype", doctype.name),
				source_identifier=doctype.name,
				source_locator=provenance.source_path,
				source_type=provenance.source_type,
				collected_at=collected_at,
				source_version=schema.metadata_hash,
				assertion_kind="configured",
				confidence="HIGH",
				confidence_reason="The DocType exists in the verified SchemaSnapshot.",
				summary=f"Purchasing candidate DocType {doctype.name} is installed.",
				details={
					"module": doctype.module,
					"is_submittable": bool(doctype.flags.get("is_submittable")),
					"required_fields": [field.fieldname for field in doctype.fields if field.required],
					"status_fields": [
						field.fieldname
						for field in doctype.fields
						if field.fieldname in {"status", "workflow_state", "docstatus"}
					],
					"capable_roles": sorted(
						{
							permission.role
							for permission in doctype.permissions
							if any(bool(value) for value in permission.permissions.values())
						}
					),
				},
			)
		)
	for relationship in schema.relationships:
		provenance = relationship.provenance[0]
		records.append(
			EvidenceRecord(
				evidence_id=_stable_id("ev", "relationship", relationship.relationship_id),
				source_identifier=relationship.relationship_id,
				source_locator=provenance.source_path,
				source_type=provenance.source_type,
				collected_at=collected_at,
				source_version=schema.metadata_hash,
				assertion_kind="configured",
				confidence="HIGH",
				confidence_reason="The relationship is present in the verified SchemaSnapshot.",
				summary=(
					f"{relationship.source_doctype}.{relationship.source_field} structurally references "
					f"{relationship.target_doctype or 'a dynamic target'}."
				),
				details={"relationship_type": relationship.relationship_type},
				missing_evidence=("Transaction history proving process order",),
			)
		)
	for diagnostic in schema.diagnostics:
		records.append(
			EvidenceRecord(
				evidence_id=_stable_id(
					"ev", "schema-diagnostic", diagnostic.code, diagnostic.doctype, diagnostic.fieldname
				),
				source_identifier=diagnostic.code,
				source_locator=f"SchemaSnapshot/{schema.snapshot_id}/diagnostics",
				source_type="Schema Diagnostic",
				collected_at=collected_at,
				source_version=schema.metadata_hash,
				assertion_kind="configured",
				confidence="HIGH",
				confidence_reason="Schema Intelligence recorded this extraction diagnostic.",
				summary=diagnostic.message,
				details=diagnostic.to_dict(),
				missing_evidence=("Complete schema metadata",) if diagnostic.severity == "error" else (),
			)
		)
	return records


def _configuration_evidence(configuration: dict) -> list[EvidenceRecord]:
	collected_at = configuration["collected_at"]
	version = configuration["configuration_hash"]
	records: list[EvidenceRecord] = []
	for source_type, key, identifier_field in (
		("Workflow", "workflows", "name"),
		("Workflow Document State", "workflow_states", "name"),
		("Workflow Transition", "workflow_transitions", "name"),
		("Assignment Rule", "assignment_rules", "name"),
		("Notification", "notifications", "name"),
		("Client Script", "client_scripts", "name"),
		("Server Script", "server_scripts", "name"),
	):
		for record in configuration.get(key, []):
			identifier = str(record.get(identifier_field) or _stable_id("record", source_type, record))
			records.append(
				EvidenceRecord(
					evidence_id=_stable_id("ev", source_type, identifier),
					source_identifier=identifier,
					source_locator=f"database:{source_type}/{identifier}",
					source_type=source_type,
					collected_at=collected_at,
					source_version=version,
					assertion_kind="configured",
					confidence="HIGH",
					confidence_reason=f"The enabled or stored {source_type} record was read from the local site.",
					summary=f"Configured {source_type}: {identifier}.",
					details=record,
				)
			)
	return records


def build_purchasing_process_model(
	schema: PurchasingSchemaView,
	configuration: dict,
) -> ProcessModel:
	evidence = _schema_evidence(schema, configuration["collected_at"]) + _configuration_evidence(configuration)
	evidence_by_source = {(item.source_type, item.source_identifier): item.evidence_id for item in evidence}
	active_workflows: dict[str, list[dict]] = {}
	for item in configuration.get("workflows", []):
		if item.get("is_active"):
			active_workflows.setdefault(str(item.get("document_type")), []).append(item)
	workflow_by_doctype = {doctype: items[0] for doctype, items in active_workflows.items()}
	states_by_workflow: dict[str, list[dict]] = {}
	for item in configuration.get("workflow_states", []):
		states_by_workflow.setdefault(item.get("parent"), []).append(item)

	steps: list[ProcessStep] = []
	for doctype in schema.doctypes:
		workflow = workflow_by_doctype.get(doctype.name)
		native_states = tuple(
			str(item.get("state"))
			for item in states_by_workflow.get(workflow.get("name"), [])
			if item.get("state")
		) if workflow else (() if not doctype.flags.get("is_submittable") else ("Draft", "Submitted", "Cancelled"))
		steps.append(
			ProcessStep(
				step_id=_stable_id("step", doctype.name),
				name=doctype.name,
				step_type="HUMAN_APPROVAL" if workflow else "UNKNOWN",
				actor="UNKNOWN",
				inputs=tuple(field.fieldname for field in doctype.fields if field.required and not field.hidden),
				action=f"Create or update {doctype.name} using native ERP permissions and validations.",
				outputs=(doctype.name,),
				native_states=native_states,
				evidence_ids=(_stable_id("ev", "doctype", doctype.name),),
				assertion_kind="configured",
				confidence="HIGH",
			)
		)

	step_ids = {step.name: step.step_id for step in steps}
	transitions: list[ProcessTransition] = []
	decisions: list[DecisionPoint] = []
	exceptions: list[ExceptionPath] = []
	for item in configuration.get("workflow_transitions", []):
		workflow = next(
			(
				value
				for value in configuration.get("workflows", [])
				if value.get("name") == item.get("parent")
			),
			None,
		)
		if not workflow or workflow.get("document_type") not in step_ids:
			continue
		condition = represent_condition(item.get("condition"))
		evidence_id = evidence_by_source.get(("Workflow Transition", str(item.get("name"))))
		transition_id = _stable_id(
			"transition",
			item.get("parent"),
			item.get("state"),
			item.get("action"),
			item.get("next_state"),
		)
		transitions.append(
			ProcessTransition(
				transition_id=transition_id,
				from_step_id=step_ids[workflow["document_type"]],
				to_step_id=step_ids[workflow["document_type"]],
				transition_type="CONFIGURED_WORKFLOW_STATE_CHANGE",
				from_state=item.get("state"),
				to_state=item.get("next_state"),
				condition=condition.expression,
				condition_support=condition.support,
				evidence_ids=tuple(value for value in (evidence_id,) if value),
				assertion_kind="configured",
				confidence="HIGH",
			)
		)
		if condition.expression:
			decisions.append(
				DecisionPoint(
					decision_id=_stable_id("decision", transition_id),
					name=str(item.get("action") or "Configured workflow decision"),
					owner=str(item.get("allowed") or "UNKNOWN"),
					inputs=(condition.expression,),
					rules=(condition.note,),
					possible_outcomes=(str(item.get("next_state") or "UNKNOWN"), "TRANSITION_NOT_TAKEN"),
					risk_level="UNKNOWN",
					evidence_ids=tuple(value for value in (evidence_id,) if value),
					assertion_kind="configured",
					confidence="HIGH",
				)
			)
		if any(token in str(item.get("next_state") or "").lower() for token in ("reject", "cancel", "fail")):
			exceptions.append(
				ExceptionPath(
					exception_id=_stable_id("exception", transition_id),
					name=str(item.get("next_state")),
					trigger=condition.expression or str(item.get("action") or "Configured workflow action"),
					detection="Configured workflow transition",
					resolution="UNDEFINED",
					owner=str(item.get("allowed") or "UNKNOWN"),
					final_outcome=str(item.get("next_state")),
					evidence_ids=tuple(value for value in (evidence_id,) if value),
					assertion_kind="configured",
					confidence="HIGH",
				)
			)

	child_owners = {
		relationship.target_doctype: (relationship.source_doctype, relationship.relationship_id)
		for relationship in schema.relationships
		if relationship.relationship_type in {"CHILD_TABLE", "TABLE_MULTISELECT"}
		and relationship.source_doctype in step_ids
		and relationship.target_doctype
	}
	for relationship in schema.relationships:
		source_doctype = relationship.source_doctype
		evidence_ids = [_stable_id("ev", "relationship", relationship.relationship_id)]
		if source_doctype not in step_ids and source_doctype in child_owners:
			source_doctype, owner_relationship_id = child_owners[source_doctype]
			evidence_ids.append(_stable_id("ev", "relationship", owner_relationship_id))
		if source_doctype not in step_ids or relationship.target_doctype not in step_ids:
			continue
		transitions.append(
			ProcessTransition(
				transition_id=_stable_id("transition", relationship.relationship_id),
				from_step_id=step_ids[source_doctype],
				to_step_id=step_ids[relationship.target_doctype],
				transition_type="SCHEMA_REFERENCE_NOT_PROVEN_SEQUENCE",
				from_state=None,
				to_state=None,
				condition=None,
				condition_support="NOT_APPLICABLE",
				evidence_ids=tuple(sorted(evidence_ids)),
				assertion_kind="inferred",
				confidence="LOW",
			)
		)

	gaps = [
		ProcessGap(
			"gap-process-owner",
			"ownership",
			"Process owner is not established by schema or permissions.",
			tuple(step_ids),
		),
		ProcessGap(
			"gap-trigger",
			"business_rules",
			"A business trigger and start condition are not proven by configuration evidence.",
			tuple(step_ids),
		),
		ProcessGap(
			"gap-end",
			"business_rules",
			"A cross-document completion condition is not proven.",
			tuple(step_ids),
		),
		ProcessGap(
			"gap-history",
			"data",
			"Actual execution, timing, handoffs, rework and exceptions are not analyzed in this milestone.",
			tuple(step_ids),
		),
		ProcessGap(
			"gap-sequence",
			"documentation",
			"Schema references do not prove a mandatory purchasing sequence.",
			tuple(step_ids),
		),
	]
	if schema.completeness != "complete":
		gaps.append(
			ProcessGap(
				"gap-incomplete-schema",
				"data",
				"The source SchemaSnapshot is incomplete; affected assertions must be treated cautiously.",
				tuple(schema.doctype_names),
				tuple(
					_stable_id("ev", "schema-diagnostic", item.code, item.doctype, item.fieldname)
					for item in schema.diagnostics
				),
			)
		)
	workflow_names = {item.get("name") for item in configuration.get("workflows", [])}
	for item in configuration.get("workflow_states", []) + configuration.get("workflow_transitions", []):
		if item.get("parent") not in workflow_names:
			gaps.append(
				ProcessGap(
					_stable_id("gap", "missing-workflow", item.get("parent"), item.get("name")),
					"workflows",
					f"Configuration record {item.get('name')} references missing Workflow {item.get('parent')}",
					(str(item.get("name") or "UNKNOWN"),),
				)
			)
	configured_states = {
		(str(item.get("parent")), str(item.get("state")))
		for item in configuration.get("workflow_states", [])
		if item.get("parent") and item.get("state")
	}
	for item in configuration.get("workflow_transitions", []):
		for state_field in ("state", "next_state"):
			state = item.get(state_field)
			if state and (str(item.get("parent")), str(state)) not in configured_states:
				gaps.append(
					ProcessGap(
						_stable_id("gap", "missing-state", item.get("name"), state_field, state),
						"workflows",
						f"Workflow transition {item.get('name')} references undefined state {state}.",
						(str(item.get("name") or "UNKNOWN"), str(state)),
						(
							evidence_by_source.get(("Workflow Transition", str(item.get("name")))),
						)
						if evidence_by_source.get(("Workflow Transition", str(item.get("name"))))
						else (),
					)
				)
	for doctype, workflows in active_workflows.items():
		if len(workflows) > 1:
			gaps.append(
				ProcessGap(
					_stable_id("gap", "conflicting-workflows", doctype),
					"workflows",
					f"Multiple active Workflows were collected for {doctype}; the first stable record was modeled.",
					(doctype,),
					tuple(
						evidence_by_source.get(("Workflow", str(item.get("name"))))
						for item in workflows
						if evidence_by_source.get(("Workflow", str(item.get("name"))))
					),
				)
			)
	for name in schema.missing_candidates:
		gaps.append(
			ProcessGap(
				_stable_id("gap", "missing", name),
				"data",
				f"Candidate DocType {name} is absent from the snapshot.",
				(name,),
			)
		)
	for doctype in schema.doctypes:
		if doctype.name not in workflow_by_doctype:
			gaps.append(
				ProcessGap(
					_stable_id("gap", "workflow", doctype.name),
					"workflows",
					f"No active custom Workflow was found for {doctype.name}; native status remains separate.",
					(doctype.name,),
					(_stable_id("ev", "doctype", doctype.name),),
				)
			)
	for item in configuration.get("client_scripts", []) + configuration.get("server_scripts", []):
		source_type = "Client Script" if item in configuration.get("client_scripts", []) else "Server Script"
		gaps.append(
			ProcessGap(
				_stable_id("gap", "script", item.get("name")),
				"business_rules",
				f"Executable rule {item.get('name')} was hashed but not interpreted or executed.",
				(str(item.get("dt") or item.get("reference_doctype") or "UNKNOWN"),),
				(_stable_id("ev", source_type, item.get("name")),),
			)
		)

	stable_basis = {
		"schema": schema.metadata_hash,
		"configuration": configuration["configuration_hash"],
		"candidates": schema.doctype_names,
	}
	return ProcessModel(
		process_id=_stable_id("process", canonical_json(stable_basis)),
		model_version=PROCESS_MODEL_VERSION,
		name="Configured Purchasing Document Network",
		business_domain="Purchasing",
		business_objective=(
			"Support installed purchasing document capabilities without asserting an unproven mandatory sequence."
		),
		process_owner="UNKNOWN",
		trigger="UNKNOWN",
		trigger_source="UNKNOWN",
		start_condition="UNKNOWN",
		end_condition="UNKNOWN",
		upstream_process="UNKNOWN",
		downstream_process="UNKNOWN",
		schema_snapshot_id=schema.snapshot_id,
		schema_metadata_hash=schema.metadata_hash,
		configuration_hash=configuration["configuration_hash"],
		collected_at=configuration["collected_at"],
		steps=tuple(sorted(steps, key=lambda item: item.name)),
		transitions=tuple(sorted(transitions, key=lambda item: item.transition_id)),
		decisions=tuple(sorted(decisions, key=lambda item: item.decision_id)),
		exceptions=tuple(sorted(exceptions, key=lambda item: item.exception_id)),
		evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
		gaps=tuple(sorted(gaps, key=lambda item: item.gap_id)),
		metrics={
			"process_cycle_time": "DATA_NOT_AVAILABLE",
			"step_cycle_time": "DATA_NOT_AVAILABLE",
			"waiting_time": "DATA_NOT_AVAILABLE",
			"approval_time": "DATA_NOT_AVAILABLE",
			"handoffs": "DATA_NOT_AVAILABLE",
			"rework_rate": "DATA_NOT_AVAILABLE",
			"exception_rate": "DATA_NOT_AVAILABLE",
		},
	)
