import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.pridict.page.pridict_inventory import pridict_inventory


class TestPridictInventory(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_guest_cannot_load_inventory(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_inventory.get_overview()

	def test_overview_returns_inventory_contract(self):
		result = pridict_inventory.get_overview()
		self.assertEqual(set(result["metrics"]), {"stock_items", "warehouses", "draft_stock_entries", "pending_pick_lists"})
		self.assertEqual(set(result["create_permissions"]), set(pridict_inventory.INVENTORY_DOCTYPES))
		self.assertEqual(len(result["reports"]), 4)
