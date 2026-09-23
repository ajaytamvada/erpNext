from __future__ import annotations

from datetime import timedelta, timezone
from typing import Any

import frappe
from frappe.utils import cint, convert_utc_to_system_timezone, get_datetime, now_datetime

from pridict.schema_intelligence.service import get_default_repository, snapshot_summary

SETTINGS_DOCTYPE = "Schema Intelligence Settings"
SNAPSHOT_DOCTYPE = "Schema Snapshot Record"
OPEN_REVIEW_STATUSES = ("Open", "Acknowledged")
DEFAULT_SETTINGS = {
	"scheduler_enabled": 0,
	"capture_cadence": "Weekly",
	"capture_time": "02:00:00",
	"comparison_target": "Pinned Baseline",
	"retention_enabled": 0,
	"retention_max_count": 30,
	"retention_max_age_days": 90,
	"notification_enabled": 0,
	"notification_minimum_severity": "Warning",
	"notification_users": "",
	"notification_roles": "",
	"graph_node_limit": 100,
	"graph_edge_limit": 250,
	"max_findings_per_review": 5000,
}


def get_settings() -> dict[str, Any]:
	settings = frappe.get_single(SETTINGS_DOCTYPE)
	return {key: settings.get(key) if settings.get(key) is not None else value for key, value in DEFAULT_SETTINGS.items()} | {
		"last_capture_status": settings.last_capture_status,
		"last_capture_at": settings.last_capture_at,
		"last_capture_message": settings.last_capture_message,
		"last_snapshot": settings.last_snapshot,
	}


def update_settings(values: dict[str, Any]) -> dict[str, Any]:
	settings = frappe.get_single(SETTINGS_DOCTYPE)
	for fieldname in DEFAULT_SETTINGS:
		if fieldname in values:
			settings.set(fieldname, values[fieldname])
	settings.save(ignore_permissions=True)
	return get_settings()


