"""Data models and serialization for Decision Intelligence."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class DecisionStatus(str, Enum):
	COMPLIANT = "COMPLIANT"
	WARNING = "WARNING"
	BREACH = "BREACH"


class AnomalySeverity(str, Enum):
	HIGH = "HIGH"
	MEDIUM = "MEDIUM"
	LOW = "LOW"


class VendorTier(str, Enum):
	PREFERRED = "PREFERRED"
	STANDARD = "STANDARD"
	WATCHLIST = "WATCHLIST"
	HIGH_RISK = "HIGH_RISK"


class RecommendationPriority(str, Enum):
	CRITICAL = "CRITICAL"
	HIGH = "HIGH"
	MEDIUM = "MEDIUM"
	LOW = "LOW"


@dataclass(frozen=True)
class DecisionRule:
	rule_id: str
	name: str
	category: str
	description: str
	default_threshold: float = 0.0
	severity: AnomalySeverity = AnomalySeverity.MEDIUM

	def to_dict(self) -> dict[str, Any]:
		data = asdict(self)
		data["severity"] = self.severity.value
		return data


@dataclass(frozen=True)
class RuleEvaluationResult:
	rule_id: str
	rule_name: str
	status: DecisionStatus
	message: str
	threshold_value: float = 0.0
	actual_value: float = 0.0

	def to_dict(self) -> dict[str, Any]:
		data = asdict(self)
		data["status"] = self.status.value
		return data


@dataclass(frozen=True)
class EvaluatedDecision:
	doc_type: str
	doc_name: str
	creation: str
	company: str
	total_amount: float
	currency: str
	owner: str
	status: DecisionStatus
	evaluations: tuple[RuleEvaluationResult, ...]
	approver: str = ""
	workflow_state: str = ""
	risk_score: float = 0.0
	doc_url: str = ""

	def to_dict(self) -> dict[str, Any]:
		return {
			"doc_type": self.doc_type,
			"doc_name": self.doc_name,
			"creation": self.creation,
			"company": self.company,
			"total_amount": round(self.total_amount, 2),
			"currency": self.currency,
			"owner": self.owner,
			"status": self.status.value,
			"evaluations": [item.to_dict() for item in self.evaluations],
			"approver": self.approver,
			"workflow_state": self.workflow_state,
			"risk_score": round(self.risk_score, 1),
			"doc_url": self.doc_url,
		}


@dataclass(frozen=True)
class AnomalyFinding:
	anomaly_id: str
	anomaly_type: str
	severity: AnomalySeverity
	title: str
	description: str
	doc_type: str
	doc_name: str
	party_name: str = ""
	item_code: str = ""
	amount: float = 0.0
	variance_percent: float = 0.0
	potential_impact: float = 0.0
	doc_url: str = ""

	def to_dict(self) -> dict[str, Any]:
		return {
			"anomaly_id": self.anomaly_id,
			"anomaly_type": self.anomaly_type,
			"severity": self.severity.value,
			"title": self.title,
			"description": self.description,
			"doc_type": self.doc_type,
			"doc_name": self.doc_name,
			"party_name": self.party_name,
			"item_code": self.item_code,
			"amount": round(self.amount, 2),
			"variance_percent": round(self.variance_percent, 2),
			"potential_impact": round(self.potential_impact, 2),
			"doc_url": self.doc_url,
		}


@dataclass(frozen=True)
class VendorScore:
	vendor_id: str
	vendor_name: str
	total_spend: float
	order_count: int
	on_time_delivery_rate: float
	quality_acceptance_rate: float
	price_variance_rate: float
	overall_score: float
	tier: VendorTier
	key_strengths: tuple[str, ...] = ()
	risk_flags: tuple[str, ...] = ()

	def to_dict(self) -> dict[str, Any]:
		return {
			"vendor_id": self.vendor_id,
			"vendor_name": self.vendor_name,
			"total_spend": round(self.total_spend, 2),
			"order_count": self.order_count,
			"on_time_delivery_rate": round(self.on_time_delivery_rate, 1),
			"quality_acceptance_rate": round(self.quality_acceptance_rate, 1),
			"price_variance_rate": round(self.price_variance_rate, 1),
			"overall_score": round(self.overall_score, 1),
			"tier": self.tier.value,
			"key_strengths": list(self.key_strengths),
			"risk_flags": list(self.risk_flags),
		}


@dataclass(frozen=True)
class Recommendation:
	rec_id: str
	title: str
	category: str
	priority: RecommendationPriority
	description: str
	suggested_action: str
	target_doctype: str = ""
	target_docname: str = ""
	estimated_saving: float = 0.0
	doc_url: str = ""

	def to_dict(self) -> dict[str, Any]:
		return {
			"rec_id": self.rec_id,
			"title": self.title,
			"category": self.category,
			"priority": self.priority.value,
			"description": self.description,
			"suggested_action": self.suggested_action,
			"target_doctype": self.target_doctype,
			"target_docname": self.target_docname,
			"estimated_saving": round(self.estimated_saving, 2),
			"doc_url": self.doc_url,
		}


@dataclass(frozen=True)
class DecisionIntelligenceSummary:
	total_decisions_evaluated: int
	compliant_count: int
	warning_count: int
	breach_count: int
	compliance_rate_pct: float
	total_spend_evaluated: float
	total_spend_at_risk: float
	total_anomalies_count: int
	active_recommendations_count: int
	potential_savings_total: float

	def to_dict(self) -> dict[str, Any]:
		return {
			"total_decisions_evaluated": self.total_decisions_evaluated,
			"compliant_count": self.compliant_count,
			"warning_count": self.warning_count,
			"breach_count": self.breach_count,
			"compliance_rate_pct": round(self.compliance_rate_pct, 1),
			"total_spend_evaluated": round(self.total_spend_evaluated, 2),
			"total_spend_at_risk": round(self.total_spend_at_risk, 2),
			"total_anomalies_count": self.total_anomalies_count,
			"active_recommendations_count": self.active_recommendations_count,
			"potential_savings_total": round(self.potential_savings_total, 2),
		}


@dataclass(frozen=True)
class DecisionIntelligenceResult:
	summary: DecisionIntelligenceSummary
	evaluated_decisions: tuple[EvaluatedDecision, ...]
	anomalies: tuple[AnomalyFinding, ...]
	vendor_scores: tuple[VendorScore, ...]
	recommendations: tuple[Recommendation, ...]
	scope: dict[str, Any] = field(default_factory=dict)
	generated_at: str = ""

	def to_dict(self) -> dict[str, Any]:
		return {
			"summary": self.summary.to_dict(),
			"evaluated_decisions": [item.to_dict() for item in self.evaluated_decisions],
			"anomalies": [item.to_dict() for item in self.anomalies],
			"vendor_scores": [item.to_dict() for item in self.vendor_scores],
			"recommendations": [item.to_dict() for item in self.recommendations],
			"scope": self.scope,
			"generated_at": self.generated_at,
		}
