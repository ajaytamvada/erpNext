import frappe
from frappe.tests.utils import FrappeTestCase

from pridict import __version__
from pridict.website import get_notices_context, get_release_notes_context


class TestPridictWebsite(FrappeTestCase):
	def test_notices_context_exposes_truthful_product_details(self):
		context = get_notices_context(frappe._dict())
		self.assertEqual(context.pridict_version, __version__)
		self.assertEqual(context.support_email, "pavan@riditstack.com")
		self.assertEqual(context.title, "Pridict notices")

	def test_release_notes_context_exposes_installed_version(self):
		context = get_release_notes_context(frappe._dict())
		self.assertEqual(context.pridict_version, __version__)
		self.assertEqual(context.support_email, "pavan@riditstack.com")
		self.assertEqual(context.title, "Pridict release notices")
