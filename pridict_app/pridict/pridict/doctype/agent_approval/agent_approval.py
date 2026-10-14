import frappe
from frappe import _
from frappe.model.document import Document


class AgentApproval(Document):
	def validate(self):
		previous = self.get_doc_before_save()
		if previous and previous.status != "Pending" and previous.status != self.status:
			frappe.throw(
				_("This approval was already {0} and cannot change.").format(_(previous.status).lower())
			)
