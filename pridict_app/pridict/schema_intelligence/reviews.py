from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import cint, now_datetime

from pridict.schema_intelligence.classification import SEVERITY_ORDER, classify_changes
from pridict.schema_intelligence.governance import index_existing_snapshots, promote_baseline
from pridict.schema_intelligence.normalization import canonical_json
from pridict.schema_intelligence.service import get_default_repository

VALID_TRANSITIONS = {
	"Open": {"Acknowledged", "Approved", "Rejected"},
	"Acknowledged": {"Approved", "Rejected"},
	"Approved": set(),
	"Rejected": set(),
}


def create_review(baseline_snapshot_id: str, candidate_snapshot_id: str):
	if baseline_snapshot_id == candidate_snapshot_id:
		frappe.throw("Baseline and candidate snapshots must be different.")
	index_existing_snapshots()
	repository = get_default_repository()
	comparison = classify_changes(repository.load(baseline_snapshot_id), repository.load(candidate_snapshot_id))
	existing = frappe.db.get_value("Schema Change Review", {"comparison_hash": comparison["comparison_hash"]}, "name")
	if existing:
		return get_review(existing)

	settings = frappe.get_single("Schema Intelligence Settings")
	maximum = min(max(cint(settings.max_findings_per_review or 5000), 100), 10000)
	repository_identifier = _save_comparison(comparison)
	doc = frappe.get_doc(
		{
			"doctype": "Schema Change Review",
			"baseline_snapshot": baseline_snapshot_id,
			"candidate_snapshot": candidate_snapshot_id,
			"comparison_hash": comparison["comparison_hash"],
			"status": "Open",
			"critical_count": comparison["severity_totals"]["critical"],
			"warning_count": comparison["severity_totals"]["warning"],
			"information_count": comparison["severity_totals"]["information"],
			"unresolved_count": len(comparison["findings"]),
			"findings_truncated": len(comparison["findings"]) > maximum,
			"comparison_repository_identifier": repository_identifier,
		}
	)
	for finding in comparison["findings"][:maximum]:
		doc.append("findings", _finding_row(finding))
	doc.append("comments", _comment_row("Comment", "Review created from deterministic comparison."))
	doc.insert(ignore_permissions=True)
	frappe.db.set_value("Schema Snapshot Record", candidate_snapshot_id, "review_status", "Open")
	return get_review(doc.name)


def get_review(review_name: str) -> dict[str, Any]:
	doc = frappe.get_doc("Schema Change Review", review_name)
	return {
		**doc.as_dict(),
		"findings": [row.as_dict() for row in doc.findings],
		"comments": [row.as_dict() for row in doc.comments],
	}


def list_reviews() -> list[dict[str, Any]]:
	return frappe.get_all(
		"Schema Change Review",
		fields=["name", "baseline_snapshot", "candidate_snapshot", "status", "critical_count", "warning_count", "information_count", "unresolved_count", "reviewer", "creation", "baseline_promoted"],
		order_by="creation desc",
	)


def list_findings(review_name: str, *, severity: str | None = None, category: str | None = None, start: int = 0, page_length: int = 100):
	doc = frappe.get_doc("Schema Change Review", review_name)
	findings = _load_comparison(doc.comparison_repository_identifier)["findings"]
	if severity:
		findings = [item for item in findings if item["severity"] == severity.lower()]
	if category:
		findings = [item for item in findings if item["category"] == category]
	start = max(cint(start), 0)
	page_length = min(max(cint(page_length), 1), 250)
	return {"total": len(findings), "items": findings[start : start + page_length]}


