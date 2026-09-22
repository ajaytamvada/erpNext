import frappe
from frappe.tests.utils import FrappeTestCase


class TestSchemaIntelligencePage(FrappeTestCase):
	def test_page_is_restricted_to_system_managers(self):
		page = frappe.get_doc("Page", "schema-intelligence")

		self.assertEqual(page.title, "Schema Intelligence")
		self.assertEqual(page.standard, "Yes")
		self.assertEqual({row.role for row in page.roles}, {"System Manager"})
