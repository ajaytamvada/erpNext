import hashlib
import re
from datetime import datetime, timezone
from unittest.mock import patch

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import (
	delete_property_setter,
	make_property_setter,
)
from frappe.tests.utils import FrappeTestCase
from frappe.utils import convert_utc_to_system_timezone

from pridict.schema_intelligence.comparison import compare_snapshots
from pridict.schema_intelligence import api
from pridict.schema_intelligence.frappe_source import FrappeMetadataSource
from pridict.schema_intelligence.governance import index_snapshot
from pridict.schema_intelligence.normalization import canonical_json
from pridict.schema_intelligence.service import capture_snapshot
from pridict.schema_intelligence.snapshots import build_snapshot


REPRESENTATIVE_DOCTYPES = {
	"Customer",
	"Supplier",
	"Item",
	"Warehouse",
	"Sales Order",
	"Sales Order Item",
	"Purchase Order",
	"Purchase Order Item",
	"Delivery Note",
	"Sales Invoice",
	"Payment Entry",
}
CUSTOM_FIELD_NAME = "custom_pridict_schema_tier"
CUSTOM_LABEL = "Customer Name (Schema Test)"
WRITE_STATEMENT = re.compile(
	r"^\s*(?:insert|update|delete|replace|alter|create|drop|truncate|rename|grant|revoke|call)\b",
	re.IGNORECASE,
)


class TestSchemaIntelligenceGovernanceIntegration(FrappeTestCase):
	def test_index_snapshot_persists_timezone_aware_capture_time(self):
		captured_at = datetime(2026, 9, 23, 16, 3, 29, 2162, tzinfo=timezone.utc)
		snapshot = build_snapshot(
			frappe_version="15.120.1",
			erpnext_version="15.121.2",
			site="development.localhost",
			doctypes=[],
			relationships=[],
			raw_metadata={},
			diagnostics=[],
			captured_at=captured_at,
		)

		try:
			index_snapshot(snapshot, origin="Manual")
			stored_value = frappe.db.get_value("Schema Snapshot Record", snapshot.snapshot_id, "captured_at")
			expected_value = convert_utc_to_system_timezone(captured_at).replace(tzinfo=None)
			self.assertEqual(stored_value, expected_value)
			self.assertIsNone(stored_value.tzinfo)
		finally:
			frappe.delete_doc("Schema Snapshot Record", snapshot.snapshot_id, force=True)


class TestSchemaIntelligenceBaselineIntegration(FrappeTestCase):
	def setUp(self):
		if frappe.conf.get("schema_intelligence_profile") != "clean":
			self.skipTest("requires the clean schema-intelligence site")

	def test_real_site_discovery_relationships_and_idempotency(self):
		first = capture_snapshot()
		second = capture_snapshot()
		self.assertEqual(first.completeness, "complete")
		self.assertTrue(REPRESENTATIVE_DOCTYPES.issubset({item.name for item in first.doctypes}))
		self.assertEqual(first.metadata_hash, second.metadata_hash)

		sales_order = next(item for item in first.doctypes if item.name == "Sales Order")
		actual_meta = FrappeMetadataSource().get_effective_metadata("Sales Order")
		actual_fields = {
			field["fieldname"]: (field["fieldtype"], field.get("options"))
			for field in actual_meta["fields"]
		}
		for field in sales_order.fields:
			self.assertEqual((field.fieldtype, field.options), actual_fields[field.fieldname])

		relationships = {
			(item.source_doctype, item.source_field): item for item in first.relationships
		}
		self.assertEqual(relationships[("Sales Order", "customer")].target_doctype, "Customer")
		self.assertEqual(
			relationships[("Sales Order", "items")].target_doctype,
			"Sales Order Item",
		)

	def test_extraction_executes_no_database_writes(self):
		before = _metadata_fingerprint()
		original_sql = frappe.db.sql
		observed_queries = []

		def guarded_sql(query, *args, **kwargs):
			statement = str(query)
			observed_queries.append(statement)
			if WRITE_STATEMENT.match(statement):
				raise AssertionError(f"extraction attempted a database write: {statement[:120]}")
			return original_sql(query, *args, **kwargs)

		with (
			patch.object(frappe.db, "sql", side_effect=guarded_sql),
			patch.object(frappe.db, "commit", side_effect=AssertionError("extraction attempted a commit")),
		):
			snapshot = capture_snapshot()

		after = _metadata_fingerprint()
		self.assertEqual(snapshot.completeness, "complete")
		self.assertTrue(observed_queries)
		self.assertEqual(before, after)

	def test_remote_api_requires_system_manager(self):
		frappe.set_user("Guest")
		try:
			protected_calls = {
				"capture_snapshot": lambda: api.capture_snapshot(),
				"capture_and_persist": lambda: api.capture_and_persist(),
				"get_snapshot": lambda: api.get_snapshot("missing"),
				"list_snapshots": api.list_snapshots,
				"get_snapshot_overview": lambda: api.get_snapshot_overview("missing"),
				"get_doctype_schema": lambda: api.get_doctype_schema("missing", "Sales Order"),
				"compare_snapshots": lambda: api.compare_snapshots("before", "after"),
				"get_settings": api.get_settings,
				"update_settings": lambda: api.update_settings({}),
				"update_snapshot": lambda: api.update_snapshot("missing"),
				"delete_snapshot": lambda: api.delete_snapshot("missing", 1),
				"promote_baseline": lambda: api.promote_baseline("missing", 1),
				"create_review": lambda: api.create_review("before", "after"),
				"list_reviews": api.list_reviews,
				"get_review": lambda: api.get_review("missing"),
				"list_findings": lambda: api.list_findings("missing"),
				"transition_review": lambda: api.transition_review("missing", "Approved"),
				"add_review_comment": lambda: api.add_review_comment("missing", "comment"),
				"promote_review_baseline": lambda: api.promote_review_baseline("missing", 1),
				"get_relationship_subgraph": lambda: api.get_relationship_subgraph("missing", "Sales Order"),
				"export_snapshot_summary": lambda: api.export_snapshot_summary("missing"),
				"export_comparison": lambda: api.export_comparison("missing"),
				"export_review": lambda: api.export_review("missing"),
				"export_findings_csv": lambda: api.export_findings_csv("missing"),
				"export_subgraph": lambda: api.export_subgraph("missing", "Sales Order"),
				"get_future_analysis_payload": lambda: api.get_future_analysis_payload("missing"),
				"retry_review_notification": lambda: api.retry_review_notification("missing"),
			}
			for name, protected_call in protected_calls.items():
				with self.subTest(endpoint=name), self.assertRaises(frappe.PermissionError):
					protected_call()
		finally:
			frappe.set_user("Administrator")


