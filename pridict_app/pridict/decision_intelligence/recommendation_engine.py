"""Prescriptive recommendation and next-best-action generator for procurement decisions."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pridict.decision_intelligence.models import (
	AnomalyFinding,
	AnomalySeverity,
	EvaluatedDecision,
	Recommendation,
	RecommendationPriority,
	VendorScore,
	VendorTier,
)


def generate_recommendations(
	decisions: list[EvaluatedDecision],
	anomalies: list[AnomalyFinding],
	vendor_scores: list[VendorScore],
) -> list[Recommendation]:
	"""Synthesizes evaluated rules, detected anomalies, and vendor scores into prioritized,

	actionable next-best actions.
	"""
	recommendations: list[Recommendation] = []
	rec_counter = 1

	# 1. Price Anomaly Recommendations
	price_anomalies = [a for a in anomalies if a.anomaly_type == "PRICE_VARIANCE_OUTLIER"]
	if price_anomalies:
		# Group by item_code
		for anom in price_anomalies[:3]:
			priority = (
				RecommendationPriority.CRITICAL if anom.severity == AnomalySeverity.HIGH
				else RecommendationPriority.HIGH
			)
			recommendations.append(
				Recommendation(
					rec_id=f"REC-{rec_counter:03d}",
					title=f"Renegotiate Rate for {anom.item_code} on {anom.doc_name}",
					category="COST_OPTIMIZATION",
					priority=priority,
					description=(
						f"Detected {anom.variance_percent:.1f}% unit rate variance on {anom.doc_name} for vendor {anom.party_name}. "
						f"Potential cost reduction: {anom.potential_impact:,.2f}."
					),
					suggested_action="Benchmark against latest supplier quotations and request revised quotation from vendor.",
					target_doctype=anom.doc_type,
					target_docname=anom.doc_name,
					estimated_saving=anom.potential_impact,
					doc_url=anom.doc_url,
				)
			)
			rec_counter += 1

	# 2. Split PO Circumvention Recommendations
	split_anomalies = [a for a in anomalies if a.anomaly_type == "SPLIT_PURCHASE_CIRCUMVENTION"]
	for split in split_anomalies[:2]:
		recommendations.append(
			Recommendation(
				rec_id=f"REC-{rec_counter:03d}",
				title=f"Consolidate Split POs for {split.party_name}",
				category="APPROVAL_COMPLIANCE",
				priority=RecommendationPriority.CRITICAL,
				description=(
					f"Orders {split.doc_name} aggregate to {split.amount:,.2f}, circumventing single-order authorization tiers. "
					"Consolidation enforces executive review and unlocks volume bargaining."
				),
				suggested_action="Consolidate orders into a single requisition and route through standard L3 Executive approval.",
				target_doctype="Purchase Order",
				target_docname=split.doc_name.split(",")[0].strip(),
				estimated_saving=split.amount * 0.05,  # 5% estimated volume consolidation savings
				doc_url=split.doc_url,
			)
		)
		rec_counter += 1

	# 3. Maverick Spend Control
	maverick_anomalies = [a for a in anomalies if a.anomaly_type == "MAVERICK_UNLINKED_SPEND"]
	if maverick_anomalies:
		total_maverick = sum(m.amount for m in maverick_anomalies)
		first_m = maverick_anomalies[0]
		recommendations.append(
			Recommendation(
				rec_id=f"REC-{rec_counter:03d}",
				title="Enforce Requisition & Sourcing Gate for Direct POs",
				category="SOURCING_GOVERNANCE",
				priority=RecommendationPriority.HIGH,
				description=(
					f"Identified {len(maverick_anomalies)} direct POs totaling {total_maverick:,.2f} without prior "
					"Material Request (PR) or quotation competition."
				),
				suggested_action="Activate Buying Settings requirement for mandatory Supplier Quotation or PR on orders above threshold.",
				target_doctype=first_m.doc_type,
				target_docname=first_m.doc_name,
				estimated_saving=total_maverick * 0.08,
				doc_url=first_m.doc_url,
			)
		)
		rec_counter += 1

	# 4. Supplier Risk & Sourcing Diversification
	high_risk_vendors = [v for v in vendor_scores if v.tier in (VendorTier.WATCHLIST, VendorTier.HIGH_RISK)]
	for v in high_risk_vendors[:2]:
		recommendations.append(
			Recommendation(
				rec_id=f"REC-{rec_counter:03d}",
				title=f"Diversify Sourcing for Vendor {v.vendor_name}",
				category="SUPPLIER_RISK",
				priority=RecommendationPriority.MEDIUM,
				description=(
					f"Vendor {v.vendor_name} is on {v.tier.value} with overall decision score {v.overall_score:.1f}/100. "
					f"Risk factors: {', '.join(v.risk_flags) or 'Performance inconsistency'}."
				),
				suggested_action="Issue Request for Quotation (RFQ) to alternate approved vendors to establish backup suppliers.",
				target_doctype="Supplier",
				target_docname=v.vendor_name,
				estimated_saving=0.0,
				doc_url=f"/app/supplier/{quote(v.vendor_name, safe='')}",
			)
		)
		rec_counter += 1

	# 5. Preferred Supplier Volume Consolidation
	preferred_vendors = [v for v in vendor_scores if v.tier == VendorTier.PREFERRED and v.order_count >= 3]
	if preferred_vendors:
		top_vendor = preferred_vendors[0]
		recommendations.append(
			Recommendation(
				rec_id=f"REC-{rec_counter:03d}",
				title=f"Establish Annual Rate Contract with {top_vendor.vendor_name}",
				category="COMMERCIAL_OPTIMIZATION",
				priority=RecommendationPriority.LOW,
				description=(
					f"Vendor {top_vendor.vendor_name} achieved {top_vendor.overall_score:.1f}/100 with "
					f"{top_vendor.on_time_delivery_rate:.1f}% punctuality across {top_vendor.order_count} orders."
				),
				suggested_action="Negotiate a long-term Blanket Order or annual rate contract for an estimated 3-5% rebate.",
				target_doctype="Supplier",
				target_docname=top_vendor.vendor_name,
				estimated_saving=top_vendor.total_spend * 0.04,
				doc_url=f"/app/supplier/{quote(top_vendor.vendor_name, safe='')}",
			)
		)

	return recommendations
