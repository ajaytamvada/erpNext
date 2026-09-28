import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.pridict.page.pridict_sales import pridict_sales


class TestPridictSales(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_guest_cannot_load_sales(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_sales.get_overview()

	def test_overview_uses_a_permitted_company(self):
		result = pridict_sales.get_overview()
		self.assertTrue(result.get("companies"))
		self.assertIn(result["filters"]["company"], {company.name for company in result["companies"]})

	def test_overview_returns_sales_contract(self):
		result = pridict_sales.get_overview()
		self.assertEqual(
			set(result["metrics"]),
			{"open_opportunities", "active_quotations", "orders_to_deliver", "orders_to_bill"},
		)
		self.assertEqual(set(result["create_permissions"]), set(pridict_sales.SALES_DOCTYPES))
		self.assertEqual([row["doctype"] if isinstance(row, dict) else row.doctype for row in result["pipeline"]], list(pridict_sales.SALES_DOCTYPES))
