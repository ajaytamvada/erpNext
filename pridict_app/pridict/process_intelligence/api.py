from __future__ import annotations

import frappe

from pridict.process_intelligence.service import (
	analyze_and_persist_purchasing,
	analyze_purchasing,
	get_default_repository,
	get_reconstruction_repository,
	process_artifacts,
	reconstruct_and_persist_purchasing,
	reconstruct_purchasing_transactions,
	reconstruction_artifacts,
)
from pridict.process_intelligence.transaction_models import TransactionScope


def _require_manager_access() -> None:
	if frappe.session.user == "Guest":
		raise frappe.PermissionError
	frappe.only_for("System Manager")


@frappe.whitelist()
def discover_purchasing(snapshot_id: str | None = None, persist: int | str = 0):
	"""Discover configured purchasing evidence without reading transactions or mutating ERP data."""
	_require_manager_access()
	if frappe.utils.cint(persist):
		model = analyze_and_persist_purchasing(snapshot_id=snapshot_id)
	else:
		model = analyze_purchasing(snapshot_id=snapshot_id)
	return process_artifacts(model)


@frappe.whitelist()
def get_process_model(process_id: str):
	_require_manager_access()
	return process_artifacts(get_default_repository().load(process_id))


@frappe.whitelist()
def list_process_models():
	_require_manager_access()
	return get_default_repository().list_ids()


@frappe.whitelist()
def reconstruct_purchasing(
	company: str,
	start_date: str,
	end_date: str,
	max_records_per_doctype: int | str = 5000,
	persist: int | str = 0,
):
	_require_manager_access()
	scope = TransactionScope(
		company=company,
		start_date=start_date,
		end_date=end_date,
		max_records_per_doctype=frappe.utils.cint(max_records_per_doctype),
	)
	result = (
		reconstruct_and_persist_purchasing(scope)
		if frappe.utils.cint(persist)
		else reconstruct_purchasing_transactions(scope)
	)
	return reconstruction_artifacts(result)


@frappe.whitelist()
def get_reconstruction(reconstruction_id: str):
	_require_manager_access()
	return reconstruction_artifacts(get_reconstruction_repository().load(reconstruction_id))


@frappe.whitelist()
def list_reconstructions():
	_require_manager_access()
	return get_reconstruction_repository().list_ids()
