import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.pridict.page.pridict_support import pridict_support


class TestPridictSupport(FrappeTestCase):
	def test_guest_cannot_load_support(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_support.get_overview()
		frappe.set_user("Administrator")

	def test_overview_contract(self):
		frappe.set_user("Administrator")
		result = pridict_support.get_overview()
		self.assertEqual(
			set(result["metrics"]),
			{"open_issues", "sla_due", "open_warranty_claims", "active_slas"},
		)
		self.assertEqual(set(result["create_permissions"]), set(pridict_support.SUPPORT_DOCTYPES))
		self.assertEqual(
			{report["route"] for report in result["reports"]},
			{
				"query-report/Issue Analytics",
				"query-report/Issue Summary",
				"query-report/First Response Time for Issues",
			},
		)
