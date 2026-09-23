import frappe
from frappe.model.document import Document


IMMUTABLE_FIELDS = {
	"snapshot_id", "metadata_hash", "captured_at", "frappe_version", "erpnext_version",
	"completeness", "doctype_count", "field_count", "relationship_count", "permission_count",
	"warning_count", "error_count", "capture_origin", "capture_actor", "repository_identifier",
}


class SchemaSnapshotRecord(Document):
	def validate(self):
		if self.is_new():
			return
		previous = self.get_doc_before_save()
		if previous and any(previous.get(fieldname) != self.get(fieldname) for fieldname in IMMUTABLE_FIELDS):
			frappe.throw("Immutable snapshot identity and capture fields cannot be changed.")
