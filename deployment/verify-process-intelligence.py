"""Create and verify a real linked purchasing flow, ONLY on the named local test site.

Run with the bench Python from its directory. --seed is required to create fixtures.
No UAT connection, credentials or business data are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import unittest

import frappe

SITE = "process-intelligence.localhost"
COMPANY = "PI Demonstration"
OTHER_COMPANY = "PI Empty Company"
ANALYST = "pi.analyst@example.test"
BUYER = "pi.buyer@example.test"
DENIED = "pi.noaccess@example.test"
MANIFEST = (Path("sites") / SITE / "private" / "pi-demo.json").resolve()
OUTPUT = Path("/workspace/development/apps/erpnext/documentation/process-intelligence/evidence")


def guard():
	if frappe.local.site != SITE or not frappe.conf.get("allow_process_intelligence_demo"):
		raise RuntimeError("Demo is restricted to process-intelligence.localhost with explicit demo config.")


def create_user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc({
			"doctype": "User", "email": email, "first_name": email.split(".")[1].split("@")[0].title(),
			"send_welcome_email": 0, "user_type": "System User", "new_password": "Local-PI-Demo-2026!",
			"roles": [{"role": role} for role in roles],
		}).insert()
	if not frappe.db.exists("User Permission", {"user": email, "allow": "Company", "for_value": COMPANY}):
		frappe.get_doc({
			"doctype": "User Permission", "user": email, "allow": "Company", "for_value": COMPANY,
			"apply_to_all_doctypes": 1,
		}).insert()


def prepare_browser():
	guard()
	if not MANIFEST.exists() or not frappe.db.exists("Company", COMPANY):
		raise RuntimeError("Seed the complete isolated purchasing fixture before preparing browser access.")
	from frappe.desk.page.setup_wizard.setup_wizard import enable_setup_wizard_complete
	for app in ("frappe", "erpnext"):
		enable_setup_wizard_complete(app)
	create_user("pi.reviewer@example.test", ["System Manager", "Accounts Manager", "Stock Manager", "Purchase Manager", "Sales Manager", "Website Manager"])
	frappe.db.set_default("desktop:home_page", "workspace")
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
	frappe.db.commit()
	frappe.clear_cache()
	assert frappe.is_setup_complete()


def seed():
	guard()
	if MANIFEST.exists():
		return json.loads(MANIFEST.read_text())
	from erpnext.setup.setup_wizard.setup_wizard import setup_complete
	from erpnext.stock.doctype.material_request.material_request import make_request_for_quotation
	from erpnext.buying.doctype.request_for_quotation.request_for_quotation import make_supplier_quotation_from_rfq
	from erpnext.buying.doctype.supplier_quotation.supplier_quotation import make_purchase_order
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	frappe.flags.mute_emails = True
	if not frappe.db.exists("Company", COMPANY):
		setup_complete(frappe._dict(
			company_name=COMPANY, company_abbr="PID", currency="INR", country="India",
			chart_of_accounts="Standard", fy_start_date="2026-04-01", fy_end_date="2027-03-31",
			bank_account="PI Demo Bank", language="en", timezone="Asia/Kolkata",
		))
	if not frappe.db.exists("Company", OTHER_COMPANY):
		frappe.get_doc({
			"doctype": "Company", "company_name": OTHER_COMPANY, "abbr": "PIE",
			"default_currency": "INR", "country": "India", "chart_of_accounts": "Standard",
		}).insert()
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
	frappe.db.set_single_value("System Settings", "time_zone", "Asia/Kolkata")
	frappe.db.set_single_value("System Settings", "enable_onboarding", 0)
	frappe.db.set_single_value("System Settings", "enable_telemetry", 0)
	if not frappe.db.exists("Supplier", "PI Demo Supplier"):
		frappe.get_doc({"doctype": "Supplier", "supplier_name": "PI Demo Supplier", "supplier_group": "All Supplier Groups", "supplier_type": "Company"}).insert()
	if not frappe.db.exists("Item", "PI-DEMO-BOLT"):
		frappe.get_doc({
			"doctype": "Item", "item_code": "PI-DEMO-BOLT", "item_name": "Demonstration steel bolt",
			"item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 1,
			"valuation_rate": 100, "is_purchase_item": 1,
		}).insert()
	warehouse = frappe.db.get_value("Warehouse", {"company": COMPANY, "warehouse_name": "Stores"}, "name")
	assert warehouse
	today = frappe.utils.today()
	documents = []

	def submit(doc):
		doc.insert()
		doc.submit()
		documents.append({"doctype": doc.doctype, "name": doc.name})
		print(f"Submitted {doc.doctype}: {doc.name}", flush=True)
		return doc

	mr = submit(frappe.get_doc({
		"doctype": "Material Request", "company": COMPANY, "material_request_type": "Purchase",
		"transaction_date": today, "schedule_date": today,
		"items": [{"item_code": "PI-DEMO-BOLT", "qty": 10, "warehouse": warehouse, "schedule_date": today}],
	}))
	rfq = make_request_for_quotation(mr.name)
	rfq.append("suppliers", {"supplier": "PI Demo Supplier", "send_email": 0})
	rfq = submit(rfq)
	sq = make_supplier_quotation_from_rfq(rfq.name, for_supplier="PI Demo Supplier")
	for item in sq.items:
		item.rate = 100
	sq = submit(sq)
	po = submit(make_purchase_order(sq.name))
	pr = submit(make_purchase_receipt(po.name))
	pi = make_purchase_invoice(pr.name)
	pi.bill_no = "PI-DEMO-SUPPLIER-001"
	pi.bill_date = today
	pi = submit(pi)
	bank = frappe.db.get_value("Account", {"company": COMPANY, "account_type": "Bank", "is_group": 0}, "name")
	pe = get_payment_entry("Purchase Invoice", pi.name, bank_account=bank)
	pe.reference_no = "PI-DEMO-PAYMENT-001"
	pe.reference_date = today
	pe = submit(pe)
	create_user(ANALYST, ["Process Analyst", "Purchase User", "Stock User", "Accounts User"])
	create_user(BUYER, ["Process Analyst", "Purchase User"])
	create_user(DENIED, ["Purchase User"])
	frappe.db.commit()
	manifest = {"site": SITE, "company": COMPANY, "date": today, "documents": documents, "quantity": 10, "invoice_total": pi.grand_total}
	MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
	prepare_browser()
	return manifest


def fingerprint():
	from pridict.schema_intelligence.normalization import canonical_json
	from pridict.process_intelligence.schema_adapter import PURCHASING_CANDIDATES
	from pridict.process_intelligence.transaction_collection import CHILD_DOCTYPES
	types = (*PURCHASING_CANDIDATES, *CHILD_DOCTYPES, "GL Entry", "Stock Ledger Entry", "Payment Ledger Entry", "Version", "Workflow Action", "Workflow", "User Permission")
	payload = {kind: frappe.get_all(kind, fields="*", order_by="name asc") for kind in types}
	return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


class PurchasingScreenVerification(unittest.TestCase):
	def setUp(self):
		guard()
		frappe.set_user("Administrator")
		self.manifest = json.loads(MANIFEST.read_text())
		self.day = self.manifest["date"]

	def tearDown(self):
		frappe.db.rollback()
		frappe.set_user("Administrator")
		frappe.clear_cache()

	def analysis(self, company=COMPANY, start=None, end=None):
		from pridict.process_intelligence.purchasing_screen import get_analysis
		return get_analysis(company, start or self.day, end or self.day)

	def test_browser_setup_is_complete(self):
		self.assertTrue(frappe.is_setup_complete())
		self.assertNotEqual(frappe.db.get_default("desktop:home_page"), "setup-wizard")

	def test_complete_linked_flow_and_read_only_deterministic_reconstruction(self):
		from pridict.process_intelligence.transaction_models import ReconstructionResult
		before = fingerprint()
		first = self.analysis()
		second = self.analysis()
		self.assertEqual(before, fingerprint())
		self.assertEqual(ReconstructionResult.from_dict(first["reconstruction"]).deterministic_dict(), ReconstructionResult.from_dict(second["reconstruction"]).deterministic_dict())
		r = first["reconstruction"]
		self.assertEqual(len(first["documents"]), 7)
		self.assertEqual(len(r["instances"]), 1)
		self.assertEqual(len(r["instances"][0]["document_ids"]), 7)
		self.assertGreaterEqual(len(r["edges"]), 6)
		self.assertEqual(r["metrics"]["unlinked_document_count"], 0)
		self.assertEqual(r["metrics"]["over_allocation_edge_count"], 0)
		self.assertTrue(any(edge["relation_type"] == "PAYMENT_ALLOCATION" for edge in r["edges"]))
		for key in ("process_cycle_time", "approval_time", "waiting_time", "handoff_count"):
			self.assertEqual(r["metrics"][key], "DATA_NOT_AVAILABLE")
		for doc in self.manifest["documents"]:
			self.assertEqual(frappe.db.get_value(doc["doctype"], doc["name"], "docstatus"), 1)
			self.assertNotIn(doc["name"], json.dumps(r))
		invoice = next(doc["name"] for doc in self.manifest["documents"] if doc["doctype"] == "Purchase Invoice")
		self.assertEqual(frappe.db.get_value("Purchase Invoice", invoice, "outstanding_amount"), 0)
		OUTPUT.mkdir(parents=True, exist_ok=True)
		(OUTPUT / "analysis.json").write_text(json.dumps(first, indent=2, default=str) + "\n")
		(OUTPUT / "read-only.json").write_text(json.dumps({"before": before, "after": fingerprint(), "deterministic": True}, indent=2) + "\n")

	def test_ordinary_analyst_and_document_links(self):
		from pridict.process_intelligence.purchasing_screen import get_options
		frappe.set_user(ANALYST)
		self.assertNotIn("System Manager", frappe.get_roles())
		self.assertEqual(get_options()["companies"], [COMPANY])
		data = self.analysis()
		self.assertEqual(len(data["documents"]), 7)
		for doc in data["documents"].values():
			self.assertTrue(frappe.has_permission(doc["doctype"], "read", doc=frappe.get_doc(doc["doctype"], doc["name"])))
			self.assertTrue(doc["url"].startswith("/app/"))
		with self.assertRaises(frappe.PermissionError):
			self.analysis(OTHER_COMPANY)

	def test_guest_and_user_without_analysis_role_are_denied(self):
		from pridict.process_intelligence.purchasing_screen import get_options
		for user in ("Guest", DENIED):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				get_options()
			with self.assertRaises(frappe.PermissionError):
				self.analysis()

	def test_missing_document_permission_does_not_expose_payment(self):
		frappe.set_user(BUYER)
		self.assertFalse(frappe.has_permission("Payment Entry", "read"))
		data = self.analysis()
		self.assertNotIn("Payment Entry", [doc["doctype"] for doc in data["documents"].values()])
		self.assertIn("Payment Entry", data["scope"]["excluded_types"])
		payment_name = next(doc["name"] for doc in self.manifest["documents"] if doc["doctype"] == "Payment Entry")
		self.assertNotIn(payment_name, json.dumps(data))

	def test_empty_scope_and_invalid_dates(self):
		self.assertEqual(len(self.analysis(OTHER_COMPANY)["documents"]), 0)
		self.assertEqual(len(self.analysis(start="2000-01-01", end="2000-01-02")["documents"]), 0)
		with self.assertRaises(frappe.ValidationError):
			self.analysis(start="2026-10-02", end="2026-10-01")
		with self.assertRaises(frappe.ValidationError):
			self.analysis(start="invalid")

	def test_page_role_registration(self):
		page = frappe.get_doc("Page", "process-intelligence")
		self.assertEqual({row.role for row in page.roles}, {"System Manager", "Process Analyst"})

	def test_record_level_permission_hides_a_second_order(self):
		order = next(doc["name"] for doc in self.manifest["documents"] if doc["doctype"] == "Purchase Order")
		other = frappe.get_doc({
			"doctype": "Purchase Order", "company": COMPANY, "supplier": "PI Demo Supplier",
			"transaction_date": self.day, "schedule_date": self.day,
			"items": [{"item_code": "PI-DEMO-BOLT", "qty": 1, "rate": 100, "schedule_date": self.day}],
		}).insert()
		frappe.set_user(ANALYST)
		self.assertTrue(frappe.get_list("Purchase Order", filters={"name": other.name}, pluck="name"))
		frappe.set_user("Administrator")
		frappe.get_doc({
			"doctype": "User Permission", "user": ANALYST, "allow": "Purchase Order",
			"for_value": order, "apply_to_all_doctypes": 1,
		}).insert()
		frappe.clear_cache(user=ANALYST)
		frappe.set_user(ANALYST)
		self.assertFalse(frappe.has_permission("Purchase Order", "read", doc=other))
		data = self.analysis(end=max(self.day, frappe.utils.today()))
		self.assertNotIn(other.name, json.dumps(data))
		self.assertIn(order, [doc["name"] for doc in data["documents"].values()])

	def test_record_limit_is_reported_and_child_reads_cannot_escape_scope(self):
		from unittest.mock import patch
		from pridict.process_intelligence import purchasing_screen
		source = purchasing_screen.PermittedTransactionSource()
		self.assertEqual(source.get_records("Purchase Order Item", filters={"parent": ["like", "%"]}), [])
		with patch.object(purchasing_screen, "SCREEN_LIMIT", 1):
			data = self.analysis()
		self.assertEqual(data["scope"]["record_limit"], 1)
		self.assertTrue(any("POSSIBLE_TRUNCATION" in gap for gap in data["reconstruction"]["gaps"]))


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--seed", action="store_true")
	parser.add_argument("--prepare-browser", action="store_true")
	args = parser.parse_args()
	os.chdir(Path.cwd() / "sites")
	frappe.init(site=SITE)
	frappe.connect()
	try:
		guard()
		frappe.set_user("Administrator")
		if args.seed:
			seed()
		if args.prepare_browser:
			prepare_browser()
			print("Isolated demo browser setup is complete; purchasing documents unchanged.")
			return
		manifest = json.loads(MANIFEST.read_text())
		print(json.dumps(manifest, indent=2))
		OUTPUT.mkdir(parents=True, exist_ok=True)
		(OUTPUT / "fixture.json").write_text(json.dumps(manifest, indent=2) + "\n")
		with (OUTPUT / "integration-tests.txt").open("w") as stream:
			result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PurchasingScreenVerification))
		print((OUTPUT / "integration-tests.txt").read_text())
		if not result.wasSuccessful():
			raise SystemExit(1)
	finally:
		frappe.db.rollback()
		frappe.destroy()


if __name__ == "__main__":
	main()
