import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.pridict.page.pridict_finance import pridict_finance


class TestPridictFinance(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_guest_cannot_load_finance(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_finance.get_overview()

	def test_overview_uses_a_permitted_company(self):
		result = pridict_finance.get_overview()
		self.assertTrue(result.get("companies"))
		self.assertIn(result["filters"]["company"], {company.name for company in result["companies"]})

	def test_overview_returns_finance_contract(self):
		result = pridict_finance.get_overview()
		self.assertEqual(
			set(result["metrics"]),
			{"revenue", "expenses", "overdue_receivables", "overdue_payables"},
		)
		self.assertEqual(set(result["create_permissions"]), set(pridict_finance.FINANCE_DOCTYPES))
		self.assertGreaterEqual(len(result["reports"]), 6)
