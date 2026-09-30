from __future__ import annotations

import copy
import shutil
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pridict.process_intelligence.collection import collect_purchasing_configuration
from pridict.process_intelligence.graph import build_process_graph
from pridict.process_intelligence.modeling import build_purchasing_process_model
from pridict.process_intelligence.persistence import FilesystemProcessModelRepository, compute_process_hash
from pridict.process_intelligence.reporting import render_process_report
from pridict.process_intelligence.schema_adapter import SchemaSnapshotAdapter
from pridict.schema_intelligence.models import (
	DocTypeSchema,
	Diagnostic,
	FieldSchema,
	PermissionSchema,
	Provenance,
	RelationshipSchema,
)
from pridict.schema_intelligence.snapshots import build_snapshot


class FakeConfigurationSource:
	def __init__(self, records=None):
		self.records = copy.deepcopy(records or {})
		self.calls = []

	def has_doctype(self, doctype):
		return doctype in self.records

	def get_records(self, doctype, *, filters=None, fields=(), order_by="name asc"):
		self.calls.append((doctype, copy.deepcopy(filters), fields, order_by))
		rows = copy.deepcopy(self.records.get(doctype, []))
		for fieldname, expected in (filters or {}).items():
			if isinstance(expected, list) and expected[0] == "in":
				rows = [row for row in rows if row.get(fieldname) in expected[1]]
			else:
				rows = [row for row in rows if row.get(fieldname) == expected]
		return [{field: row.get(field) for field in fields} for row in rows]


def make_snapshot(
	*,
	include_relationship=True,
	include_purchase_invoice=True,
	diagnostics=None,
	snapshot_id="11111111-1111-1111-1111-111111111111",
):
	provenance = (Provenance("DocType JSON", "erpnext/buying/doctype"),)
	field_provenance = (Provenance("DocField", "database:DocField"),)
	permission_provenance = (Provenance("DocPerm", "database:DocPerm"),)

	def doctype(name, submittable=True):
		return DocTypeSchema(
			name=name,
			module="Buying" if name != "Payment Entry" else "Accounts",
			flags={"is_submittable": int(submittable)},
			properties={},
			fields=(
				FieldSchema(name, "company", "Link", 1, "Company", "Company", True, False, False, False, False, {}, field_provenance),
				FieldSchema(name, "status", "Select", 2, "Status", "Draft\nSubmitted\nCancelled", False, True, False, False, False, {}, field_provenance),
			),
			permissions=(PermissionSchema(name, "Purchase User", 0, {"read": 1, "write": 1}, False, "DocPerm", permission_provenance),),
			provenance=provenance,
		)

	doctypes = [doctype("Material Request"), doctype("Purchase Order")]
	if include_purchase_invoice:
		doctypes.append(doctype("Purchase Invoice"))
	relationships = []
	if include_relationship:
		relationships.append(
			RelationshipSchema(
				"Purchase Order.material_request->Material Request",
				"LINK",
				"Purchase Order",
				"material_request",
				"Material Request",
				None,
				(),
				{},
				field_provenance,
			)
		)
	return build_snapshot(
		frappe_version="15.120.1",
		erpnext_version="15.121.2",
		site="test.localhost",
		doctypes=doctypes,
		relationships=relationships,
		raw_metadata={},
		diagnostics=diagnostics or [],
		captured_at=datetime(2026, 9, 29, tzinfo=timezone.utc),
		snapshot_id=snapshot_id,
	)


def configured_source():
	return FakeConfigurationSource(
		{
			"Workflow": [
				{"name": "Purchase Approval", "document_type": "Purchase Order", "workflow_name": "Purchase Approval", "is_active": 1, "workflow_state_field": "workflow_state", "send_email_alert": 0}
			],
			"Workflow Document State": [
				{"name": "state-1", "parent": "Purchase Approval", "state": "Draft", "doc_status": "0", "allow_edit": "Purchase User"},
				{"name": "state-2", "parent": "Purchase Approval", "state": "Approved", "doc_status": "1", "allow_edit": "Purchase Manager"},
			],
			"Workflow Transition": [
				{"name": "transition-1", "parent": "Purchase Approval", "state": "Draft", "action": "Approve", "next_state": "Approved", "allowed": "Purchase Manager", "condition": "doc.grand_total < 10000", "allow_self_approval": 0}
			],
			"Assignment Rule": [],
			"Notification": [],
			"Client Script": [{"name": "PO Client Rule", "dt": "Purchase Order", "view": "Form", "enabled": 1, "script": "frappe.msgprint('x')"}],
			"Server Script": [],
		}
	)


