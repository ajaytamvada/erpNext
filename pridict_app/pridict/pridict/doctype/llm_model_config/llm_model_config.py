import frappe
from frappe import _
from frappe.model.document import Document


class LLMModelConfig(Document):
	def validate(self):
		if self.temperature is not None and not 0 <= self.temperature <= 2:
			frappe.throw(_("Temperature must be between 0 and 2."))
		for field, label in (("max_tokens", _("Max Output Tokens")), ("timeout_s", _("Timeout"))):
			if (self.get(field) or 0) <= 0:
				frappe.throw(_("{0} must be greater than zero.").format(label))
		if (self.retries or 0) < 0:
			frappe.throw(_("Retries cannot be negative."))
		self.validate_fallback_chain()

	def validate_fallback_chain(self):
		"""Reject a fallback that points back to this configuration (directly or through others)."""
		seen = {self.name}
		current = self.fallback
		while current:
			if current in seen:
				frappe.throw(_("Fallback chain loops back to {0}.").format(frappe.bold(current)))
			seen.add(current)
			current = frappe.db.get_value("LLM Model Config", current, "fallback")