class TestSchemaIntelligenceCustomizedIntegration(FrappeTestCase):
	def setUp(self):
		if frappe.conf.get("schema_intelligence_profile") != "custom":
			self.skipTest("requires the customized schema-intelligence site")
		_cleanup_fixture()

	def tearDown(self):
		_cleanup_fixture()

	def test_custom_field_override_and_controlled_diff(self):
		before = capture_snapshot()
		_apply_fixture()
		after = capture_snapshot()
		repeated = capture_snapshot()

		customer = next(item for item in after.doctypes if item.name == "Customer")
		custom_field = next(item for item in customer.fields if item.fieldname == CUSTOM_FIELD_NAME)
		customer_name = next(item for item in customer.fields if item.fieldname == "customer_name")
		self.assertTrue(custom_field.custom)
		self.assertEqual(custom_field.provenance[0].source_type, "Custom Field")
		self.assertEqual(customer_name.label, CUSTOM_LABEL)
		self.assertIn("Property Setter", {item.source_type for item in customer_name.provenance})
		self.assertEqual(after.metadata_hash, repeated.metadata_hash)

		diff = compare_snapshots(before, after)
		self.assertFalse(diff["equivalent"])
		self.assertIn(CUSTOM_FIELD_NAME, diff["fields"]["Customer"]["added"])
		self.assertIn("customer_name", diff["fields"]["Customer"]["changed"])


def _apply_fixture():
	create_custom_field(
		"Customer",
		{
			"fieldname": CUSTOM_FIELD_NAME,
			"label": "Schema Tier",
			"fieldtype": "Data",
			"insert_after": "customer_name",
		},
		is_system_generated=False,
	)
	make_property_setter(
		"Customer",
		"customer_name",
		"label",
		CUSTOM_LABEL,
		"Data",
		is_system_generated=False,
	)
	frappe.clear_cache(doctype="Customer")


def _cleanup_fixture():
	for name in frappe.get_all(
		"Custom Field",
		filters={"dt": "Customer", "fieldname": CUSTOM_FIELD_NAME},
		pluck="name",
	):
		frappe.delete_doc("Custom Field", name, force=True)
	delete_property_setter("Customer", property="label", field_name="customer_name")
	frappe.clear_cache(doctype="Customer")
	frappe.db.commit()


def _metadata_fingerprint():
	payload = {}
	for doctype, filters, order_by in (
		("DocType", {}, "name asc"),
		("DocField", {}, "parent asc, idx asc, name asc"),
		("DocPerm", {}, "parent asc, idx asc, name asc"),
		("Custom Field", {}, "dt asc, idx asc, name asc"),
		("Property Setter", {}, "doc_type asc, name asc"),
		("Custom DocPerm", {}, "parent asc, idx asc, name asc"),
	):
		payload[doctype] = frappe.get_all(
			doctype,
			filters=filters,
			fields="*",
			order_by=order_by,
		)
	return hashlib.sha256(canonical_json(payload).encode()).hexdigest()
