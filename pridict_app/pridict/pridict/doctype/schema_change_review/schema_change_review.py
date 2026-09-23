import frappe
from frappe.model.document import Document

IMMUTABLE_FIELDS = {"baseline_snapshot", "candidate_snapshot", "comparison_hash"}
VALID_TRANSITIONS = {
	"Open": {"Acknowledged", "Approved", "Rejected"},
	"Acknowledged": {"Approved", "Rejected"},
	"Approved": set(),
	"Rejected": set(),
}


class SchemaChangeReview(Document):
	def validate(self):
		if self.is_new():
			return
		previous = self.get_doc_before_save()
		if not previous:
			return
		if any(previous.get(fieldname) != self.get(fieldname) for fieldname in IMMUTABLE_FIELDS):
			frappe.throw("Comparison inputs are immutable after a review is created.")
		if previous.status != self.status and self.status not in VALID_TRANSITIONS.get(previous.status, set()):
			frappe.throw(f"Invalid review transition from {previous.status} to {self.status}.")
		if previous.status != self.status and not frappe.flags.in_schema_review_transition:
			frappe.throw("Use the Schema Intelligence review actions to change status.")
		previous_comments = [(row.commented_at, row.commented_by, row.comment_type, row.comment) for row in previous.comments]
		current_prefix = [
			(row.commented_at, row.commented_by, row.comment_type, row.comment)
			for row in self.comments[: len(previous_comments)]
		]
		if previous_comments != current_prefix or len(self.comments) < len(previous_comments):
			frappe.throw("Review comments are append-only.")