class TestProcessIntelligence(unittest.TestCase):
	def test_consumes_real_schema_snapshot_and_preserves_native_states(self):
		schema = SchemaSnapshotAdapter().adapt_purchasing(make_snapshot())
		configuration = collect_purchasing_configuration(schema, FakeConfigurationSource(), collected_at="2026-09-29T00:00:00Z")
		model = build_purchasing_process_model(schema, configuration)
		material_request = next(step for step in model.steps if step.name == "Material Request")
		self.assertEqual(material_request.native_states, ("Draft", "Submitted", "Cancelled"))
		self.assertEqual(material_request.actor, "UNKNOWN")

	def test_configured_workflow_states_transitions_and_condition_are_preserved(self):
		schema = SchemaSnapshotAdapter().adapt_purchasing(make_snapshot())
		configuration = collect_purchasing_configuration(schema, configured_source(), collected_at="2026-09-29T00:00:00Z")
		model = build_purchasing_process_model(schema, configuration)
		purchase_order = next(step for step in model.steps if step.name == "Purchase Order")
		transition = next(item for item in model.transitions if item.transition_type == "CONFIGURED_WORKFLOW_STATE_CHANGE")
		self.assertEqual(purchase_order.native_states, ("Draft", "Approved"))
		self.assertEqual((transition.from_state, transition.to_state), ("Draft", "Approved"))
		self.assertEqual(transition.condition_support, "RECORDED_NOT_EXECUTED")
		self.assertEqual(model.decisions[0].owner, "Purchase Manager")

	def test_relationship_is_not_promoted_to_proven_process_sequence(self):
		schema = SchemaSnapshotAdapter().adapt_purchasing(make_snapshot())
		configuration = collect_purchasing_configuration(schema, FakeConfigurationSource(), collected_at="2026-09-29T00:00:00Z")
		model = build_purchasing_process_model(schema, configuration)
		transition = next(item for item in model.transitions if item.transition_type.startswith("SCHEMA_REFERENCE"))
		self.assertEqual(transition.assertion_kind, "inferred")
		self.assertEqual(transition.confidence, "LOW")

	def test_scripts_are_hashed_not_exposed_or_executed(self):
		schema = SchemaSnapshotAdapter().adapt_purchasing(make_snapshot())
		configuration = collect_purchasing_configuration(schema, configured_source(), collected_at="2026-09-29T00:00:00Z")
		self.assertNotIn("script", configuration["client_scripts"][0])
		self.assertEqual(len(configuration["client_scripts"][0]["script_hash"]), 64)
		model = build_purchasing_process_model(schema, configuration)
		self.assertTrue(any("not interpreted" in gap.description for gap in model.gaps))

	def test_missing_references_conflicts_unknowns_and_undefined_resolution(self):
		source = configured_source()
		source.records["Workflow"].append({**source.records["Workflow"][0], "name": "Second Purchase Approval"})
		source.records["Workflow Transition"].append({"name": "orphan", "parent": "Purchase Approval", "state": "Draft", "action": "Reject", "next_state": "Rejected", "allowed": "Purchase Manager", "condition": None})
		schema = SchemaSnapshotAdapter().adapt_purchasing(make_snapshot(include_purchase_invoice=False))
		configuration = collect_purchasing_configuration(schema, source, collected_at="2026-09-29T00:00:00Z")
		model = build_purchasing_process_model(schema, configuration)
		gap_text = " ".join(item.description for item in model.gaps)
		self.assertIn("Multiple active Workflows", gap_text)
		self.assertIn("undefined state", gap_text)
		self.assertEqual(model.process_owner, "UNKNOWN")
		self.assertTrue(all(item.resolution == "UNDEFINED" for item in model.exceptions))

	def test_incomplete_schema_is_reported_as_a_gap(self):
		diagnostic = Diagnostic("error", "missing_metadata", "extraction", "Metadata could not be read", "Purchase Order")
		schema = SchemaSnapshotAdapter().adapt_purchasing(make_snapshot(diagnostics=[diagnostic]))
		configuration = collect_purchasing_configuration(schema, FakeConfigurationSource(), collected_at="2026-09-29T00:00:00Z")
		model = build_purchasing_process_model(schema, configuration)
		self.assertTrue(any(gap.gap_id == "gap-incomplete-schema" for gap in model.gaps))
		self.assertTrue(any(item.source_type == "Schema Diagnostic" for item in model.evidence))

	def test_output_is_deterministic_except_collection_times(self):
		schema = SchemaSnapshotAdapter().adapt_purchasing(make_snapshot())
		equivalent_schema = SchemaSnapshotAdapter().adapt_purchasing(
			make_snapshot(snapshot_id="22222222-2222-2222-2222-222222222222")
		)
		first = build_purchasing_process_model(schema, collect_purchasing_configuration(schema, configured_source(), collected_at="2026-09-29T00:00:00Z"))
		second = build_purchasing_process_model(equivalent_schema, collect_purchasing_configuration(equivalent_schema, configured_source(), collected_at="2026-09-29T01:00:00Z"))
		self.assertEqual(first.process_id, second.process_id)
		self.assertEqual(first.deterministic_dict(), second.deterministic_dict())
		self.assertEqual(compute_process_hash(first), compute_process_hash(second))

	def test_repeated_collection_is_read_only_and_persistence_round_trips(self):
		source = configured_source()
		original = copy.deepcopy(source.records)
		schema = SchemaSnapshotAdapter().adapt_purchasing(make_snapshot())
		configuration = collect_purchasing_configuration(schema, source, collected_at="2026-09-29T00:00:00Z")
		model = build_purchasing_process_model(schema, configuration)
		collect_purchasing_configuration(schema, source, collected_at="2026-09-29T00:00:00Z")
		self.assertEqual(source.records, original)
		directory = Path(__file__).parent / f".test-process-model-{uuid.uuid4().hex}"
		directory.mkdir()
		try:
			repository = FilesystemProcessModelRepository(directory)
			repository.save(model)
			self.assertEqual(repository.load(model.process_id), model)
		finally:
			shutil.rmtree(directory)

	def test_graph_and_report_use_required_contract(self):
		schema = SchemaSnapshotAdapter().adapt_purchasing(make_snapshot())
		model = build_purchasing_process_model(schema, collect_purchasing_configuration(schema, configured_source(), collected_at="2026-09-29T00:00:00Z"))
		graph = build_process_graph(model)
		report = render_process_report(model)
		self.assertTrue(graph["directed"])
		self.assertTrue(all(edge["evidence_ids"] for edge in graph["edges"]))
		for heading in ("PROCESS", "TRIGGER", "PROCESS FLOW", "DECISION POINTS", "EXCEPTIONS", "PROCESS GRAPH", "PROCESS GAPS", "PROCESS SUMMARY"):
			self.assertIn(heading, report)


if __name__ == "__main__":
	unittest.main()
