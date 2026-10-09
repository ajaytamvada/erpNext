"""Unit test suite for Decision Intelligence."""
from __future__ import annotations

import unittest

from pridict.decision_intelligence.anomaly_detector import (
	detect_maverick_orders,
	detect_price_variances,
	detect_split_purchases,
)
from pridict.decision_intelligence.models import (
	AnomalySeverity,
	DecisionStatus,
	VendorTier,
)
from pridict.decision_intelligence.recommendation_engine import generate_recommendations
from pridict.decision_intelligence.rules import (
	DEFAULT_RULES,
	evaluate_approval_tier,
	evaluate_cost_center,
	evaluate_maverick_spend,
)
from pridict.decision_intelligence.service import evaluate_decisions
from pridict.decision_intelligence.vendor_scoring import calculate_vendor_scores


class TestDecisionIntelligence(unittest.TestCase):

	def test_default_rules_structure(self):
		self.assertGreaterEqual(len(DEFAULT_RULES), 5)
		rule_ids = [r.rule_id for r in DEFAULT_RULES]
		self.assertEqual(len(rule_ids), len(set(rule_ids)))
		self.assertIn("RULE-AUTH-TIER", rule_ids)
		self.assertIn("RULE-MAVERICK-SPEND", rule_ids)
		self.assertIn("RULE-SPLIT-PO", rule_ids)

	def test_evaluate_approval_tier(self):
		# Small order <= 50,000 -> L1 Compliant
		po_small = {"grand_total": 25000.0, "docstatus": 1}
		res_small = evaluate_approval_tier(po_small, roles={"Purchase User"})
		self.assertEqual(res_small.status, DecisionStatus.COMPLIANT)

		# Medium order 50k - 150k -> L2 Compliant
		po_med = {"grand_total": 85000.0, "docstatus": 1}
		res_med = evaluate_approval_tier(po_med, roles={"Purchase Manager"})
		self.assertEqual(res_med.status, DecisionStatus.COMPLIANT)

		# Large order > 150k submitted without Director role -> Breach
		po_large = {"grand_total": 240000.0, "docstatus": 1}
		res_large = evaluate_approval_tier(po_large, roles={"Purchase User"})
		self.assertEqual(res_large.status, DecisionStatus.BREACH)
		self.assertGreaterEqual(res_large.actual_value, 240000.0)

	def test_evaluate_maverick_spend(self):
		# PO with upstream Material Request -> Compliant
		po = {"grand_total": 120000.0}
		items_compliant = [{"item_code": "LAPTOP", "material_request": "MR-001"}]
		res_comp = evaluate_maverick_spend(po, items_compliant)
		self.assertEqual(res_comp.status, DecisionStatus.COMPLIANT)

		# Direct PO without upstream sourcing -> Breach/Warning
		items_maverick = [{"item_code": "LAPTOP", "qty": 5, "rate": 24000.0}]
		res_mav = evaluate_maverick_spend(po, items_maverick)
		self.assertEqual(res_mav.status, DecisionStatus.BREACH)
		self.assertIn("bypassed", res_mav.message.lower())

	def test_evaluate_cost_center(self):
		# PO below 25,000 -> automatically compliant
		po_low = {"grand_total": 10000.0}
		self.assertEqual(evaluate_cost_center(po_low, []).status, DecisionStatus.COMPLIANT)

		# High value PO without cost center -> Warning
		po_high = {"grand_total": 80000.0}
		items_high = [{"item_code": "IT-EQUIP", "rate": 80000.0}]
		self.assertEqual(evaluate_cost_center(po_high, items_high).status, DecisionStatus.WARNING)

		# High value PO with cost center -> Compliant
		po_high_with_cc = {"grand_total": 80000.0, "cost_center": "Main - TC"}
		self.assertEqual(evaluate_cost_center(po_high_with_cc, items_high).status, DecisionStatus.COMPLIANT)

	def test_detect_price_variances(self):
		po_rows = [
			{"name": "PO-001", "supplier": "Supplier A"},
			{"name": "PO-002", "supplier": "Supplier B"},
		]
		po_items = [
			{"name": "POI-1", "parent": "PO-001", "item_code": "STEEL-ROD", "rate": 100.0, "qty": 50},
			{"name": "POI-2", "parent": "PO-002", "item_code": "STEEL-ROD", "rate": 135.0, "qty": 100},
		]
		# Explicit benchmark: 100.0
		anomalies = detect_price_variances(po_rows, po_items, historical_item_rates={"STEEL-ROD": 100.0})
		self.assertEqual(len(anomalies), 1)
		anom = anomalies[0]
		self.assertEqual(anom.item_code, "STEEL-ROD")
		self.assertEqual(anom.doc_name, "PO-002")
		self.assertAlmostEqual(anom.variance_percent, 35.0)
		self.assertAlmostEqual(anom.potential_impact, 3500.0)  # (135 - 100) * 100
		self.assertEqual(anom.severity, AnomalySeverity.HIGH)

	def test_detect_split_purchases(self):
		po_rows = [
			{
				"name": "PO-101",
				"supplier": "Vendor FastTech",
				"grand_total": 95000.0,
				"transaction_date": "2026-10-01",
			},
			{
				"name": "PO-102",
				"supplier": "Vendor FastTech",
				"grand_total": 80000.0,
				"transaction_date": "2026-10-02",
			},
		]
		anomalies = detect_split_purchases(po_rows)
		self.assertEqual(len(anomalies), 1)
		anom = anomalies[0]
		self.assertEqual(anom.anomaly_type, "SPLIT_PURCHASE_CIRCUMVENTION")
		self.assertEqual(anom.party_name, "Vendor FastTech")
		self.assertAlmostEqual(anom.amount, 175000.0)

	def test_calculate_vendor_scores(self):
		po_rows = [
			{"name": "PO-A1", "supplier": "Vendor Prime", "grand_total": 200000.0, "schedule_date": "2026-10-05"},
			{"name": "PO-A2", "supplier": "Vendor Prime", "grand_total": 150000.0, "schedule_date": "2026-10-10"},
		]
		po_items = [
			{"name": "POI-1", "parent": "PO-A1", "item_code": "ITEM-1", "qty": 100, "rate": 2000.0},
		]
		pr_rows = [
			{"name": "PR-01", "supplier": "Vendor Prime", "posting_date": "2026-10-04"},  # on-time
			{"name": "PR-02", "supplier": "Vendor Prime", "posting_date": "2026-10-09"},  # on-time
		]
		pr_items = [
			{"name": "PRI-1", "parent": "PR-01", "received_qty": 100, "rejected_qty": 0, "purchase_order": "PO-A1"},
			{"name": "PRI-2", "parent": "PR-02", "received_qty": 100, "rejected_qty": 2, "purchase_order": "PO-A2"},
		]
		scores = calculate_vendor_scores(po_rows, po_items, pr_rows, pr_items)
		self.assertEqual(len(scores), 1)
		v = scores[0]
		self.assertEqual(v.vendor_name, "Vendor Prime")
		self.assertAlmostEqual(v.total_spend, 350000.0)
		self.assertEqual(v.order_count, 2)
		self.assertAlmostEqual(v.on_time_delivery_rate, 100.0)
		self.assertGreaterEqual(v.overall_score, 85.0)
		self.assertEqual(v.tier, VendorTier.PREFERRED)

	def test_evaluate_decisions_service_e2e(self):
		dataset = {
			"Purchase Order": [
				{
					"name": "PO-2026-001",
					"company": "Test Enterprise",
					"supplier": "Acme Industrial",
					"grand_total": 180000.0,
					"docstatus": 1,
					"status": "Submitted",
					"owner": "buyer@test.com",
					"transaction_date": "2026-10-01",
					"schedule_date": "2026-10-08",
					"currency": "INR",
				},
				{
					"name": "PO-2026-002",
					"company": "Test Enterprise",
					"supplier": "Acme Industrial",
					"grand_total": 45000.0,
					"docstatus": 1,
					"status": "Submitted",
					"owner": "buyer@test.com",
					"transaction_date": "2026-10-03",
					"schedule_date": "2026-10-06",
					"currency": "INR",
				},
			],
			"Purchase Order Item": [
				{
					"name": "POI-1",
					"parent": "PO-2026-001",
					"item_code": "MOTOR-01",
					"qty": 10,
					"rate": 18000.0,
					"cost_center": "Plant 1",
				},
				{
					"name": "POI-2",
					"parent": "PO-2026-002",
					"item_code": "VALVE-02",
					"qty": 5,
					"rate": 9000.0,
					"material_request": "MR-0099",
					"cost_center": "Plant 1",
				},
			],
			"Purchase Receipt": [
				{
					"name": "PR-2026-001",
					"company": "Test Enterprise",
					"supplier": "Acme Industrial",
					"grand_total": 180000.0,
					"posting_date": "2026-10-07",
				}
			],
			"Purchase Receipt Item": [
				{
					"name": "PRI-1",
					"parent": "PR-2026-001",
					"item_code": "MOTOR-01",
					"qty": 10,
					"received_qty": 10,
					"rejected_qty": 0,
					"purchase_order": "PO-2026-001",
				}
			],
		}

		result = evaluate_decisions(
			company="Test Enterprise",
			start_date="2026-10-01",
			end_date="2026-10-09",
			dataset=dataset,
		)

		self.assertEqual(result.summary.total_decisions_evaluated, 2)
		self.assertAlmostEqual(result.summary.total_spend_evaluated, 225000.0)
		self.assertGreaterEqual(len(result.vendor_scores), 1)
		self.assertGreaterEqual(len(result.recommendations), 1)

		# Verify serialization
		res_dict = result.to_dict()
		self.assertIn("summary", res_dict)
		self.assertIn("evaluated_decisions", res_dict)
		self.assertIn("anomalies", res_dict)
		self.assertIn("vendor_scores", res_dict)
		self.assertIn("recommendations", res_dict)
		self.assertEqual(res_dict["summary"]["total_decisions_evaluated"], 2)


if __name__ == "__main__":
	unittest.main()
