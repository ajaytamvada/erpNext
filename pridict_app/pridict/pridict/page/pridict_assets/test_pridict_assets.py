import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.pridict.page.pridict_assets import pridict_assets


class TestPridictAssets(FrappeTestCase):
	def test_guest_cannot_load_assets(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_assets.get_overview()
		frappe.set_user("Administrator")

	def test_overview_contract(self):
		frappe.set_user("Administrator")
		result = pridict_assets.get_overview()
		self.assertEqual(set(result["metrics"]), {"operating_assets", "assets_in_maintenance", "pending_repairs", "draft_movements"})
		self.assertEqual(set(result["create_permissions"]), set(pridict_assets.ASSET_DOCTYPES))
