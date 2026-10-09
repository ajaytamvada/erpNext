"""Procurement decision rules and evaluation logic."""
from __future__ import annotations

from typing import Any

from pridict.decision_intelligence.models import (
	AnomalySeverity,
	DecisionRule,
	DecisionStatus,
	RuleEvaluationResult,
)

# Standard predefined rule definitions
DEFAULT_RULES = (
	DecisionRule(
		rule_id="RULE-AUTH-TIER",
		name="Multi-Tier Approval Authorization",
		category="APPROVAL_GOVERNANCE",
		description="Enforces approval authority tiers based on order monetary value (L1 < 50k, L2 50k-150k, L3 > 150k).",
		default_threshold=150000.0,
		severity=AnomalySeverity.HIGH,
	),
	DecisionRule(
		rule_id="RULE-PRICE-VAR",
		name="Price Variance Tolerance",
		category="PRICE_INTELLIGENCE",
		description="Flags item unit prices exceeding historical benchmarks or linked quotations by more than 5%.",
		default_threshold=5.0,
		severity=AnomalySeverity.MEDIUM,
	),
	DecisionRule(
		rule_id="RULE-MAVERICK-SPEND",
		name="Direct PO Maverick Spend Check",
		category="SOURCING_COMPLIANCE",
		description="Identifies purchase orders raised directly without upstream requisition (PR) or quotation competition.",
		default_threshold=0.0,
		severity=AnomalySeverity.MEDIUM,
	),
	DecisionRule(
		rule_id="RULE-SPLIT-PO",
		name="Split Purchase Circumvention Detection",
		category="FRAUD_PREVENTION",
		description="Flags multiple purchase orders to the same vendor within 48h that aggregate above approval thresholds.",
		default_threshold=150000.0,
		severity=AnomalySeverity.HIGH,
	),
	DecisionRule(
		rule_id="RULE-COST-CENTER",
		name="Cost Center & Budget Attribution",
		category="BUDGET_COMPLIANCE",
		description="Ensures all non-trivial procurement transactions have defined cost center accountability.",
		default_threshold=25000.0,
		severity=AnomalySeverity.LOW,
	),
	DecisionRule(
		rule_id="RULE-LEAD-TIME",
		name="Unrealistic Delivery Lead Time",
		category="OPERATIONAL_FEASIBILITY",
		description="Flags purchase orders where scheduled delivery is prior to or same-day as creation without expediting rationale.",
		default_threshold=1.0,
		severity=AnomalySeverity.LOW,
	),
)


def evaluate_approval_tier(doc: dict[str, Any], roles: set[str] | None = None) -> RuleEvaluationResult:
	"""Evaluates if the document's total amount corresponds to the required authorization tier."""
	amount = float(doc.get("grand_total") or doc.get("total") or 0.0)
	docstatus = int(doc.get("docstatus") or 0)
	user_roles = set(roles or set())

	# Document is submitted (docstatus=1) or approved
	if amount > 150000.0:
		required_tier = "L3 (Director / Executive)"
		has_role = bool(user_roles.intersection({"System Manager", "Director", "Managing Director"}))
		if docstatus == 1 and not has_role and user_roles:
			return RuleEvaluationResult(
				rule_id="RULE-AUTH-TIER",
				rule_name="Multi-Tier Approval Authorization",
				status=DecisionStatus.BREACH,
				message=f"Order value {amount:,.2f} exceeds 150,000 threshold and requires {required_tier} approval.",
				threshold_value=150000.0,
				actual_value=amount,
			)
		elif amount > 500000.0:
			return RuleEvaluationResult(
				rule_id="RULE-AUTH-TIER",
				rule_name="Multi-Tier Approval Authorization",
				status=DecisionStatus.WARNING,
				message=f"High-value procurement ({amount:,.2f}) pending board/executive review verification.",
				threshold_value=150000.0,
				actual_value=amount,
			)
	elif amount > 50000.0:
		required_tier = "L2 (Accounts / Finance Manager)"
		# Passed L1 tier, within L2
		return RuleEvaluationResult(
			rule_id="RULE-AUTH-TIER",
			rule_name="Multi-Tier Approval Authorization",
			status=DecisionStatus.COMPLIANT,
			message=f"Order value {amount:,.2f} evaluated under {required_tier}.",
			threshold_value=50000.0,
			actual_value=amount,
		)

	return RuleEvaluationResult(
		rule_id="RULE-AUTH-TIER",
		rule_name="Multi-Tier Approval Authorization",
		status=DecisionStatus.COMPLIANT,
		message=f"Order value {amount:,.2f} within standard operational approval limit (L1).",
		threshold_value=50000.0,
		actual_value=amount,
	)