def index_snapshot(snapshot, *, origin: str, actor: str | None = None):
	if frappe.db.exists(SNAPSHOT_DOCTYPE, snapshot.snapshot_id):
		return frappe.get_doc(SNAPSHOT_DOCTYPE, snapshot.snapshot_id)
	summary = snapshot_summary(snapshot)
	summary["captured_at"] = _get_database_datetime(snapshot.captured_at)
	doc = frappe.get_doc(
		{
			"doctype": SNAPSHOT_DOCTYPE,
			**summary,
			"capture_origin": origin,
			"capture_actor": actor or frappe.session.user or "Administrator",
			"repository_identifier": f"{snapshot.snapshot_id}.json",
			"lifecycle_state": "Retained",
			"review_status": "Unreviewed",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def _get_database_datetime(value):
	datetime_value = get_datetime(value)
	if datetime_value.tzinfo is None:
		return datetime_value
	utc_value = datetime_value.astimezone(timezone.utc)
	return convert_utc_to_system_timezone(utc_value).replace(tzinfo=None)


def index_existing_snapshots() -> dict[str, int]:
	repository = get_default_repository()
	indexed = 0
	failed = 0
	for snapshot_id in repository.list_ids():
		if not frappe.db.exists(SNAPSHOT_DOCTYPE, snapshot_id):
			try:
				index_snapshot(repository.load(snapshot_id), origin="Indexed", actor=frappe.session.user)
				indexed += 1
			except Exception:
				failed += 1
				frappe.log_error(title=f"Schema Intelligence could not index snapshot {snapshot_id}")
	return {"indexed": indexed, "failed": failed, "total": len(repository.list_ids())}


def list_snapshot_records() -> list[dict[str, Any]]:
	return frappe.get_all(
		SNAPSHOT_DOCTYPE,
		fields=[
			"name", "snapshot_id", "label", "metadata_hash", "captured_at", "completeness",
			"capture_origin", "capture_actor", "lifecycle_state", "is_baseline", "review_status",
			"doctype_count", "field_count", "relationship_count", "warning_count", "error_count",
		],
		order_by="captured_at desc",
	)


def update_snapshot_metadata(snapshot_id: str, *, label: str | None = None, note: str | None = None, lifecycle_state: str | None = None):
	doc = frappe.get_doc(SNAPSHOT_DOCTYPE, snapshot_id)
	if label is not None:
		doc.label = label.strip()
	if note is not None:
		doc.note = note.strip()
	if lifecycle_state is not None:
		if lifecycle_state not in {"Retained", "Archived", "Deletion Eligible"}:
			frappe.throw("Unsupported snapshot lifecycle state.")
		doc.lifecycle_state = lifecycle_state
	doc.save(ignore_permissions=True)
	return doc.as_dict()


def promote_baseline(snapshot_id: str, *, review_name: str | None = None):
	doc = frappe.get_doc(SNAPSHOT_DOCTYPE, snapshot_id)
	if doc.completeness != "complete":
		frappe.throw("Only complete snapshots can be promoted to baseline.")
	current_baseline = frappe.db.get_value(SNAPSHOT_DOCTYPE, {"is_baseline": 1}, "name")
	if current_baseline and current_baseline != snapshot_id and not review_name:
		frappe.throw("Replacing an existing baseline requires an approved review.")
	if review_name:
		review = frappe.get_doc("Schema Change Review", review_name)
		if review.status != "Approved" or review.candidate_snapshot != snapshot_id:
			frappe.throw("The selected snapshot must belong to an approved review.")
	frappe.db.set_value(SNAPSHOT_DOCTYPE, {"is_baseline": 1}, "is_baseline", 0, update_modified=False)
	frappe.db.set_value(SNAPSHOT_DOCTYPE, snapshot_id, {"is_baseline": 1, "lifecycle_state": "Retained"})
	if review_name:
		frappe.db.set_value("Schema Change Review", review_name, "baseline_promoted", 1)
		from pridict.schema_intelligence.reviews import append_review_comment

		append_review_comment(review_name, "Baseline Promotion", f"Promoted {snapshot_id} to baseline.")
	return frappe.get_doc(SNAPSHOT_DOCTYPE, snapshot_id).as_dict()


def delete_snapshot(snapshot_id: str, *, confirmed: bool = False) -> dict[str, Any]:
	if not confirmed:
		frappe.throw("Snapshot deletion requires explicit confirmation.")
	doc = frappe.get_doc(SNAPSHOT_DOCTYPE, snapshot_id)
	if doc.is_baseline:
		frappe.throw("A pinned baseline cannot be deleted.")
	if _has_open_review(snapshot_id):
		frappe.throw("A snapshot referenced by an open review cannot be deleted.")
	if doc.completeness == "complete" and frappe.db.count(SNAPSHOT_DOCTYPE, {"completeness": "complete"}) <= 1:
		frappe.throw("The only complete snapshot cannot be deleted.")
	get_default_repository().delete(snapshot_id)
	frappe.delete_doc(SNAPSHOT_DOCTYPE, snapshot_id, ignore_permissions=True)
	return {"deleted": snapshot_id}


def apply_retention(settings: dict[str, Any] | None = None) -> dict[str, Any]:
	settings = settings or get_settings()
	if not cint(settings.get("retention_enabled")):
		return {"enabled": False, "deleted": [], "eligible": []}
	max_count = max(cint(settings.get("retention_max_count")), 1)
	max_age_days = max(cint(settings.get("retention_max_age_days")), 1)
	records = frappe.get_all(
		SNAPSHOT_DOCTYPE,
		filters={"is_baseline": 0},
		fields=["name", "captured_at", "completeness"],
		order_by="captured_at desc",
	)
	cutoff = now_datetime() - timedelta(days=max_age_days)
	eligible = []
	for index, record in enumerate(records):
		if _has_open_review(record.name):
			continue
		if index >= max_count and get_datetime(record.captured_at) < cutoff:
			eligible.append(record.name)
	deleted = []
	for snapshot_id in eligible:
		try:
			delete_snapshot(snapshot_id, confirmed=True)
			deleted.append(snapshot_id)
		except Exception:
			frappe.log_error(title="Schema Intelligence retention failure")
	return {"enabled": True, "eligible": eligible, "deleted": deleted}


def comparison_target_snapshot(policy: str, *, exclude_snapshot: str | None = None) -> str | None:
	filters: dict[str, Any] = {"completeness": "complete"}
	if policy == "Pinned Baseline":
		filters["is_baseline"] = 1
	rows = frappe.get_all(
		SNAPSHOT_DOCTYPE,
		filters=filters,
		pluck="name",
		order_by="captured_at desc",
		limit_page_length=2,
	)
	return next((name for name in rows if name != exclude_snapshot), None)


def _has_open_review(snapshot_id: str) -> bool:
	filters = {"status": ["in", OPEN_REVIEW_STATUSES]}
	return bool(
		frappe.db.exists("Schema Change Review", {**filters, "baseline_snapshot": snapshot_id})
		or frappe.db.exists("Schema Change Review", {**filters, "candidate_snapshot": snapshot_id})
	)
