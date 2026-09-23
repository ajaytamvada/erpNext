from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from pridict.schema_intelligence.comparison import compare_snapshots
from pridict.schema_intelligence.classification import classify_changes
from pridict.schema_intelligence.artifacts import relationship_graph
from pridict.schema_intelligence.extraction import extract_schema
from pridict.schema_intelligence.graph import relationship_subgraph
from pridict.schema_intelligence.normalization import canonical_json, normalize_value
from pridict.schema_intelligence.persistence import (
	FilesystemSnapshotRepository,
	IncompleteSnapshotError,
	InMemorySnapshotRepository,
)
from pridict.schema_intelligence.service import get_doctype_schema, get_snapshot_overview, list_snapshot_summaries


class FakeMetadataSource:
	site = "schema-test.localhost"
	frappe_version = "15.120.1"
	erpnext_version = "15.121.2"

	def __init__(self, metadata, raw=None, failures=None):
		self.metadata = metadata
		self.raw = raw or {name: _raw_metadata(name, value) for name, value in metadata.items()}
		self.failures = failures or set()

	def discover_doctypes(self):
		return list(reversed(self.metadata))

	def get_raw_metadata(self, doctype):
		if doctype in self.failures:
			raise RuntimeError("controlled metadata failure")
		return deepcopy(self.raw[doctype])

	def get_effective_metadata(self, doctype):
		return deepcopy(self.metadata[doctype])


def _raw_metadata(name, effective):
	return {
		"doctype": {"name": name, "module": effective.get("module")},
		"docfields": [
			dict(field, name=f"{name}-{field.get('fieldname')}") for field in effective.get("fields", [])
		],
		"docperms": [
			dict(permission, name=f"{name}-perm-{index}")
			for index, permission in enumerate(effective.get("permissions", []))
		],
		"custom_fields": [],
		"property_setters": [],
		"custom_docperms": [],
		"custom_links": [],
		"custom_actions": [],
		"custom_states": [],
	}


def _base_metadata():
	return {
		"DocType": {
			"name": "DocType",
			"module": "Core",
			"fields": [],
			"permissions": [],
		},
		"Customer": {
			"name": "Customer",
			"module": "Selling",
			"fields": [
				{"fieldname": "customer_name", "fieldtype": "Data", "idx": 1, "reqd": 1},
			],
			"permissions": [{"role": "Sales User", "permlevel": 0, "read": 1, "write": 1}],
		},
		"Sales Order Item": {
			"name": "Sales Order Item",
			"module": "Selling",
			"istable": 1,
			"fields": [
				{"fieldname": "item_code", "fieldtype": "Link", "options": "Item", "idx": 1},
			],
			"permissions": [],
		},
		"Item": {
			"name": "Item",
			"module": "Stock",
			"fields": [{"fieldname": "item_name", "fieldtype": "Data", "idx": 1}],
			"permissions": [],
		},
		"Sales Team Member": {
			"name": "Sales Team Member",
			"module": "Selling",
			"istable": 1,
			"fields": [
				{"fieldname": "sales_person", "fieldtype": "Link", "options": "Customer", "idx": 1},
			],
			"permissions": [],
		},
		"Sales Order": {
			"name": "Sales Order",
			"module": "Selling",
			"is_submittable": 1,
			"fields": [
				{"fieldname": "customer", "fieldtype": "Link", "options": "Customer", "idx": 1},
				{
					"fieldname": "items",
					"fieldtype": "Table",
					"options": "Sales Order Item",
					"idx": 2,
				},
				{"fieldname": "reference_doctype", "fieldtype": "Link", "options": "DocType", "idx": 3},
				{
					"fieldname": "reference_name",
					"fieldtype": "Dynamic Link",
					"options": "reference_doctype",
					"idx": 4,
				},
				{
					"fieldname": "sales_team",
					"fieldtype": "Table MultiSelect",
					"options": "Sales Team Member",
					"idx": 5,
				},
			],
			"permissions": [{"role": "Sales User", "permlevel": 0, "read": 1, "write": 1}],
		},
	}


