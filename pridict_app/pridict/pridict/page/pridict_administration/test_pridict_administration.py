import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.pridict.page.pridict_administration import pridict_administration


class TestPridictAdministration(FrappeTestCase):
	def test_guest_cannot_load_administration(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_administration.get_overview()
		frappe.set_user("Administrator")

	def test_overview_contract(self):
		frappe.set_user("Administrator")
		result = pridict_administration.get_overview()
		self.assertEqual(
			set(result["metrics"]),
			{"enabled_users", "workflows", "notifications", "email_accounts"},
		)
		self.assertEqual(set(result["create_permissions"]), set(pridict_administration.ADMINISTRATION_DOCTYPES))
		self.assertEqual(len(result["groups"]), 4)