def evaluate_maverick_spend(doc: dict[str, Any], items: list[dict[str, Any]]) -> RuleEvaluationResult:
	"""Checks whether a Purchase Order was raised with or without upstream sourcing references."""
	if not items:
		return RuleEvaluationResult(
			rule_id="RULE-MAVERICK-SPEND",
			rule_name="Direct PO Maverick Spend Check",
			status=DecisionStatus.COMPLIANT,
			message="No items found for evaluation.",
		)

	has_pr = any(bool(item.get("material_request") or item.get("material_request_item")) for item in items)
	has_sq = any(bool(item.get("supplier_quotation") or item.get("supplier_quotation_item")) for item in items)
	amount = float(doc.get("grand_total") or 0.0)

	if not has_pr and not has_sq:
		status = DecisionStatus.BREACH if amount > 100000.0 else DecisionStatus.WARNING
		return RuleEvaluationResult(
			rule_id="RULE-MAVERICK-SPEND",
			rule_name="Direct PO Maverick Spend Check",
			status=status,
			message=f"Direct purchase of {amount:,.2f} bypassed Material Requisition (PR) and Supplier Quotation competition.",
			threshold_value=0.0,
			actual_value=amount,
		)

	return RuleEvaluationResult(
		rule_id="RULE-MAVERICK-SPEND",
		rule_name="Direct PO Maverick Spend Check",
		status=DecisionStatus.COMPLIANT,
		message="Sourcing compliance verified: upstream PR/Quotation references present.",
		threshold_value=0.0,
		actual_value=amount,
	)


def evaluate_cost_center(doc: dict[str, Any], items: list[dict[str, Any]]) -> RuleEvaluationResult:
	"""Ensures cost center accountability on purchase transactions above threshold."""
	amount = float(doc.get("grand_total") or 0.0)
	threshold = 25000.0

	if amount < threshold:
		return RuleEvaluationResult(
			rule_id="RULE-COST-CENTER",
			rule_name="Cost Center & Budget Attribution",
			status=DecisionStatus.COMPLIANT,
			message=f"Amount ({amount:,.2f}) is below cost center audit threshold ({threshold:,.2f}).",
			threshold_value=threshold,
			actual_value=amount,
		)

	has_doc_cc = bool(doc.get("cost_center") or doc.get("project"))
	has_item_cc = all(bool(item.get("cost_center") or item.get("project")) for item in items) if items else False

	if not has_doc_cc and not has_item_cc:
		return RuleEvaluationResult(
			rule_id="RULE-COST-CENTER",
			rule_name="Cost Center & Budget Attribution",
			status=DecisionStatus.WARNING,
			message=f"Transaction value {amount:,.2f} lacks cost center or project attribution for budget tracking.",
			threshold_value=threshold,
			actual_value=amount,
		)

	return RuleEvaluationResult(
		rule_id="RULE-COST-CENTER",
		rule_name="Cost Center & Budget Attribution",
		status=DecisionStatus.COMPLIANT,
		message="Cost center / project attribution confirmed.",
		threshold_value=threshold,
		actual_value=amount,
	)