class TestSchemaExtraction(TestCase):
	def test_extracts_doctypes_fields_relationships_and_permissions(self):
		snapshot = extract_schema(FakeMetadataSource(_base_metadata()))
		self.assertEqual(snapshot.completeness, "complete")
		self.assertEqual([item.name for item in snapshot.doctypes], sorted(_base_metadata()))

		sales_order = next(item for item in snapshot.doctypes if item.name == "Sales Order")
		self.assertEqual([field.fieldname for field in sales_order.fields], [
			"customer",
			"items",
			"reference_doctype",
			"reference_name",
			"sales_team",
		])
		self.assertEqual(sales_order.permissions[0].source, "DocPerm")
		self.assertTrue(sales_order.permissions[0].permissions["read"])

		relationships = {item.source_field: item for item in snapshot.relationships}
		self.assertEqual(relationships["customer"].target_doctype, "Customer")
		self.assertEqual(relationships["items"].relationship_type, "CHILD_TABLE")
		self.assertEqual(relationships["items"].target_doctype, "Sales Order Item")
		self.assertEqual(relationships["reference_name"].relationship_type, "DYNAMIC_LINK")
		self.assertEqual(relationships["reference_name"].selector_field, "reference_doctype")
		self.assertIn("Customer", relationships["reference_name"].discoverable_targets)
		self.assertEqual(relationships["sales_team"].relationship_type, "TABLE_MULTISELECT")
		self.assertEqual(
			relationships["sales_team"].properties["child_link_fields"],
			[{"fieldname": "sales_person", "target_doctype": "Customer"}],
		)

	def test_custom_field_and_property_setter_provenance(self):
		metadata = _base_metadata()
		metadata["Customer"]["fields"].append(
			{
				"fieldname": "custom_schema_tier",
				"fieldtype": "Data",
				"label": "Schema Tier",
				"idx": 2,
				"is_custom_field": 1,
			}
		)
		metadata["Customer"]["fields"][0]["label"] = "Customer Display Name"
		raw = {name: _raw_metadata(name, value) for name, value in metadata.items()}
		raw["Customer"]["custom_fields"] = [
			{
				"name": "Customer-custom_schema_tier",
				"dt": "Customer",
				"fieldname": "custom_schema_tier",
				"fieldtype": "Data",
			}
		]
		raw["Customer"]["docfields"] = [raw["Customer"]["docfields"][0]]
		raw["Customer"]["property_setters"] = [
			{
				"name": "Customer-customer_name-label",
				"doc_type": "Customer",
				"doctype_or_field": "DocField",
				"field_name": "customer_name",
				"property": "label",
				"value": "Customer Display Name",
			}
		]

		snapshot = extract_schema(FakeMetadataSource(metadata, raw))
		customer = next(item for item in snapshot.doctypes if item.name == "Customer")
		custom_field = next(item for item in customer.fields if item.fieldname == "custom_schema_tier")
		standard_field = next(item for item in customer.fields if item.fieldname == "customer_name")
		self.assertTrue(custom_field.custom)
		self.assertEqual(custom_field.provenance[0].source_type, "Custom Field")
		self.assertIn("Property Setter", {item.source_type for item in standard_field.provenance})

	def test_custom_permissions_replace_standard_permission_source(self):
		metadata = _base_metadata()
		raw = {name: _raw_metadata(name, value) for name, value in metadata.items()}
		raw["Sales Order"]["custom_docperms"] = [
			{"name": "custom-perm", "parent": "Sales Order", "role": "Sales User", "permlevel": 0}
		]
		snapshot = extract_schema(FakeMetadataSource(metadata, raw))
		sales_order = next(item for item in snapshot.doctypes if item.name == "Sales Order")
		self.assertEqual(sales_order.permissions[0].source, "Custom DocPerm")

	def test_missing_relationship_target_is_reported_without_losing_completeness(self):
		metadata = _base_metadata()
		metadata["Sales Order"]["fields"][0]["options"] = "Missing Customer"
		snapshot = extract_schema(FakeMetadataSource(metadata))
		self.assertEqual(snapshot.completeness, "complete")
		self.assertIn("link_target_not_discovered", {item.code for item in snapshot.diagnostics})

	def test_malformed_field_is_reported_without_losing_other_doctypes(self):
		metadata = _base_metadata()
		metadata["Customer"]["fields"].append({"fieldname": "broken", "idx": 2})
		snapshot = extract_schema(FakeMetadataSource(metadata))
		self.assertEqual(snapshot.completeness, "incomplete")
		self.assertIn("Customer", {item.name for item in snapshot.doctypes})
		diagnostic = next(item for item in snapshot.diagnostics if item.code == "field_normalization_failed")
		self.assertEqual(diagnostic.doctype, "Customer")
		self.assertEqual(diagnostic.fieldname, "broken")

	def test_partial_source_failure_is_reported(self):
		snapshot = extract_schema(FakeMetadataSource(_base_metadata(), failures={"Customer"}))
		self.assertEqual(snapshot.completeness, "incomplete")
		self.assertNotIn("Customer", {item.name for item in snapshot.doctypes})
		self.assertIn("doctype_extraction_failed", {item.code for item in snapshot.diagnostics})

	def test_unchanged_extractions_have_equivalent_content_and_hash(self):
		first = extract_schema(FakeMetadataSource(_base_metadata()))
		raw = {name: _raw_metadata(name, value) for name, value in _base_metadata().items()}
		raw["Customer"]["docfields"][0]["name"] = "different-random-row-id"
		second = extract_schema(FakeMetadataSource(_base_metadata(), raw=raw))
		self.assertNotEqual(first.snapshot_id, second.snapshot_id)
		self.assertEqual(first.metadata_hash, second.metadata_hash)
		self.assertTrue(compare_snapshots(first, second)["equivalent"])

	def test_field_and_permission_changes_affect_hash_and_diff(self):
		before = extract_schema(FakeMetadataSource(_base_metadata()))
		changed = _base_metadata()
		changed["Customer"]["fields"][0]["reqd"] = 0
		changed["Sales Order"]["permissions"][0]["write"] = 0
		after = extract_schema(FakeMetadataSource(changed))
		diff = compare_snapshots(before, after)
		self.assertNotEqual(before.metadata_hash, after.metadata_hash)
		self.assertEqual(diff["fields"]["Customer"]["changed"], ["customer_name"])
		self.assertEqual(diff["permissions"]["Sales Order"]["changed"], ["Sales User:0:0"])
		self.assertNotIn("Customer", diff["field_order_changed"])

	def test_relationship_change_is_structural(self):
		before = extract_schema(FakeMetadataSource(_base_metadata()))
		changed = _base_metadata()
		changed["Sales Order"]["fields"][0]["options"] = "Item"
		after = extract_schema(FakeMetadataSource(changed))
		diff = compare_snapshots(before, after)
		self.assertEqual(diff["relationships"]["changed"], ["Sales Order.customer:LINK"])

	def test_deterministic_classification_assigns_expected_severity(self):
		before_metadata = _base_metadata()
		after_metadata = _base_metadata()
		after_metadata["Customer"]["fields"][0]["fieldtype"] = "Link"
		after_metadata["Customer"]["fields"][0]["options"] = "Item"
		after_metadata["Sales Order"]["fields"].append(
			{"fieldname": "required_reference", "fieldtype": "Data", "idx": 6, "reqd": 1}
		)
		before = extract_schema(FakeMetadataSource(before_metadata))
		after = extract_schema(FakeMetadataSource(after_metadata))

		first = classify_changes(before, after)
		second = classify_changes(before, after)
		self.assertEqual(first["comparison_hash"], second["comparison_hash"])
		self.assertIn("field.type_changed", {item["rule_id"] for item in first["findings"]})
		self.assertIn("field.required_added", {item["rule_id"] for item in first["findings"]})
		self.assertGreaterEqual(first["severity_totals"]["critical"], 1)
		self.assertGreaterEqual(first["severity_totals"]["warning"], 1)

	def test_relationship_subgraph_is_bounded_and_filterable(self):
		snapshot = extract_schema(FakeMetadataSource(_base_metadata()))
		graph = relationship_subgraph(
			snapshot,
			"Sales Order",
			hops=2,
			direction="outgoing",
			relationship_types={"LINK", "CHILD_TABLE"},
			node_limit=3,
			edge_limit=2,
		)
		self.assertLessEqual(len(graph["nodes"]), 3)
		self.assertLessEqual(len(graph["edges"]), 2)
		self.assertTrue(all(item["relationship_type"] in {"LINK", "CHILD_TABLE"} for item in graph["edges"]))

	def test_malformed_dynamic_link_is_reported(self):
		metadata = _base_metadata()
		metadata["Sales Order"]["fields"][2]["fieldtype"] = "Data"
		snapshot = extract_schema(FakeMetadataSource(metadata))
		self.assertIn("dynamic_link_selector_invalid", {item.code for item in snapshot.diagnostics})

	def test_non_json_values_are_explicitly_normalized(self):
		value = normalize_value(
			{
				"when": datetime(2026, 9, 22, tzinfo=timezone.utc),
				"path": Path("schema.json"),
				"values": {"b", "a"},
			}
		)
		self.assertEqual(value["when"]["$type"], "datetime")
		self.assertEqual(value["path"]["$type"], "path")
		self.assertEqual(canonical_json(value["values"]), canonical_json(normalize_value({"a", "b"})))


