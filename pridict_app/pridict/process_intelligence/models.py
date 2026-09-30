from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


PROCESS_MODEL_VERSION = "1.0.0"
AssertionKind = Literal["configured", "documented", "observed", "inferred", "unknown"]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
StepType = Literal[
	"DETERMINISTIC_WORKFLOW",
	"HUMAN_TASK",
	"HUMAN_APPROVAL",
	"SYSTEM_AUTOMATION",
	"RULE_BASED_DECISION",
	"REASONING_REQUIRED",
	"EXTERNAL_ACTION",
	"UNKNOWN",
]


def _require_text(value: str, name: str) -> None:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class EvidenceRecord:
	evidence_id: str
	source_identifier: str
	source_locator: str
	source_type: str
	collected_at: str
	source_version: str
	assertion_kind: AssertionKind
	confidence: Confidence
	confidence_reason: str
	summary: str
	details: dict[str, Any] = field(default_factory=dict)
	missing_evidence: tuple[str, ...] = ()
	conflicting_evidence: tuple[str, ...] = ()

	def __post_init__(self):
		for name in (
			"evidence_id",
			"source_identifier",
			"source_locator",
			"source_type",
			"collected_at",
			"source_version",
			"confidence_reason",
			"summary",
		):
			_require_text(getattr(self, name), name)

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "EvidenceRecord":
		return cls(
			**{
				**value,
				"missing_evidence": tuple(value.get("missing_evidence", [])),
				"conflicting_evidence": tuple(value.get("conflicting_evidence", [])),
			}
		)


@dataclass(frozen=True)
class ProcessStep:
	step_id: str
	name: str
	step_type: StepType
	actor: str
	inputs: tuple[str, ...]
	action: str
	outputs: tuple[str, ...]
	native_states: tuple[str, ...]
	evidence_ids: tuple[str, ...]
	assertion_kind: AssertionKind
	confidence: Confidence

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "ProcessStep":
		return cls(
			**{
				**value,
				"inputs": tuple(value.get("inputs", [])),
				"outputs": tuple(value.get("outputs", [])),
				"native_states": tuple(value.get("native_states", [])),
				"evidence_ids": tuple(value.get("evidence_ids", [])),
			}
		)


@dataclass(frozen=True)
class ProcessTransition:
	transition_id: str
	from_step_id: str
	to_step_id: str
	transition_type: str
	from_state: str | None
	to_state: str | None
	condition: str | None
	condition_support: str
	evidence_ids: tuple[str, ...]
	assertion_kind: AssertionKind
	confidence: Confidence

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "ProcessTransition":
		return cls(**{**value, "evidence_ids": tuple(value.get("evidence_ids", []))})


@dataclass(frozen=True)
class DecisionPoint:
	decision_id: str
	name: str
	owner: str
	inputs: tuple[str, ...]
	rules: tuple[str, ...]
	possible_outcomes: tuple[str, ...]
	risk_level: str
	evidence_ids: tuple[str, ...]
	assertion_kind: AssertionKind
	confidence: Confidence

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "DecisionPoint":
		return cls(
			**{
				**value,
				"inputs": tuple(value.get("inputs", [])),
				"rules": tuple(value.get("rules", [])),
				"possible_outcomes": tuple(value.get("possible_outcomes", [])),
				"evidence_ids": tuple(value.get("evidence_ids", [])),
			}
		)


@dataclass(frozen=True)
class ExceptionPath:
	exception_id: str
	name: str
	trigger: str
	detection: str
	resolution: str
	owner: str
	final_outcome: str
	evidence_ids: tuple[str, ...]
	assertion_kind: AssertionKind
	confidence: Confidence

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "ExceptionPath":
		return cls(**{**value, "evidence_ids": tuple(value.get("evidence_ids", []))})


@dataclass(frozen=True)
class ProcessGap:
	gap_id: str
	category: str
	description: str
	affected_elements: tuple[str, ...]
	evidence_ids: tuple[str, ...] = ()

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "ProcessGap":
		return cls(
			**{
				**value,
				"affected_elements": tuple(value.get("affected_elements", [])),
				"evidence_ids": tuple(value.get("evidence_ids", [])),
			}
		)


@dataclass(frozen=True)
class ProcessModel:
	process_id: str
	model_version: str
	name: str
	business_domain: str
	business_objective: str
	process_owner: str
	trigger: str
	trigger_source: str
	start_condition: str
	end_condition: str
	upstream_process: str
	downstream_process: str
	schema_snapshot_id: str
	schema_metadata_hash: str
	configuration_hash: str
	collected_at: str
	steps: tuple[ProcessStep, ...]
	transitions: tuple[ProcessTransition, ...]
	decisions: tuple[DecisionPoint, ...]
	exceptions: tuple[ExceptionPath, ...]
	evidence: tuple[EvidenceRecord, ...]
	gaps: tuple[ProcessGap, ...]
	metrics: dict[str, Any]

	def to_dict(self) -> dict[str, Any]:
		return {
			**{
				key: value
				for key, value in asdict(self).items()
				if key not in {"steps", "transitions", "decisions", "exceptions", "evidence", "gaps"}
			},
			"steps": [item.to_dict() for item in self.steps],
			"transitions": [item.to_dict() for item in self.transitions],
			"decisions": [item.to_dict() for item in self.decisions],
			"exceptions": [item.to_dict() for item in self.exceptions],
			"evidence": [item.to_dict() for item in self.evidence],
			"gaps": [item.to_dict() for item in self.gaps],
		}

	def deterministic_dict(self) -> dict[str, Any]:
		payload = self.to_dict()
		payload.pop("collected_at", None)
		payload.pop("schema_snapshot_id", None)
		for evidence in payload["evidence"]:
			evidence.pop("collected_at", None)
		return payload

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "ProcessModel":
		return cls(
			**{
				key: value[key]
				for key in (
					"process_id",
					"model_version",
					"name",
					"business_domain",
					"business_objective",
					"process_owner",
					"trigger",
					"trigger_source",
					"start_condition",
					"end_condition",
					"upstream_process",
					"downstream_process",
					"schema_snapshot_id",
					"schema_metadata_hash",
					"configuration_hash",
					"collected_at",
					"metrics",
				)
			},
			steps=tuple(ProcessStep.from_dict(item) for item in value.get("steps", [])),
			transitions=tuple(ProcessTransition.from_dict(item) for item in value.get("transitions", [])),
			decisions=tuple(DecisionPoint.from_dict(item) for item in value.get("decisions", [])),
			exceptions=tuple(ExceptionPath.from_dict(item) for item in value.get("exceptions", [])),
			evidence=tuple(EvidenceRecord.from_dict(item) for item in value.get("evidence", [])),
			gaps=tuple(ProcessGap.from_dict(item) for item in value.get("gaps", [])),
		)
