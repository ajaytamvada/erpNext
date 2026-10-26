"""Hand-written example specs. Phase 5 turns these into the starter templates."""

from __future__ import annotations

import json
import os

import frappe

EXAMPLES_DIR = os.path.dirname(__file__)
EXAMPLES = (
	"s1_short_stock_rfq",
	"s2_overdue_invoice_reminders",
	"s3_supplier_onboarding",
	"s4_po_approval",
	"s5_email_to_sales_order",
	"s6_weekly_receipt_summary",
)


def load_example(key: str) -> dict:
	with open(os.path.join(EXAMPLES_DIR, f"{key}.json"), encoding="utf-8") as handle:
		return json.load(handle)


def install(key: str = "s3_supplier_onboarding", activate: bool = False, run_as: str | None = None) -> str:
	"""Create (or refresh) an Automation from an example spec. For dev benches and tests:

	bench --site <site> execute pridict.automation.examples.install --kwargs "{'activate': True}"
	"""
	spec = load_example(key)
	name = frappe.db.get_value("Automation", {"title": spec["title"]})
	doc = frappe.get_doc("Automation", name) if name else frappe.new_doc("Automation")
	doc.update(
		{
			"title": spec["title"],
			"description": spec.get("description"),
			"draft_spec": json.dumps(spec, indent=1, ensure_ascii=False),
		}
	)
	if run_as:
		doc.run_as = run_as
	doc.save()
	if activate:
		doc.activate("Installed from example", require_test=False)
	elif doc.status == "Active":
		doc.pause("Reinstalled from example")
	return doc.name
