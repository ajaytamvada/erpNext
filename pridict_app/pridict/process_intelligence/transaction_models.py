from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


RECONSTRUCTION_VERSION = "1.0.0"


@dataclass(frozen=True)
class TransactionScope:
	company: str
	start_date: str
	end_date: str
	max_records_per_doctype: int = 5000

	def __post_init__(self):
		if not self.company.strip():
			raise ValueError("company is required")
		try:
			start_date = date.fromisoformat(self.start_date)
			end_date = date.fromisoformat(self.end_date)
		except (TypeError, ValueError) as error:
			raise ValueError("start_date and end_date must use YYYY-MM-DD") from error
		if start_date > end_date:
			raise ValueError("a valid inclusive date range is required")
		if not 1 <= self.max_records_per_doctype <= 5000:
			raise ValueError("max_records_per_doctype must be between 1 and 5000")


@dataclass(frozen=True)
class TransactionEvent:
	event_id: str
	event_type: str
	document_id: str
	document_type: str
	occurred_at: str | None
	observed_at: str
	timestamp_semantics: str
	actor_id: str | None
	details: dict[str, Any]
	evidence_ids: tuple[str, ...]
	confidence: str

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)


@dataclass(frozen=True)
class TransactionEvidence:
	evidence_id: str
	source_type: str
	source_locator: str
	observed_at: str
	summary: str
	details: dict[str, Any]

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)


@dataclass(frozen=True)
class CorrelationEdge:
	edge_id: str
	source_document_id: str
	target_document_id: str
	source_doctype: str
	target_doctype: str
	source_row_id: str | None
	target_row_id: str | None
	relation_type: str
	quantity: float | None
	allocated_amount: float | None
	allocation_status: str
	source_in_scope: bool
	target_in_scope: bool
	evidence_ids: tuple[str, ...]
	confidence: str

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)


@dataclass(frozen=True)
class ProcessInstance:
	instance_id: str
	document_ids: tuple[str, ...]
	event_ids: tuple[str, ...]
	edge_ids: tuple[str, ...]
	start_at: str | None
	end_at: str | None
	completion_status: str

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)


@dataclass(frozen=True)
class ReconstructionResult:
	reconstruction_id: str
	version: str
	process_model_id: str
	company_id: str
	start_date: str
	end_date: str
	collected_at: str
	evidence: tuple[TransactionEvidence, ...]
	events: tuple[TransactionEvent, ...]
	edges: tuple[CorrelationEdge, ...]
	instances: tuple[ProcessInstance, ...]
	metrics: dict[str, Any]
	gaps: tuple[str, ...]

	def to_dict(self) -> dict[str, Any]:
		return {
			**asdict(self),
			"evidence": [item.to_dict() for item in self.evidence],
			"events": [item.to_dict() for item in self.events],
			"edges": [item.to_dict() for item in self.edges],
			"instances": [item.to_dict() for item in self.instances],
		}

	def deterministic_dict(self) -> dict[str, Any]:
		payload = self.to_dict()
		payload.pop("collected_at", None)
		for event in payload["events"]:
			event.pop("observed_at", None)
		for evidence in payload["evidence"]:
			evidence.pop("observed_at", None)
		return payload

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "ReconstructionResult":
		return cls(
			reconstruction_id=value["reconstruction_id"],
			version=value["version"],
			process_model_id=value["process_model_id"],
			company_id=value["company_id"],
			start_date=value["start_date"],
			end_date=value["end_date"],
			collected_at=value["collected_at"],
			evidence=tuple(TransactionEvidence(**item) for item in value.get("evidence", [])),
			events=tuple(
				TransactionEvent(**{**item, "evidence_ids": tuple(item["evidence_ids"])})
				for item in value.get("events", [])
			),
			edges=tuple(
				CorrelationEdge(**{**item, "evidence_ids": tuple(item["evidence_ids"])})
				for item in value.get("edges", [])
			),
			instances=tuple(
				ProcessInstance(
					**{
						**item,
						"document_ids": tuple(item["document_ids"]),
						"event_ids": tuple(item["event_ids"]),
						"edge_ids": tuple(item["edge_ids"]),
					}
				)
				for item in value.get("instances", [])
			),
			metrics=value.get("metrics", {}),
			gaps=tuple(value.get("gaps", [])),
		)
