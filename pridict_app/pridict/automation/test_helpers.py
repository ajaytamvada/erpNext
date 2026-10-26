"""Shared fixtures for automation tests. Tests run against whatever company the site has."""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from pridict.automation import guards, triggers
from pridict.automation.examples import install

MANAGER = "_test_automation_pm@example.com"
TEST_EMAIL_ACCOUNT = "_Test Automation Outgoing"


class AutomationTestCase(FrappeTestCase):
	"""Enables automations, blocks commits and cleans the caches that outlive a rollback."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# In tests Frappe sends some emails at once and the Email Queue commits its status.
		# Block commits so everything here is rolled back.
		commit = patch.object(frappe.db, "commit")
		commit.start()
		cls.addClassCleanup(commit.stop)
		cls.addClassCleanup(reset_caches)
		settings = frappe.get_single("Automation Settings")
		settings.update({"enabled": 1, "pause_all": 0, "max_failures_before_pause": 5, "max_chain_depth": 3})
		settings.save()
		ensure_email_account()
		ensure_manager()
		reset_caches()

	def setUp(self):
		clear_counters()


def reset_caches():
	# Redis caches survive the test rollback: drop the trigger index and cached settings.
	triggers.clear_index()
	frappe.clear_document_cache(guards.SETTINGS, guards.SETTINGS)
	clear_counters()


def clear_counters():
	frappe.cache().delete_keys(guards.COUNTER_PREFIX)


def ensure_email_account():
	if not frappe.db.exists("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}):
		# Emails need a default outgoing account to queue (SMTP is not contacted in tests).
		frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_account_name": TEST_EMAIL_ACCOUNT,
				"email_id": "automation-test@example.com",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"smtp_server": "smtp.example.com",
				"password": "password",
			}
		).insert()


def ensure_manager():
	if not frappe.db.exists("User", MANAGER):
		user = frappe.get_doc(
			{"doctype": "User", "email": MANAGER, "first_name": "Automation PM", "send_welcome_email": 0}
		).insert()
		user.add_roles("Purchase Manager", "Sales Manager", "Accounts User")


def spec_automation(spec: dict, *, activate: bool = True, run_as: str = "Administrator", **values) -> str:
	"""Create an Automation from a spec dict (optionally activated)."""
	doc = frappe.get_doc(
		{
			"doctype": "Automation",
			"title": spec.get("title") or "Test automation",
			"draft_spec": json.dumps(spec),
			"run_as": run_as,
			**values,
		}
	).insert()
	if activate:
		doc.activate("test", require_test=False)
	return doc.name


def manual_spec(nodes: list[dict], edges: list[dict], title: str = "Manual test", **settings) -> dict:
	return {
		"schema": 1,
		"title": title,
		"trigger": {"id": "trigger", "type": "trigger.manual", "config": {}, "position": [0, 0]},
		"nodes": nodes,
		"edges": edges,
		"settings": {"on_error": "stop_and_notify", "max_steps": 200, **settings},
	}


def install_example(key: str, activate: bool = True) -> str:
	return install(key, activate=activate, run_as="Administrator")


def steps(run: str) -> dict:
	return {step.node_id: step for step in frappe.get_doc("Agent Run", run).steps}


def step_list(run: str) -> list[str]:
	return [step.node_id for step in frappe.get_doc("Agent Run", run).steps]


# ---------------------------------------------------------------------------
# ERPNext records


def company() -> str:
	return (
		frappe.defaults.get_global_default("company") or frappe.get_all("Company", pluck="name", limit=1)[0]
	)


def warehouse(company_name: str) -> str:
	return frappe.db.get_value("Warehouse", {"company": company_name, "is_group": 0, "disabled": 0}, "name")


def leaf(doctype: str) -> str:
	return frappe.db.get_value(doctype, {"is_group": 0}, "name") or frappe.db.get_value(doctype, {}, "name")


def make_supplier(name: str, email: str | None = None) -> str:
	if frappe.db.exists("Supplier", name):
		return name
	supplier = frappe.get_doc(
		{"doctype": "Supplier", "supplier_name": name, "supplier_group": "All Supplier Groups"}
	).insert()
	if email:
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": name,
				"email_ids": [{"email_id": email, "is_primary": 1}],
				"links": [{"link_doctype": "Supplier", "link_name": supplier.name}],
			}
		).insert()
		supplier.db_set({"supplier_primary_contact": contact.name, "email_id": email})
	return supplier.name


def make_item(code: str, *, stock: bool = True, suppliers: list[str] | None = None) -> str:
	if frappe.db.exists("Item", code):
		return code
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": code,
			"item_name": code,
			"item_group": leaf("Item Group"),
			"stock_uom": "Nos",
			"is_stock_item": 1 if stock else 0,
			"supplier_items": [{"supplier": supplier} for supplier in suppliers or []],
		}
	).insert()
	return code


def make_material_request(item_code: str, qty: float = 5) -> str:
	company_name = company()
	schedule = add_days(nowdate(), 7)
	doc = frappe.get_doc(
		{
			"doctype": "Material Request",
			"material_request_type": "Purchase",
			"company": company_name,
			"transaction_date": nowdate(),
			"schedule_date": schedule,
			"items": [
				{
					"item_code": item_code,
					"qty": qty,
					"schedule_date": schedule,
					"warehouse": warehouse(company_name),
					"uom": "Nos",
					"conversion_factor": 1,
				}
			],
		}
	).insert()
	doc.submit()
	return doc.name


def make_purchase_order(supplier: str, item_code: str, rate: float, qty: float = 1) -> str:
	"""A draft Purchase Order (not submitted)."""
	company_name = company()
	schedule = add_days(nowdate(), 14)
	doc = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"supplier": supplier,
			"company": company_name,
			"transaction_date": nowdate(),
			"schedule_date": schedule,
			"items": [
				{
					"item_code": item_code,
					"qty": qty,
					"rate": rate,
					"schedule_date": schedule,
					"warehouse": warehouse(company_name),
				}
			],
		}
	).insert()
	return doc.name
