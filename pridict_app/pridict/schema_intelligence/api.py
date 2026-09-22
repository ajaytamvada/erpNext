from __future__ import annotations

import frappe
from frappe.utils import cint

from pridict.schema_intelligence.service import (
	capture_and_persist_snapshot,
	capture_snapshot as capture_snapshot_service,
	compare_persisted_snapshots,
	get_doctype_schema as get_doctype_schema_service,
	get_default_repository,
	get_snapshot_overview as get_snapshot_overview_service,
	list_snapshot_summaries,
	snapshot_summary,
)


def _require_access():
	if frappe.session.user == "Guest":
		raise frappe.PermissionError
	frappe.only_for("System Manager")


@frappe.whitelist()
def capture_snapshot(persist: int | str = 0, allow_incomplete: int | str = 0):
	"""Capture effective metadata; optionally persist the explicitly requested snapshot."""
	_require_access()
	if cint(persist):
		snapshot = capture_and_persist_snapshot(require_complete=not cint(allow_incomplete))
	else:
		snapshot = capture_snapshot_service()
	return snapshot.to_dict()


@frappe.whitelist()
def capture_and_persist(allow_incomplete: int | str = 0):
	"""Capture and persist a snapshot, returning an operator-friendly summary."""
	_require_access()
	snapshot = capture_and_persist_snapshot(require_complete=not cint(allow_incomplete))
	return snapshot_summary(snapshot)


def capture_summary():
	"""Return a concise summary for trusted operator use through bench execute."""
	snapshot = capture_snapshot_service()
	return {**snapshot_summary(snapshot), "diagnostics": [item.to_dict() for item in snapshot.diagnostics]}


@frappe.whitelist()
def get_snapshot(snapshot_id: str):
	_require_access()
	return get_default_repository().load(snapshot_id).to_dict()


@frappe.whitelist()
def list_snapshots():
	_require_access()
	return list_snapshot_summaries()


@frappe.whitelist()
def get_snapshot_overview(snapshot_id: str):
	_require_access()
	return get_snapshot_overview_service(snapshot_id)


@frappe.whitelist()
def get_doctype_schema(snapshot_id: str, doctype: str):
	_require_access()
	return get_doctype_schema_service(snapshot_id, doctype)


@frappe.whitelist()
def compare_snapshots(before_snapshot_id: str, after_snapshot_id: str):
	_require_access()
	return compare_persisted_snapshots(before_snapshot_id, after_snapshot_id)
