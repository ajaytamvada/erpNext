from __future__ import annotations

from datetime import timedelta

import frappe
from frappe.utils import cint, get_datetime, now_datetime

from pridict.schema_intelligence.governance import (
	apply_retention,
	comparison_target_snapshot,
	index_snapshot,
)
from pridict.schema_intelligence.notifications import notify_operational_warning, notify_review
from pridict.schema_intelligence.reviews import create_review
from pridict.schema_intelligence.service import capture_snapshot, get_default_repository, persist_snapshot

LOCK_NAME = "pridict:schema-intelligence:capture"


def hourly():
	if not frappe.db.exists("DocType", "Schema Intelligence Settings"):
		return
	settings = frappe.get_single("Schema Intelligence Settings")
	if not cint(settings.scheduler_enabled) or not _is_due(settings):
		return
	return run_scheduled_capture()


def run_scheduled_capture():
	settings = frappe.get_single("Schema Intelligence Settings")
	try:
		with frappe.cache.lock(LOCK_NAME, timeout=3600, blocking_timeout=0):
			return _capture(settings)
	except Exception as exc:
		if "lock" in exc.__class__.__name__.lower():
			return {"status": "already-running"}
		_update_status(settings, "Failed", str(exc))
		notify_operational_warning("Schema Intelligence scheduled capture failed", str(exc))
		frappe.log_error(title="Schema Intelligence scheduled capture failed")
		return {"status": "failed", "message": str(exc)}


def _capture(settings):
	target = comparison_target_snapshot(settings.comparison_target or "Pinned Baseline")
	snapshot = capture_snapshot()
	persist_snapshot(snapshot, require_complete=False)
	record = index_snapshot(snapshot, origin="Scheduled", actor="Administrator (Scheduled)")
	if snapshot.completeness != "complete":
		_update_status(settings, "Incomplete", "Scheduled capture completed with diagnostics.", snapshot.snapshot_id)
		notify_operational_warning(
			"Schema Intelligence scheduled capture was incomplete",
			f"Snapshot {snapshot.snapshot_id} was retained for diagnosis and was not reviewed or promoted.",
		)
		return {"status": "incomplete", "snapshot": record.name}
	review = None
	if target and target != snapshot.snapshot_id:
		before = get_default_repository().load(target)
		if before.metadata_hash != snapshot.metadata_hash:
			review = create_review(target, snapshot.snapshot_id)
			notify_review(review["name"])
	retention = apply_retention()
	_update_status(settings, "Success", "Scheduled capture completed.", snapshot.snapshot_id)
	return {"status": "success", "snapshot": record.name, "review": review and review["name"], "retention": retention}


def _is_due(settings) -> bool:
	now = now_datetime()
	configured = get_datetime(f"{now.date()} {settings.capture_time or '02:00:00'}")
	if now < configured:
		return False
	if not settings.last_capture_at:
		return True
	last = get_datetime(settings.last_capture_at)
	minimum = timedelta(days=1 if settings.capture_cadence == "Daily" else 7)
	return now - last >= minimum


def _update_status(settings, status: str, message: str, snapshot_id: str | None = None):
	settings.last_capture_status = status
	settings.last_capture_at = now_datetime()
	settings.last_capture_message = message[:1000]
	if snapshot_id:
		settings.last_snapshot = snapshot_id
	settings.save(ignore_permissions=True)
