from __future__ import annotations

import frappe
from frappe.utils import cint

from pridict.schema_intelligence.exports import (
	export_comparison as export_comparison_service,
	export_findings_csv as export_findings_csv_service,
	export_review as export_review_service,
	export_snapshot_summary as export_snapshot_summary_service,
	export_subgraph as export_subgraph_service,
	future_analysis_payload as future_analysis_payload_service,
)
from pridict.schema_intelligence.governance import (
	delete_snapshot as delete_snapshot_service,
	get_settings as get_settings_service,
	index_snapshot,
	list_snapshot_records,
	promote_baseline as promote_baseline_service,
	update_settings as update_settings_service,
	update_snapshot_metadata,
)
from pridict.schema_intelligence.graph import relationship_subgraph
from pridict.schema_intelligence.notifications import notify_review
from pridict.schema_intelligence.reviews import (
	append_review_comment,
	create_review as create_review_service,
	get_review as get_review_service,
	list_findings as list_findings_service,
	list_reviews as list_reviews_service,
	promote_review_candidate,
	transition_review as transition_review_service,
)
from pridict.schema_intelligence.service import (
	capture_and_persist_snapshot,
	capture_snapshot as capture_snapshot_service,
	compare_persisted_snapshots,
	get_doctype_schema as get_doctype_schema_service,
	get_default_repository,
	get_snapshot_overview as get_snapshot_overview_service,
	snapshot_summary,
)


def _require_reviewer_access():
	if frappe.session.user == "Guest":
		raise frappe.PermissionError
	roles = set(frappe.get_roles())
	if not roles.intersection({"System Manager", "Schema Reviewer"}):
		raise frappe.PermissionError


def _require_manager_access():
	if frappe.session.user == "Guest":
		raise frappe.PermissionError
	frappe.only_for("System Manager")


@frappe.whitelist()
def capture_snapshot(persist: int | str = 0, allow_incomplete: int | str = 0):
	"""Capture effective metadata; optionally persist the explicitly requested snapshot."""
	_require_manager_access()
	if cint(persist):
		snapshot = capture_and_persist_snapshot(require_complete=not cint(allow_incomplete))
		index_snapshot(snapshot, origin="Manual")
	else:
		snapshot = capture_snapshot_service()
	return snapshot.to_dict()


@frappe.whitelist()
def capture_and_persist(allow_incomplete: int | str = 0):
	"""Capture and persist a snapshot, returning an operator-friendly summary."""
	_require_manager_access()
	snapshot = capture_and_persist_snapshot(require_complete=not cint(allow_incomplete))
	index_snapshot(snapshot, origin="Manual")
	return snapshot_summary(snapshot)


def capture_summary():
	"""Return a concise summary for trusted operator use through bench execute."""
	snapshot = capture_snapshot_service()
	return {**snapshot_summary(snapshot), "diagnostics": [item.to_dict() for item in snapshot.diagnostics]}


@frappe.whitelist()
def get_snapshot(snapshot_id: str):
	_require_manager_access()
	return get_default_repository().load(snapshot_id).to_dict()


@frappe.whitelist()
def list_snapshots():
	_require_reviewer_access()
	return list_snapshot_records()


@frappe.whitelist()
def get_snapshot_overview(snapshot_id: str):
	_require_reviewer_access()
	return get_snapshot_overview_service(snapshot_id)


@frappe.whitelist()
def get_doctype_schema(snapshot_id: str, doctype: str):
	_require_reviewer_access()
	return get_doctype_schema_service(snapshot_id, doctype)


@frappe.whitelist()
def compare_snapshots(before_snapshot_id: str, after_snapshot_id: str):
	_require_reviewer_access()
	return compare_persisted_snapshots(before_snapshot_id, after_snapshot_id)


@frappe.whitelist()
def get_settings():
	_require_manager_access()
	return get_settings_service()


@frappe.whitelist()
def update_settings(values):
	_require_manager_access()
	return update_settings_service(frappe.parse_json(values) if isinstance(values, str) else values)


