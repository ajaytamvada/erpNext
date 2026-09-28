import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.pridict.page.pridict_quality import pridict_quality


class TestPridictQuality(FrappeTestCase):
	def test_guest_cannot_load_quality(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_quality.get_overview()
		frappe.set_user("Administrator")

	def test_overview_contract(self):
		frappe.set_user("Administrator")
		result = pridict_quality.get_overview()
		self.assertEqual(
			set(result["metrics"]),
			{"draft_inspections", "open_reviews", "open_actions", "open_non_conformance"},
		)
		self.assertEqual(set(result["create_permissions"]), set(pridict_quality.QUALITY_DOCTYPES))
		self.assertEqual(result["reports"][0]["route"], "query-report/Review")
