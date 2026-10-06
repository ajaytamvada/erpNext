"""Permission-aware live presentation of the existing reconstruction backend.

Raw document names exist only in this response; persisted reconstruction artifacts
remain pseudonymized. No business records or analysis artifacts are written here.
"""
from __future__ import annotations

from urllib.parse import quote

import frappe
from frappe import _

from pridict.process_intelligence.reconstruction import _identifier
from pridict.process_intelligence.schema_adapter import PURCHASING_CANDIDATES
from pridict.process_intelligence.service import reconstruct_purchasing_transactions, reconstruction_artifacts
from pridict.process_intelligence.transaction_collection import CHILD_PARENT_DOCTYPES, FrappeTransactionSource
from pridict.process_intelligence.transaction_models import TransactionScope
from pridict.schema_intelligence.service import capture_snapshot


SCREEN_LIMIT = 500
SCREEN_ROLES = ("System Manager", "Process Analyst")


def require_access():
	if frappe.session.user == "Guest" or not set(SCREEN_ROLES).intersection(frappe.get_roles()):
		frappe.throw(_("Process Intelligence requires the Process Analyst or System Manager role."), frappe.PermissionError)


class PermittedTransactionSource(FrappeTransactionSource):
	"""Use Frappe's list and per-document checks before collecting related rows."""

	def __init__(self):
		self.documents = {}
		self.excluded_types = set()

	def get_records(self, doctype, *, filters=None, fields=(), order_by="creation asc, name asc", limit=0):
		if doctype in PURCHASING_CANDIDATES:
			if not frappe.has_permission(doctype, "read"):
				self.excluded_types.add(doctype)
				return []
			available = {field.fieldname for field in frappe.get_meta(doctype).fields} | self.STANDARD_FIELDS
			filters = dict(filters or {})
			if doctype == "Material Request":
				filters["material_request_type"] = "Purchase"
			elif doctype == "Payment Entry":
				filters["party_type"] = "Supplier"
			rows = frappe.get_list(
				doctype, filters=filters or {}, fields=[field for field in fields if field in available],
				order_by=order_by, limit_page_length=limit,
			)
			permitted = []
			for row in rows:
				if frappe.has_permission(doctype, "read", doc=frappe.get_doc(doctype, row.name)):
					self.documents[(doctype, row.name)] = dict(row)
					permitted.append(dict(row))
			return permitted

		if doctype in CHILD_PARENT_DOCTYPES:
			parent_type = CHILD_PARENT_DOCTYPES[doctype]
			# Never allow callers to supply an arbitrary parent list to the bypassing base collector.
			parents = [name for kind, name in self.documents if kind == parent_type]
			if not parents:
				return []
			return super().get_records(
				doctype, filters={"parent": ["in", parents], "parenttype": parent_type},
				fields=fields, order_by=order_by, limit=limit,
			)

		if doctype not in {"Version", "Workflow Action"}:
			return []
		if not frappe.has_permission(doctype, "read"):
			self.excluded_types.add(doctype)
			return []
		rows = super().get_records(doctype, filters=filters, fields=fields, order_by=order_by, limit=limit)
		kind_field, name_field = (
			("ref_doctype", "docname") if doctype == "Version" else ("reference_doctype", "reference_name")
		)
		return [dict(row) for row in rows if (row.get(kind_field), row.get(name_field)) in self.documents
			and frappe.has_permission(doctype, "read", doc=frappe.get_doc(doctype, row["name"]))]


@frappe.whitelist()
def get_options():
	require_access()
	companies = frappe.get_list("Company", pluck="name", order_by="name asc", limit_page_length=0)
	return {
		"companies": companies,
		"default_company": frappe.defaults.get_user_default("Company"),
		"today": frappe.utils.today(),
		"timezone": frappe.utils.get_system_timezone(),
		"record_limit": SCREEN_LIMIT,
	}


@frappe.whitelist()
def get_analysis(company: str, start_date: str, end_date: str):
	require_access()
	try:
		scope = TransactionScope(company or "", start_date, end_date, SCREEN_LIMIT)
	except (TypeError, ValueError) as error:
		frappe.throw(str(error), frappe.ValidationError)
	if not frappe.get_list("Company", filters={"name": company}, pluck="name", limit_page_length=1):
		frappe.throw(_("You do not have access to the selected company."), frappe.PermissionError)

	source = PermittedTransactionSource()
	snapshot = capture_snapshot()
	result = reconstruct_purchasing_transactions(scope, snapshot=snapshot, transaction_source=source)
	response = reconstruction_artifacts(result)
	response["documents"] = {
		_identifier(snapshot.site_identifier_hash, "doc", doctype, name): {
			"doctype": doctype, "name": name,
			"url": f"/app/{frappe.scrub(doctype).replace('_', '-')}/{quote(name, safe='')}",
		}
		for doctype, name in source.documents
	}
	response["scope"] = {
		"company": company, "start_date": start_date, "end_date": end_date,
		"date_basis": "Document creation date", "timezone": frappe.utils.get_system_timezone(),
		"record_limit": SCREEN_LIMIT, "excluded_types": sorted(source.excluded_types),
	}
	return response
