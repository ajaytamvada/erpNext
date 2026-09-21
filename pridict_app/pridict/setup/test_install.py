import frappe
from frappe.email.email_body import get_footer, get_formatted_html
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch

from pridict.email import get_welcome_email_subject
from pridict.setup.install import (
	FOOTER_POWERED,
	SUPPORT_LABEL,
	SUPPORT_ROUTE,
	UPSTREAM_HELP_ROUTES,
	_remove_upstream_links_from_html,
	apply_branding,
)


class TestBrandingInstall(FrappeTestCase):
	def assert_no_upstream_branding(self, content):
		self.assertNotIn("ERPNext", content)
		self.assertNotIn("Powered by", content)
		self.assertNotIn("frappe.io/erpnext", content)

	def test_branding_reconciliation_is_idempotent(self):
		apply_branding()
		apply_branding()

		self.assertEqual(frappe.db.get_single_value("Website Settings", "app_name"), "Pridict")
		self.assertEqual(frappe.db.get_single_value("Website Settings", "footer_powered"), FOOTER_POWERED)
		self.assertEqual(frappe.db.get_default("disable_standard_email_footer"), "1")

		help_items = frappe.get_all(
			"Navbar Item",
			filters={
				"parent": "Navbar Settings",
				"parentfield": "help_dropdown",
				"route": ["in", sorted(UPSTREAM_HELP_ROUTES)],
			},
			fields=["hidden"],
		)
		self.assertTrue(help_items)
		self.assertTrue(all(row.hidden for row in help_items))
		support_items = frappe.get_all(
			"Navbar Item",
			filters={
				"parent": "Navbar Settings",
				"parentfield": "help_dropdown",
				"item_label": SUPPORT_LABEL,
				"is_standard": 0,
			},
			fields=["route", "hidden"],
		)
		self.assertEqual(len(support_items), 1)
		self.assertEqual(support_items[0].route, SUPPORT_ROUTE)
		self.assertFalse(support_items[0].hidden)

		self.assertFalse(
			frappe.get_all(
				"Workspace Shortcut",
				filters={"url": ["like", "%school.frappe.io%"]},
				limit_page_length=1,
			)
		)

	def test_standard_email_footer_is_removed(self):
		apply_branding()
		footer = get_footer(None)
		self.assert_no_upstream_branding(footer)

	def test_contextual_help_links_are_removed_without_losing_text(self):
		html = (
			'Choose <a href="https://docs.erpnext.com/docs/user/manual/example" target="_blank">'
			"the documented option</a>."
		)
		self.assertEqual(
			_remove_upstream_links_from_html(html),
			"Choose the documented option.",
		)

		apply_branding()
		for doctype, fieldname in (
			("Payment Reconciliation", "default_advance_account"),
			("Process Payment Reconciliation", "default_advance_account"),
			("Item", "valuation_method"),
			("Stock Settings", "valuation_method"),
		):
			self.assertFalse(
				frappe.db.get_value(
					"DocField",
					{"parent": doctype, "fieldname": fieldname},
					"documentation_url",
				)
			)

		for tour in ("Selling Settings", "Stock Entry", "Stock Settings"):
			descriptions = frappe.get_all(
				"Form Tour Step",
				filters={"parent": tour},
				pluck="description",
			)
			self.assertFalse(any("docs.erpnext.com" in (description or "") for description in descriptions))

	def test_public_footer_links_to_approved_support_address(self):
		footer = frappe.get_template("templates/includes/footer/footer_powered.html").render()
		self.assertIn("Pridict", footer)
		self.assertIn(SUPPORT_ROUTE, footer)

	def test_welcome_email_uses_tenant_or_pridict_name(self):
		with patch("frappe.defaults.get_global_default", return_value=None):
			self.assertEqual(get_welcome_email_subject(), "Welcome to Pridict")

		with patch("frappe.defaults.get_global_default", return_value="Example Company"):
			self.assertEqual(get_welcome_email_subject(), "Welcome to Example Company")

	def test_welcome_email_capture_has_no_upstream_branding(self):
		apply_branding()
		user = frappe.get_doc("User", "test1@example.com")

		with patch("frappe.sendmail") as sendmail:
			user.send_welcome_mail_to_user()

		message = sendmail.call_args.kwargs
		self.assertNotIn("ERPNext", message["subject"])
		self.assertNotIn("Frappe", message["subject"])
		self.assertEqual(message["template"], "new_user")
		self.assertEqual(message["recipients"], user.email)

	def test_representative_system_email_templates_have_no_upstream_branding(self):
		apply_branding()
		messages = (
			(
				"Password Reset",
				"password_reset",
				{
					"first_name": "Pridict",
					"last_name": "User",
					"link": "https://example.invalid/update-password",
					"created_by": "Administrator",
				},
			),
			(
				"You've been invited to join Pridict",
				"user_invitation",
				{"title": "Pridict", "invite_link": "https://example.invalid/invitation"},
			),
			(
				"Pridict notification",
				"new_notification",
				{
					"body_content": "A document needs your attention.",
					"description": "",
					"doc_link": "https://example.invalid/app/document",
					"message": "",
				},
			),
		)

		outgoing_account = frappe._dict(brand_logo=None, footer=None, add_signature=0)
		with patch("frappe.email.email_body.EmailAccount.find_outgoing", return_value=outgoing_account):
			for subject, template, args in messages:
				body = frappe.get_template(f"templates/emails/{template}.html").render(args)
				html = get_formatted_html(subject, body, header=[subject, "blue"])
				self.assert_no_upstream_branding(html)
