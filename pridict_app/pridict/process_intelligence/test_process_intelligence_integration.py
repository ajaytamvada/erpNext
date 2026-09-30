from __future__ import annotations

import hashlib

import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.process_intelligence import api
from pridict.process_intelligence.collection import FrappeConfigurationSource
from pridict.process_intelligence.service import analyze_purchasing, reconstruct_purchasing_transactions
from pridict.process_intelligence.transaction_models import TransactionScope
from pridict.schema_intelligence.normalization import canonical_json
from pridict.schema_intelligence.service import capture_snapshot


class TestProcessIntelligenceIntegration(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_real_snapshot_and_read_only_repeated_extraction(self):
		before = _configuration_fingerprint()
		snapshot = capture_snapshot()
		first = analyze_purchasing(snapshot=snapshot, source=FrappeConfigurationSource())
		second = analyze_purchasing(snapshot=snapshot, source=FrappeConfigurationSource())
		after = _configuration_fingerprint()
		self.assertEqual(snapshot.frappe_version, "15.120.1")
		self.assertEqual(snapshot.erpnext_version, "15.121.2")
		self.assertTrue(first.steps)
		self.assertEqual(first.deterministic_dict(), second.deterministic_dict())
		self.assertEqual(before, after)

	def test_api_access_is_restricted(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				api.discover_purchasing()
			with self.assertRaises(frappe.PermissionError):
				api.list_process_models()
			with self.assertRaises(frappe.PermissionError):
				api.reconstruct_purchasing("_Test Company", "2026-09-01", "2026-09-29")
			with self.assertRaises(frappe.PermissionError):
				api.get_reconstruction("reconstruction-not-authorized")
			with self.assertRaises(frappe.PermissionError):
				api.list_reconstructions()
		finally:
			frappe.set_user("Administrator")

	def test_real_site_transaction_reconstruction_is_bounded_deterministic_and_read_only(self):
		scope = TransactionScope("_Test Company", "2026-09-01", "2026-09-29")
		before = _transaction_fingerprint(scope)
		snapshot = capture_snapshot()
		first = reconstruct_purchasing_transactions(scope, snapshot=snapshot)
		second = reconstruct_purchasing_transactions(scope, snapshot=snapshot)
		after = _transaction_fingerprint(scope)
		self.assertEqual(first.deterministic_dict(), second.deterministic_dict())
		self.assertEqual(before, after)
		self.assertTrue(first.events)
		self.assertTrue(all(not item.source_locator.endswith("/_Test Company") for item in first.evidence))
		self.assertEqual(first.metrics["process_cycle_time"], "DATA_NOT_AVAILABLE")


def _configuration_fingerprint():
	payload = {}
	for doctype, order_by in (
		("Workflow", "name asc"),
		("Workflow Document State", "parent asc, idx asc, name asc"),
		("Workflow Transition", "parent asc, idx asc, name asc"),
		("Assignment Rule", "name asc"),
		("Notification", "name asc"),
		("Client Script", "name asc"),
		("Server Script", "name asc"),
	):
		if frappe.db.table_exists(doctype):
			payload[doctype] = frappe.get_all(doctype, fields="*", order_by=order_by, ignore_permissions=True)
	return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def _transaction_fingerprint(scope: TransactionScope):
	payload = {}
	for doctype in (
		"Material Request",
		"Request for Quotation",
		"Supplier Quotation",
		"Purchase Order",
		"Purchase Receipt",
		"Purchase Invoice",
		"Payment Entry",
	):
		if frappe.db.table_exists(doctype):
			payload[doctype] = frappe.get_all(
				doctype,
				filters={
					"company": scope.company,
					"creation": [
						"between",
						[f"{scope.start_date} 00:00:00", f"{scope.end_date} 23:59:59.999999"],
					],
				},
				fields=["name", "creation", "modified", "docstatus"],
				order_by="creation asc, name asc",
				ignore_permissions=True,
			)
	return hashlib.sha256(canonical_json(payload).encode()).hexdigest()
