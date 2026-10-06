from __future__ import annotations

import copy
import json
import shutil
import unittest
import uuid
from pathlib import Path

from pridict.process_intelligence.collection import collect_purchasing_configuration
from pridict.process_intelligence.modeling import build_purchasing_process_model
from pridict.process_intelligence.reconstruction import reconstruct_purchasing
from pridict.process_intelligence.reconstruction_graph import build_reconstruction_graph
from pridict.process_intelligence.reconstruction_persistence import FilesystemReconstructionRepository
from pridict.process_intelligence.reconstruction_reporting import render_reconstruction_report
from pridict.process_intelligence.schema_adapter import SchemaSnapshotAdapter
from pridict.process_intelligence.test_process_intelligence import FakeConfigurationSource, make_snapshot
from pridict.process_intelligence.transaction_collection import collect_transactions
from pridict.process_intelligence.transaction_models import TransactionScope


class FakeTransactionSource:
	def __init__(self, records=None):
		self.records = copy.deepcopy(records or {})
		self.calls = []

	def has_doctype(self, doctype):
		return doctype in self.records

	def get_records(
		self,
		doctype,
		*,
		filters=None,
		fields=(),
		order_by="creation asc, name asc",
		limit=0,
	):
		self.calls.append((doctype, copy.deepcopy(filters), fields, order_by, limit))
		rows = copy.deepcopy(self.records.get(doctype, []))
		for fieldname, expected in (filters or {}).items():
			if isinstance(expected, list) and expected[0] == "in":
				rows = [row for row in rows if row.get(fieldname) in expected[1]]
			elif isinstance(expected, list) and expected[0] == "between":
				rows = [row for row in rows if expected[1][0] <= str(row.get(fieldname)) <= expected[1][1]]
			else:
				rows = [row for row in rows if row.get(fieldname) == expected]
		if limit:
			rows = rows[:limit]
		return [{field: row.get(field) for field in fields} for row in rows]


def build_context():
	schema = SchemaSnapshotAdapter().adapt_purchasing(make_snapshot())
	configuration = collect_purchasing_configuration(
		schema,
		FakeConfigurationSource(),
		collected_at="2026-09-29T00:00:00Z",
	)
	return schema, build_purchasing_process_model(schema, configuration)


