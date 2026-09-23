from frappe.model.document import Document
from frappe.utils import cint


class SchemaIntelligenceSettings(Document):
	def validate(self):
		self.retention_max_count = max(cint(self.retention_max_count or 30), 1)
		self.retention_max_age_days = max(cint(self.retention_max_age_days or 90), 1)
		self.graph_node_limit = min(max(cint(self.graph_node_limit or 100), 10), 500)
		self.graph_edge_limit = min(max(cint(self.graph_edge_limit or 250), 10), 2000)
		self.max_findings_per_review = min(max(cint(self.max_findings_per_review or 5000), 100), 10000)
