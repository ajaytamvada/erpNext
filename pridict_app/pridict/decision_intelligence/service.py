"""Core service orchestrating Decision Intelligence evaluations."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

try:
	import frappe
	from frappe import _
except ImportError:
	frappe = None
	def _(text):
		return text

from pridict.decision_intelligence.anomaly_detector import (
	detect_maverick_orders,
	detect_price_variances,
	detect_split_purchases,
)
from pridict.decision_intelligence.models import (
	DecisionIntelligenceResult,
	DecisionIntelligenceSummary,
	DecisionStatus,
	EvaluatedDecision,
)
from pridict.decision_intelligence.recommendation_engine import generate_recommendations
from pridict.decision_intelligence.rules import (
	evaluate_approval_tier,
	evaluate_cost_center,
	evaluate_maverick_spend,
)
from pridict.decision_intelligence.vendor_scoring import calculate_vendor_scores


def evaluate_decisions(
	company: str,
	start_date: str,
	end_date: str,
	limit: int = 500,
	dataset: dict[str, list[dict[str, Any]]] | None = None,
) -> DecisionIntelligenceResult:
	"""Evaluates procurement decisions, rules, anomalies, vendor scores, and recommendations

	for the specified scope. Accepts an optional in-memory dataset for testing without database dependencies.
	"""
	if dataset is not None:
		po_rows = dataset.get("Purchase Order", [])
		po_items = dataset.get("Purchase Order Item", [])
		pr_rows = dataset.get("Purchase Receipt", [])
		pr_items = dataset.get("Purchase Receipt Item", [])
	else:
		po_filters = {"company": company}
		if start_date and end_date:
			po_filters["transaction_date"] = ["between", [start_date, end_date]]

		po_rows = [
			dict(r)
			for r in frappe.get_list(
				"Purchase Order",
				filters=po_filters,
				fields=["name", "company", "supplier", "grand_total", "total", "docstatus", "status", "owner", "transaction_date", "schedule_date", "creation", "currency"],
				order_by="transaction_date desc, creation desc",
				limit_page_length=limit,
			)
		]
		po_names = [r["name"] for r in po_rows]

		po_items = (
			[
				dict(r)
				for r in frappe.get_list(
					"Purchase Order Item",
					filters={"parent": ["in", po_names]},
					fields=["name", "parent", "item_code", "item_name", "qty", "rate", "amount", "material_request", "supplier_quotation", "cost_center", "project"],
					limit_page_length=0,
				)
			]
			if po_names
			else []
		)

		pr_rows = [
			dict(r)
			for r in frappe.get_list(
				"Purchase Receipt",
				filters=po_filters,
				fields=["name", "company", "supplier", "grand_total", "docstatus", "status", "posting_date", "creation"],
				limit_page_length=limit,
			)
		]
		pr_names = [r["name"] for r in pr_rows]

		pr_items = (
			[
				dict(r)
				for r in frappe.get_list(
					"Purchase Receipt Item",
					filters={"parent": ["in", pr_names]},
					fields=["name", "parent", "item_code", "qty", "received_qty", "rejected_qty", "purchase_order"],
					limit_page_length=0,
				)
			]
			if pr_names
			else []
		)

	# Group items by PO
	items_by_po: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for item in po_items:
		items_by_po[str(item.get("parent") or "")].append(item)

	evaluated_decisions: list[EvaluatedDecision] = []
	compliant_count = 0
	warning_count = 0
	breach_count = 0
	spend_evaluated = 0.0
	spend_at_risk = 0.0

	for po in po_rows:
		name = str(po.get("name") or "")
		items = items_by_po.get(name, [])
		amount = float(po.get("grand_total") or po.get("total") or 0.0)
		spend_evaluated += amount

		# Evaluate rules
		eval1 = evaluate_approval_tier(po)
		eval2 = evaluate_maverick_spend(po, items)
		eval3 = evaluate_cost_center(po, items)
		all_evals = (eval1, eval2, eval3)

		# Determine composite status
		statuses = [e.status for e in all_evals]
		if DecisionStatus.BREACH in statuses:
			status = DecisionStatus.BREACH
			breach_count += 1
			spend_at_risk += amount
			risk_score = 85.0
		elif DecisionStatus.WARNING in statuses:
			status = DecisionStatus.WARNING
			warning_count += 1
			spend_at_risk += amount * 0.25
			risk_score = 45.0
		else:
			status = DecisionStatus.COMPLIANT
			compliant_count += 1
			risk_score = 5.0

		evaluated_decisions.append(
			EvaluatedDecision(
				doc_type="Purchase Order",
				doc_name=name,
				creation=str(po.get("transaction_date") or po.get("creation") or "")[:10],
				company=str(po.get("company") or company),
				total_amount=amount,
				currency=str(po.get("currency") or "INR"),
				owner=str(po.get("owner") or ""),
				status=status,
				evaluations=all_evals,
				approver=str(po.get("owner") or "Purchase Manager"),
				workflow_state=str(po.get("status") or ""),
				risk_score=risk_score,
				doc_url=f"/app/purchase-order/{quote(name, safe='')}",
			)
		)

	# Run Anomaly Detection
	anomalies = []
	anomalies.extend(detect_price_variances(po_rows, po_items))
	anomalies.extend(detect_split_purchases(po_rows))
	anomalies.extend(detect_maverick_orders(po_rows, po_items))

	# Run Vendor Scoring
	vendor_scores = calculate_vendor_scores(po_rows, po_items, pr_rows, pr_items)

	# Run Recommendation Engine
	recommendations = generate_recommendations(evaluated_decisions, anomalies, vendor_scores)

	# Aggregate Summary
	total_eval = len(evaluated_decisions)
	compliance_rate = (compliant_count / max(total_eval, 1)) * 100.0 if total_eval > 0 else 100.0
	potential_savings = sum(r.estimated_saving for r in recommendations)

	summary = DecisionIntelligenceSummary(
		total_decisions_evaluated=total_eval,
		compliant_count=compliant_count,
		warning_count=warning_count,
		breach_count=breach_count,
		compliance_rate_pct=compliance_rate,
		total_spend_evaluated=spend_evaluated,
		total_spend_at_risk=spend_at_risk,
		total_anomalies_count=len(anomalies),
		active_recommendations_count=len(recommendations),
		potential_savings_total=potential_savings,
	)

	return DecisionIntelligenceResult(
		summary=summary,
		evaluated_decisions=tuple(evaluated_decisions),
		anomalies=tuple(anomalies),
		vendor_scores=tuple(vendor_scores),
		recommendations=tuple(recommendations),
		scope={
			"company": company,
			"start_date": start_date,
			"end_date": end_date,
			"limit": limit,
		},
		generated_at=datetime.now(timezone.utc).isoformat(),
	)
