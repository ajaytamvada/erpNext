"""Acceptance scenarios S1 and S2 from the design, end to end on real ERPNext documents."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate

from pridict.automation import engine, triggers
from pridict.automation.test_helpers import (
	MANAGER,
	AutomationTestCase,
	company,
	install_example,
	make_item,
	make_material_request,
	make_supplier,
	step_list,
)


class TestS1ShortStockRFQ(AutomationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.automation = install_example("s1_short_stock_rfq")

	def run_for(self, material_request: str) -> str:
		trigger = {"event": "on_submit", "doctype": "Material Request", "name": material_request}
		return engine.start_run(self.automation, trigger, now=True)

	def test_short_items_get_a_submitted_rfq_and_an_email(self):
		supplier = make_supplier("_Test S1 Supplier", "quotes@s1-supplier.example")
		item = make_item("_Test S1 Sheet", suppliers=[supplier])
		material_request = make_material_request(item, qty=5)
		run = self.run_for(material_request)
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(doc.status, "Completed", doc.error)
		self.assertEqual(
			step_list(run),
			[
				"stock",
				"short",
				"item_suppliers",
				"suppliers",
				"has_suppliers",
				"rfq",
				"has_emails",
				"email_suppliers",
			],
		)
		rfq_name = frappe.db.get_value(
			"Request for Quotation Item", {"material_request": material_request}, "parent"
		)
		rfq = frappe.get_doc("Request for Quotation", rfq_name)
		self.assertEqual(rfq.docstatus, 1)
		self.assertEqual([s.supplier for s in rfq.suppliers], [supplier])
		self.assertEqual(rfq.suppliers[0].email_id, "quotes@s1-supplier.example")
		self.assertEqual(rfq.owner, "Administrator")
		email = frappe.db.get_value(
			"Email Queue",
			{"reference_doctype": "Material Request", "reference_name": material_request},
			"name",
		)
		self.assertTrue(email)
		recipients = frappe.get_all("Email Queue Recipient", filters={"parent": email}, pluck="recipient")
		self.assertEqual(recipients, ["quotes@s1-supplier.example"])

	def test_items_without_suppliers_notify_purchase_managers(self):
		item = make_item("_Test S1 Orphan Sheet")
		material_request = make_material_request(item, qty=3)
		run = self.run_for(material_request)
		self.assertEqual(frappe.db.get_value("Agent Run", run, "status"), "Completed")
		self.assertEqual(
			step_list(run), ["stock", "short", "item_suppliers", "suppliers", "has_suppliers", "no_suppliers"]
		)
		self.assertTrue(
			frappe.db.exists(
				"Notification Log",
				{"for_user": MANAGER, "subject": ["like", f"%{material_request}%no approved suppliers%"]},
			)
		)

	def test_trigger_condition_skips_other_request_types(self):
		item = make_item("_Test S1 Transfer Sheet")
		material_request = make_material_request(item)
		doc = frappe.get_doc("Material Request", material_request)
		with patch.object(engine, "start_run") as start:
			triggers.on_doc_event(doc, "on_submit")
			start.assert_called_once()
			doc.material_request_type = "Material Transfer"
			triggers.on_doc_event(doc, "on_submit")
			start.assert_called_once()


class TestS2OverdueReminders(AutomationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.automation = install_example("s2_overdue_invoice_reminders")

	def make_overdue_invoice(self, customer: str, email: str | None) -> str:
		company_name = company()
		item = make_item("_Test S2 Service", stock=False)
		posting = add_days(nowdate(), -10)
		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": company_name,
				"customer": customer,
				"set_posting_time": 1,
				"posting_date": posting,
				"due_date": add_days(nowdate(), -7),
				"contact_email": email,
				"items": [{"item_code": item, "qty": 1, "rate": 100}],
			}
		)
		invoice.insert()
		invoice.submit()
		return invoice.name

	def make_customer(self, name: str, account_manager: str | None = None) -> str:
		if not frappe.db.exists("Customer", name):
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": name,
					"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
					"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
					"account_manager": account_manager,
				}
			).insert()
		return name

	def test_loop_emails_each_customer_and_notifies_managers(self):
		with_manager = self.make_customer("_Test S2 Customer A", MANAGER)
		without = self.make_customer("_Test S2 Customer B")
		first = self.make_overdue_invoice(with_manager, "billing@s2-a.example")
		second = self.make_overdue_invoice(without, None)
		run = engine.start_run(self.automation, {"event": "schedule"}, now=True)
		doc = frappe.get_doc("Agent Run", run)
		self.assertEqual(doc.status, "Completed", doc.error)
		self.assertEqual(
			frappe.db.get_value("Email Queue Recipient", {"recipient": "billing@s2-a.example"}, "status"),
			"Not Sent",
		)
		self.assertTrue(
			frappe.db.exists(
				"Notification Log",
				{"for_user": MANAGER, "document_type": "Sales Invoice", "document_name": first},
			)
		)
		self.assertFalse(
			frappe.db.exists("Notification Log", {"document_type": "Sales Invoice", "document_name": second})
		)
		steps = step_list(run)
		self.assertEqual(steps[0], "overdue")
		self.assertEqual(steps[-1], "each_invoice")
		self.assertGreaterEqual(steps.count("remind"), 1)
