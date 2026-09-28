import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.pridict.page.pridict_procurement import pridict_procurement


class TestPridictProcurement(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_guest_cannot_load_procurement(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_procurement.get_overview()

	def test_overview_uses_a_permitted_company(self):
		result = pridict_procurement.get_overview()
		self.assertTrue(result.get("companies"))
		self.assertIn(result["filters"]["company"], {company.name for company in result["companies"]})

	def test_overview_returns_purchasing_contract(self):
		result = pridict_procurement.get_overview()
		self.assertEqual(
			set(result["metrics"]),
			{
				"material_requests",
				"purchase_orders_to_receive",
				"purchase_orders_to_bill",
				"unpaid_purchase_invoices",
			},
		)
		self.assertEqual(set(result["create_permissions"]), set(pridict_procurement.PURCHASING_DOCTYPES))
		self.assertEqual([stage["doctype"] for stage in result["pipeline"]], list(pridict_procurement.PURCHASING_DOCTYPES))
