import json

import frappe
from frappe import _
from frappe.model.document import Document

from pridict.automation import spec as specs
from pridict.automation import triggers


class Automation(Document):
	def before_insert(self):
		if not self.run_as:
			self.run_as = frappe.session.user

	def validate(self):
		spec = specs.load(self.draft_spec or "{}")
		spec.setdefault("title", self.title)
		self.draft_spec = json.dumps(spec, indent=1, ensure_ascii=False)
		self.update(specs.trigger_summary(spec))
		if self.status == "Active":
			errors = [issue["message"] for issue in specs.validate(spec) if issue["level"] == "error"]
			if errors:
				frappe.throw(
					_("Fix these problems before activating:")
					+ "<br>"
					+ "<br>".join(map(frappe.bold, errors))
				)
		if self.has_value_changed("draft_spec"):
			self.draft_revision = (self.draft_revision or 0) + 1

	def on_update(self):
		triggers.clear_index()

	def on_trash(self):
		triggers.clear_index()
