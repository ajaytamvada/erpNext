from frappe.model.document import Document


class AgentRun(Document):
	def validate(self):
		request = " ".join((self.request or "").split())
		self.request_summary = request if len(request) <= 140 else request[:137] + "..."
