"""Hand-written example specs. Phase 5 turns these into the starter templates."""

from __future__ import annotations

import json
import os

import frappe

EXAMPLES_DIR = os.path.dirname(__file__)


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
			"run_as": run_as or doc.run_as or frappe.session.user,
			"status": "Active" if activate else "Draft",
		}
	)
	doc.save()
	return doc.name
