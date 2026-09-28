import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.pridict.page.pridict_integrations import pridict_integrations


class TestPridictIntegrations(FrappeTestCase):
	def test_guest_cannot_load_integrations(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_integrations.get_overview()
		frappe.set_user("Administrator")

	def test_overview_contract(self):
		frappe.set_user("Administrator")
		result = pridict_integrations.get_overview()
		self.assertEqual(
			set(result["metrics"]),
			{"webhooks", "oauth_clients", "social_login_providers", "google_calendars"},
		)
		self.assertEqual(set(result["create_permissions"]), set(pridict_integrations.INTEGRATION_DOCTYPES))
		self.assertEqual(len(result["groups"]), 4)
