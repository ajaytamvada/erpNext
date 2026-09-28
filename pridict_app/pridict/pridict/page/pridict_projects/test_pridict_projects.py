import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.pridict.page.pridict_projects import pridict_projects


class TestPridictProjects(FrappeTestCase):
	def test_guest_cannot_load_projects(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_projects.get_overview()
		frappe.set_user("Administrator")

	def test_overview_contract(self):
		frappe.set_user("Administrator")
		result = pridict_projects.get_overview()
		self.assertEqual(set(result["metrics"]), {"open_projects", "overdue_tasks", "draft_timesheets", "unbilled_timesheets"})
		self.assertEqual(set(result["create_permissions"]), set(pridict_projects.PROJECT_DOCTYPES))
