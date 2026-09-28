import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.pridict.page.pridict_manufacturing import pridict_manufacturing


class TestPridictManufacturing(FrappeTestCase):
	def test_guest_cannot_load_manufacturing(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_manufacturing.get_overview()
		frappe.set_user("Administrator")

	def test_overview_contract(self):
		frappe.set_user("Administrator")
		result = pridict_manufacturing.get_overview()
		self.assertEqual(set(result["metrics"]), {"active_boms", "open_plans", "open_work_orders", "open_job_cards"})
		self.assertEqual(set(result["create_permissions"]), set(pridict_manufacturing.DOCTYPES))