class TestSnapshotPersistence(TestCase):
	def test_memory_and_filesystem_round_trip(self):
		snapshot = extract_schema(FakeMetadataSource(_base_metadata()))
		memory = InMemorySnapshotRepository()
		memory.save(snapshot, require_complete=True)
		self.assertEqual(memory.load(snapshot.snapshot_id), snapshot)

		with TemporaryDirectory() as directory:
			repository = FilesystemSnapshotRepository(directory)
			repository.save(snapshot, require_complete=True)
			loaded = repository.load(snapshot.snapshot_id)
			self.assertEqual(loaded.to_dict(), snapshot.to_dict())
			self.assertEqual(repository.list_ids(), [snapshot.snapshot_id])
			repository.delete(snapshot.snapshot_id)
			self.assertEqual(repository.list_ids(), [])

		memory.delete(snapshot.snapshot_id)
		self.assertEqual(memory.list_ids(), [])

	def test_incomplete_snapshot_cannot_be_saved_as_baseline(self):
		snapshot = extract_schema(FakeMetadataSource(_base_metadata(), failures={"Customer"}))
		with self.assertRaises(IncompleteSnapshotError):
			InMemorySnapshotRepository().save(snapshot, require_complete=True)

	def test_relationship_graph_is_generated_from_snapshot_relationships(self):
		snapshot = extract_schema(FakeMetadataSource(_base_metadata()))
		graph = relationship_graph(snapshot, "Sales Order")
		self.assertIn("flowchart LR", graph)
		self.assertIn("customer · LINK", graph)
		self.assertIn("items · CHILD_TABLE", graph)
		self.assertNotIn("created_at", graph)

	def test_frontend_service_contract_uses_compact_summaries(self):
		snapshot = extract_schema(FakeMetadataSource(_base_metadata()))
		repository = InMemorySnapshotRepository()
		repository.save(snapshot)

		summaries = list_snapshot_summaries(repository)
		self.assertEqual(summaries[0]["doctype_count"], len(_base_metadata()))
		self.assertNotIn("raw_metadata", summaries[0])

		overview = get_snapshot_overview(snapshot.snapshot_id, repository)
		self.assertIn("Sales Order", {item["name"] for item in overview["doctypes"]})
		self.assertNotIn("raw_metadata", overview)

		detail = get_doctype_schema(snapshot.snapshot_id, "Sales Order", repository)
		self.assertEqual(detail["doctype"]["name"], "Sales Order")
		self.assertNotIn("raw_metadata", detail)