def transition_review(review_name: str, status: str, comment: str | None = None):
	doc = frappe.get_doc("Schema Change Review", review_name)
	if status not in VALID_TRANSITIONS.get(doc.status, set()):
		frappe.throw(f"Invalid review transition from {doc.status} to {status}.")
	if status in {"Approved", "Rejected"} and doc.owner == frappe.session.user:
		frappe.throw("The review creator cannot make the final approval decision.")
	doc.status = status
	doc.reviewer = frappe.session.user
	if status == "Acknowledged":
		doc.acknowledged_at = now_datetime()
	else:
		doc.decided_at = now_datetime()
	doc.append("comments", _comment_row("Status Change", comment or f"Status changed to {status}."))
	frappe.flags.in_schema_review_transition = True
	try:
		doc.save(ignore_permissions=True)
	finally:
		frappe.flags.in_schema_review_transition = False
	frappe.db.set_value("Schema Snapshot Record", doc.candidate_snapshot, "review_status", status)
	return get_review(doc.name)


def append_review_comment(review_name: str, comment_type: str, comment: str):
	if not comment or not comment.strip():
		frappe.throw("A review comment is required.")
	doc = frappe.get_doc("Schema Change Review", review_name)
	doc.append("comments", _comment_row(comment_type, comment.strip()))
	frappe.flags.in_schema_review_transition = True
	try:
		doc.save(ignore_permissions=True)
	finally:
		frappe.flags.in_schema_review_transition = False
	return get_review(doc.name)


def promote_review_candidate(review_name: str):
	doc = frappe.get_doc("Schema Change Review", review_name)
	if doc.status != "Approved":
		frappe.throw("Only an approved review can promote its candidate snapshot.")
	return promote_baseline(doc.candidate_snapshot, review_name=doc.name)


def comparison_payload(review_name: str) -> dict[str, Any]:
	doc = frappe.get_doc("Schema Change Review", review_name)
	return _load_comparison(doc.comparison_repository_identifier)


def highest_severity(review) -> str | None:
	for severity, count in (("critical", review.critical_count), ("warning", review.warning_count), ("information", review.information_count)):
		if cint(count):
			return severity
	return None


def meets_threshold(severity: str | None, threshold: str) -> bool:
	if not severity:
		return False
	return SEVERITY_ORDER[severity.lower()] >= SEVERITY_ORDER[threshold.lower()]


def _finding_row(finding: dict[str, Any]) -> dict[str, Any]:
	return {
		"finding_id": finding["finding_id"],
		"rule_id": finding["rule_id"],
		"severity": finding["severity"],
		"category": finding["category"],
		"affected_path": finding["path"],
		"affected_doctype": finding.get("doctype"),
		"affected_field": finding.get("fieldname"),
		"explanation": finding["explanation"],
		"before_value": canonical_json(finding.get("before")),
		"after_value": canonical_json(finding.get("after")),
		"provenance": canonical_json(finding.get("provenance", [])),
	}


def _comment_row(comment_type: str, comment: str) -> dict[str, Any]:
	return {"commented_at": now_datetime(), "commented_by": frappe.session.user or "Administrator", "comment_type": comment_type, "comment": comment}


def _comparison_root() -> Path:
	return Path(frappe.get_site_path("private", "files", "pridict-schema-intelligence", "reviews"))


def _save_comparison(comparison: dict[str, Any]) -> str:
	root = _comparison_root()
	root.mkdir(parents=True, exist_ok=True)
	filename = f"{comparison['comparison_hash']}.json"
	target = root / filename
	if target.exists():
		return filename
	file_descriptor, temporary_name = tempfile.mkstemp(prefix=".comparison-", suffix=".tmp", dir=root)
	try:
		with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
			handle.write(json.dumps(comparison, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
			handle.flush()
			os.fsync(handle.fileno())
		os.replace(temporary_name, target)
	except Exception:
		if os.path.exists(temporary_name):
			os.unlink(temporary_name)
		raise
	return filename


def _load_comparison(identifier: str) -> dict[str, Any]:
	if not identifier or Path(identifier).name != identifier:
		frappe.throw("Invalid comparison repository identifier.")
	path = _comparison_root() / identifier
	with path.open(encoding="utf-8") as handle:
		return json.load(handle)