def reconstruction_dataset(collected_at="2026-09-29T12:00:00Z"):
	return {
		"collected_at": collected_at,
		"documents": {
			"Material Request": [
				{
					"name": "MAT-RAW-0001",
					"creation": "2026-09-17 09:00:00",
					"owner": "buyer@example.com",
					"docstatus": 1,
					"status": "Submitted",
				}
			],
			"Purchase Order": [
				{
					"name": "PO-RAW-0001",
					"creation": "2026-09-18 10:00:00",
					"owner": "manager@example.com",
					"docstatus": 2,
					"status": "Cancelled",
				},
				{
					"name": "PO-RAW-0002",
					"creation": "2026-09-18 11:00:00",
					"owner": "manager@example.com",
					"docstatus": 0,
					"status": "Draft",
				},
				{
					"name": "PO-RAW-AMENDED",
					"creation": "2026-09-18 12:00:00",
					"owner": "manager@example.com",
					"docstatus": 0,
					"status": "Draft",
					"amended_from": "PO-RAW-0001",
				},
			],
			"Purchase Invoice": [
				{
					"name": "PINV-RAW-0001",
					"creation": "2026-09-19 09:00:00",
					"owner": "accounts@example.com",
					"docstatus": 1,
					"status": "Unpaid",
				},
				{
					"name": "PINV-RAW-RETURN",
					"creation": "2026-09-20 09:00:00",
					"owner": "accounts@example.com",
					"docstatus": 1,
					"status": "Return",
					"is_return": 1,
					"return_against": "PINV-RAW-0001",
				},
			],
			"Payment Entry": [
				{
					"name": "PAY-RAW-0001",
					"creation": "2026-09-21 09:00:00",
					"owner": "cashier@example.com",
					"docstatus": 1,
					"status": "Submitted",
				}
			],
		},
		"children": {
			"Material Request Item": [
				{
					"name": "MRI-RAW-0001",
					"parent": "MAT-RAW-0001",
					"parenttype": "Material Request",
					"stock_qty": 10,
				}
			],
			"Purchase Order Item": [
				{
					"name": "POI-RAW-0001",
					"parent": "PO-RAW-0001",
					"parenttype": "Purchase Order",
					"stock_qty": 4,
					"material_request": "MAT-RAW-0001",
					"material_request_item": "MRI-RAW-0001",
				},
				{
					"name": "POI-RAW-0002",
					"parent": "PO-RAW-0002",
					"parenttype": "Purchase Order",
					"stock_qty": 6,
					"material_request": "MAT-RAW-0001",
					"material_request_item": "MRI-RAW-0001",
				},
			],
			"Purchase Invoice Item": [
				{
					"name": "PII-RAW-0001",
					"parent": "PINV-RAW-0001",
					"parenttype": "Purchase Invoice",
					"stock_qty": 5,
					"purchase_order": "PO-RAW-0001",
					"po_detail": "POI-RAW-0001",
				}
			],
			"Payment Entry Reference": [
				{
					"name": "PER-RAW-0001",
					"parent": "PAY-RAW-0001",
					"parenttype": "Payment Entry",
					"reference_doctype": "Purchase Invoice",
					"reference_name": "PINV-RAW-0001",
					"allocated_amount": 125,
				}
			],
		},
		"versions": [
			{
				"name": "VERSION-RAW-0001",
				"ref_doctype": "Purchase Order",
				"docname": "PO-RAW-0001",
				"creation": "2026-09-18 10:30:00",
				"owner": "manager@example.com",
				"data": json.dumps({"changed": [["status", "Draft", "To Receive"]]}),
			}
		],
		"workflow_actions": [
			{
				"name": "ACTION-RAW-0001",
				"reference_doctype": "Purchase Order",
				"reference_name": "PO-RAW-0001",
				"workflow_state": "Review",
				"status": "Open",
				"completed_by": "approver@example.com",
				"creation": "2026-09-18 10:15:00",
			}
		],
	}


class TestTransactionScope(unittest.TestCase):
	def test_requires_bounded_iso_date_scope(self):
		with self.assertRaisesRegex(ValueError, "company is required"):
			TransactionScope("", "2026-09-01", "2026-09-29")
		with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
			TransactionScope("Test", "09/01/2026", "2026-09-29")
		with self.assertRaisesRegex(ValueError, "inclusive date range"):
			TransactionScope("Test", "2026-09-30", "2026-09-29")
		with self.assertRaisesRegex(ValueError, "between 1 and 5000"):
			TransactionScope("Test", "2026-09-01", "2026-09-29", 5001)


class TestTransactionCollection(unittest.TestCase):
	def test_collects_only_children_of_scoped_parent_doctype(self):
		schema, _process_model = build_context()
		source = FakeTransactionSource(
			{
				"Material Request": [
					{
						"name": "MR-SHARED",
						"company": "Test",
						"creation": "2026-09-10 00:00:00",
					}
				],
				"Purchase Order": [
					{
						"name": "PO-SHARED",
						"company": "Test",
						"creation": "2026-09-11 00:00:00",
					}
				],
				"Material Request Item": [
					{"name": "MRI-1", "parent": "MR-SHARED", "parenttype": "Material Request"},
					{"name": "MRI-2", "parent": "PO-SHARED", "parenttype": "Purchase Order"},
				],
			}
		)
		dataset = collect_transactions(
			schema,
			TransactionScope("Test", "2026-09-01", "2026-09-29"),
			source,
			collected_at="2026-09-29T12:00:00Z",
		)
		self.assertEqual([row["name"] for row in dataset["children"]["Material Request Item"]], ["MRI-1"])


