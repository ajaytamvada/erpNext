import frappe
from frappe import _
from frappe.model.document import Document


class AgentRun(Document):
	def validate(self):
		if not self.agent and not self.automation:
			frappe.throw(_("An Agent Run belongs to an agent or an automation."))
		request = " ".join((self.request or "").split())
		self.request_summary = request if len(request) <= 140 else request[:137] + "..."