@frappe.whitelist()
def update_snapshot(snapshot_id: str, label: str | None = None, note: str | None = None, lifecycle_state: str | None = None):
	_require_manager_access()
	return update_snapshot_metadata(snapshot_id, label=label, note=note, lifecycle_state=lifecycle_state)


@frappe.whitelist()
def delete_snapshot(snapshot_id: str, confirmed: int | str = 0):
	_require_manager_access()
	return delete_snapshot_service(snapshot_id, confirmed=bool(cint(confirmed)))


@frappe.whitelist()
def promote_baseline(snapshot_id: str, confirmed: int | str = 0):
	_require_manager_access()
	if not cint(confirmed):
		frappe.throw("Baseline promotion requires explicit confirmation.")
	return promote_baseline_service(snapshot_id)


@frappe.whitelist()
def create_review(baseline_snapshot_id: str, candidate_snapshot_id: str):
	_require_reviewer_access()
	return create_review_service(baseline_snapshot_id, candidate_snapshot_id)


@frappe.whitelist()
def list_reviews():
	_require_reviewer_access()
	return list_reviews_service()


@frappe.whitelist()
def get_review(review_name: str):
	_require_reviewer_access()
	return get_review_service(review_name)


@frappe.whitelist()
def list_findings(review_name: str, severity: str | None = None, category: str | None = None, start: int | str = 0, page_length: int | str = 100):
	_require_reviewer_access()
	return list_findings_service(review_name, severity=severity, category=category, start=cint(start), page_length=cint(page_length))


@frappe.whitelist()
def transition_review(review_name: str, status: str, comment: str | None = None):
	_require_reviewer_access()
	return transition_review_service(review_name, status, comment)


@frappe.whitelist()
def add_review_comment(review_name: str, comment: str):
	_require_reviewer_access()
	return append_review_comment(review_name, "Comment", comment)


@frappe.whitelist()
def promote_review_baseline(review_name: str, confirmed: int | str = 0):
	_require_manager_access()
	if not cint(confirmed):
		frappe.throw("Baseline promotion requires explicit confirmation.")
	return promote_review_candidate(review_name)


@frappe.whitelist()
def get_relationship_subgraph(snapshot_id: str, root_doctype: str, hops: int | str = 1, direction: str = "both", relationship_types=None):
	_require_reviewer_access()
	settings = get_settings_service()
	snapshot = get_default_repository().load(snapshot_id)
	types = frappe.parse_json(relationship_types) if isinstance(relationship_types, str) else relationship_types
	return relationship_subgraph(
		snapshot,
		root_doctype,
		hops=cint(hops),
		direction=direction,
		relationship_types=set(types or []),
		node_limit=settings["graph_node_limit"],
		edge_limit=settings["graph_edge_limit"],
	)


@frappe.whitelist()
def export_snapshot_summary(snapshot_id: str):
	_require_reviewer_access()
	return export_snapshot_summary_service(snapshot_id)


@frappe.whitelist()
def export_comparison(review_name: str):
	_require_reviewer_access()
	return export_comparison_service(review_name)


@frappe.whitelist()
def export_review(review_name: str):
	_require_reviewer_access()
	return export_review_service(review_name)


@frappe.whitelist()
def export_findings_csv(review_name: str):
	_require_reviewer_access()
	return export_findings_csv_service(review_name)


@frappe.whitelist()
def export_subgraph(snapshot_id: str, root_doctype: str, hops: int | str = 1, direction: str = "both", relationship_types=None, format: str = "json"):
	_require_reviewer_access()
	types = frappe.parse_json(relationship_types) if isinstance(relationship_types, str) else relationship_types
	return export_subgraph_service(snapshot_id, root_doctype, hops=cint(hops), direction=direction, relationship_types=types, format=format)


@frappe.whitelist()
def get_future_analysis_payload(review_name: str):
	_require_reviewer_access()
	return future_analysis_payload_service(review_name)


@frappe.whitelist()
def retry_review_notification(review_name: str):
	_require_reviewer_access()
	return notify_review(review_name)