class TestProcessReconstruction(unittest.TestCase):
	def setUp(self):
		self.schema, self.process_model = build_context()
		self.scope = TransactionScope("_Test Company", "2026-09-01", "2026-09-29")

	def reconstruct(self, dataset=None):
		return reconstruct_purchasing(
			self.process_model,
			self.schema,
			self.scope,
			dataset or reconstruction_dataset(),
		)

	def test_explicit_links_allocations_returns_amendments_and_payments(self):
		result = self.reconstruct()
		item_edges = [edge for edge in result.edges if edge.relation_type == "ITEM_LEVEL_REFERENCE"]
		material_request_edges = [edge for edge in item_edges if edge.source_doctype == "Material Request"]
		purchase_order_edges = [edge for edge in item_edges if edge.source_doctype == "Purchase Order"]
		self.assertEqual({edge.allocation_status for edge in material_request_edges}, {"FULL"})
		self.assertEqual({edge.allocation_status for edge in purchase_order_edges}, {"OVER_ALLOCATED"})
		self.assertEqual(sum(edge.relation_type == "AMENDS" for edge in result.edges), 1)
		self.assertEqual(sum(edge.relation_type == "RETURNS" for edge in result.edges), 1)
		payment = next(edge for edge in result.edges if edge.relation_type == "PAYMENT_ALLOCATION")
		self.assertEqual(payment.allocated_amount, 125)
		self.assertEqual(payment.allocation_status, "AMOUNT_RECORDED")
		self.assertEqual(result.metrics["cancellation_count"], 1)
		self.assertEqual(result.metrics["return_count"], 1)
		self.assertEqual(result.metrics["amendment_count"], 1)

	def test_no_unlinked_documents_are_promoted_to_process_transitions(self):
		dataset = reconstruction_dataset()
		dataset["documents"]["Purchase Order"].append(
			{
				"name": "PO-RAW-UNLINKED",
				"creation": "2026-09-22 09:00:00",
				"owner": "buyer@example.com",
				"docstatus": 0,
				"status": "Draft",
			}
		)
		result = self.reconstruct(dataset)
		self.assertEqual(result.metrics["unlinked_document_count"], 1)
		self.assertFalse(any("UNLINKED" in edge.relation_type for edge in result.edges))

	def test_references_at_different_stages_do_not_double_count_allocation(self):
		dataset = reconstruction_dataset()
		dataset["documents"]["Purchase Receipt"] = [{"name": "PR-RAW-1", "docstatus": 1}]
		dataset["children"]["Purchase Receipt Item"] = [{
			"name": "PRI-RAW-1", "parent": "PR-RAW-1", "parenttype": "Purchase Receipt",
			"material_request": "MAT-RAW-0001", "material_request_item": "MRI-RAW-0001", "stock_qty": 10,
		}]
		result = self.reconstruct(dataset)
		edges = [edge for edge in result.edges if edge.source_doctype == "Material Request"]
		self.assertEqual({edge.allocation_status for edge in edges}, {"FULL"})

	def test_payment_reference_survives_when_no_invoice_is_in_scope(self):
		dataset = reconstruction_dataset()
		dataset["documents"]["Purchase Invoice"] = []
		dataset["children"]["Purchase Invoice Item"] = []
		result = self.reconstruct(dataset)
		payment = next(edge for edge in result.edges if edge.relation_type == "PAYMENT_ALLOCATION")
		self.assertFalse(payment.source_in_scope)
		self.assertTrue(payment.target_in_scope)
		self.assertTrue(any("OUT_OF_SCOPE_SOURCE: Purchase Invoice" in gap for gap in result.gaps))

	def test_state_events_preserve_timestamp_semantics(self):
		result = self.reconstruct()
		current_state = next(
			event for event in result.events if event.event_type == "CURRENT_DOCUMENT_STATE_OBSERVED"
		)
		version = next(event for event in result.events if event.event_type == "DOCUMENT_STATE_CHANGED")
		workflow_action = next(
			event for event in result.events if event.event_type == "WORKFLOW_ACTION_RECORDED"
		)
		self.assertIsNone(current_state.occurred_at)
		self.assertIn("not a state-change timestamp", current_state.timestamp_semantics)
		self.assertEqual(version.timestamp_semantics, "Version creation timestamp")
		self.assertIn("not assumed to be completion time", workflow_action.timestamp_semantics)
		self.assertEqual(result.metrics["approval_time"], "DATA_NOT_AVAILABLE")

	def test_missing_reference_is_a_gap_and_raw_identifiers_are_not_exposed(self):
		dataset = reconstruction_dataset()
		dataset["children"]["Purchase Order Item"][0]["material_request"] = "MAT-RAW-MISSING"
		result = self.reconstruct(dataset)
		self.assertTrue(any(gap.startswith("OUT_OF_SCOPE_SOURCE") for gap in result.gaps))
		graph = build_reconstruction_graph(result)
		node_ids = {node["id"] for node in graph["nodes"]}
		self.assertTrue(all(edge["source_document_id"] in node_ids for edge in graph["edges"]))
		self.assertTrue(all(edge["target_document_id"] in node_ids for edge in graph["edges"]))
		serialized = json.dumps(result.to_dict(), sort_keys=True)
		for raw_value in (
			"_Test Company",
			"MAT-RAW-0001",
			"PO-RAW-0001",
			"MRI-RAW-0001",
			"buyer@example.com",
			"approver@example.com",
		):
			self.assertNotIn(raw_value, serialized)

	def test_duplicate_conflicting_and_circular_correlations_are_reported(self):
		dataset = reconstruction_dataset()
		dataset["documents"]["Material Request"].append(
			{
				"name": "MAT-RAW-0002",
				"creation": "2026-09-17 08:00:00",
				"owner": "buyer@example.com",
				"docstatus": 1,
				"status": "Submitted",
			}
		)
		dataset["children"]["Material Request Item"].append(
			{
				"name": "MRI-RAW-0002",
				"parent": "MAT-RAW-0002",
				"parenttype": "Material Request",
				"stock_qty": 10,
			}
		)
		duplicate = copy.deepcopy(dataset["children"]["Purchase Order Item"][0])
		dataset["children"]["Purchase Order Item"].append(duplicate)
		conflict = copy.deepcopy(duplicate)
		conflict["material_request"] = "MAT-RAW-0002"
		conflict["material_request_item"] = "MRI-RAW-0002"
		dataset["children"]["Purchase Order Item"].append(conflict)
		dataset["documents"]["Purchase Order"][0]["amended_from"] = "PO-RAW-AMENDED"

		result = self.reconstruct(dataset)

		self.assertTrue(any(gap.startswith("DUPLICATE_CORRELATION") for gap in result.gaps))
		self.assertTrue(any(gap.startswith("CONFLICTING_CORRELATION") for gap in result.gaps))
		self.assertTrue(any(gap.startswith("CIRCULAR_CORRELATION") for gap in result.gaps))

	def test_deterministic_output_persistence_and_graph_evidence_integrity(self):
		first = self.reconstruct(reconstruction_dataset("2026-09-29T12:00:00Z"))
		second = self.reconstruct(reconstruction_dataset("2026-09-29T13:00:00Z"))
		self.assertEqual(first.deterministic_dict(), second.deterministic_dict())
		evidence_ids = {item.evidence_id for item in first.evidence}
		graph = build_reconstruction_graph(first)
		self.assertTrue(graph["directed"])
		self.assertTrue(all(set(edge["evidence_ids"]) <= evidence_ids for edge in graph["edges"]))
		report = render_reconstruction_report(first)
		for heading in (
			"PROCESS",
			"TRIGGER",
			"PROCESS FLOW",
			"DECISION POINTS",
			"EXCEPTIONS",
			"HUMAN INVOLVEMENT",
			"PROCESS STATES",
			"PROCESS GRAPH",
			"AUTOMATION ANALYSIS",
			"PROCESS METRICS",
			"OBSERVED VS INFERRED",
			"PROCESS GAPS",
			"PROCESS SUMMARY",
		):
			self.assertIn(heading, report)
		directory = Path(__file__).parent / f".test-reconstruction-{uuid.uuid4().hex}"
		directory.mkdir()
		try:
			repository = FilesystemReconstructionRepository(directory)
			repository.save(first)
			self.assertEqual(repository.load(first.reconstruction_id), first)
		finally:
			shutil.rmtree(directory)


if __name__ == "__main__":
	unittest.main()
