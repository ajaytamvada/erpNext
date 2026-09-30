from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from pridict.process_intelligence.schema_adapter import PURCHASING_CANDIDATES, PurchasingSchemaView
from pridict.process_intelligence.transaction_models import TransactionScope


CHILD_DOCTYPES = (
	"Material Request Item",
	"Request for Quotation Item",
	"Supplier Quotation Item",
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
	"Payment Entry Reference",
)

CHILD_PARENT_DOCTYPES = {
	"Material Request Item": "Material Request",
	"Request for Quotation Item": "Request for Quotation",
	"Supplier Quotation Item": "Supplier Quotation",
	"Purchase Order Item": "Purchase Order",
	"Purchase Receipt Item": "Purchase Receipt",
	"Purchase Invoice Item": "Purchase Invoice",
	"Payment Entry Reference": "Payment Entry",
}

DOCUMENT_FIELDS = (
	"name",
	"creation",
	"owner",
	"modified",
	"modified_by",
	"docstatus",
	"status",
	"workflow_state",
	"company",
	"is_return",
	"return_against",
	"amended_from",
)

CHILD_FIELDS = (
	"name",
	"parent",
	"parenttype",
	"idx",
	"qty",
	"stock_qty",
	"received_qty",
	"allocated_amount",
	"reference_doctype",
	"reference_name",
	"material_request",
	"material_request_item",
	"request_for_quotation",
	"supplier_quotation",
	"supplier_quotation_item",
	"purchase_order",
	"purchase_order_item",
	"purchase_receipt",
	"purchase_receipt_item",
	"po_detail",
	"pr_detail",
)


class TransactionSource(Protocol):
	def get_records(
		self,
		doctype: str,
		*,
		filters: dict[str, Any] | None = None,
		fields: tuple[str, ...] = (),
		order_by: str = "creation asc, name asc",
		limit: int = 0,
	) -> list[dict[str, Any]]: ...

	def has_doctype(self, doctype: str) -> bool: ...


class FrappeTransactionSource:
	STANDARD_FIELDS = {
		"name",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
		"idx",
		"parent",
		"parentfield",
		"parenttype",
	}

	def get_records(
		self,
		doctype: str,
		*,
		filters: dict[str, Any] | None = None,
		fields: tuple[str, ...] = (),
		order_by: str = "creation asc, name asc",
		limit: int = 0,
	) -> list[dict[str, Any]]:
		import frappe

		if not frappe.db.table_exists(doctype):
			return []
		available = {field.fieldname for field in frappe.get_meta(doctype).fields} | self.STANDARD_FIELDS
		selected = [field for field in fields if field in available] or ["name"]
		return [
			dict(row)
			for row in frappe.get_all(
				doctype,
				filters=filters or {},
				fields=selected,
				order_by=order_by,
				limit_page_length=limit,
				ignore_permissions=True,
			)
		]

	def has_doctype(self, doctype: str) -> bool:
		import frappe

		return bool(frappe.db.table_exists(doctype))


def collect_transactions(
	schema: PurchasingSchemaView,
	scope: TransactionScope,
	source: TransactionSource,
	*,
	collected_at: str | None = None,
) -> dict[str, Any]:
	documents: dict[str, list[dict[str, Any]]] = {}
	for doctype in schema.doctype_names:
		documents[doctype] = source.get_records(
			doctype,
			filters={
				"company": scope.company,
				"creation": ["between", [f"{scope.start_date} 00:00:00", f"{scope.end_date} 23:59:59.999999"]],
			},
			fields=DOCUMENT_FIELDS,
			limit=scope.max_records_per_doctype,
		)
	document_names = {row["name"] for rows in documents.values() for row in rows}
	children: dict[str, list[dict[str, Any]]] = {}
	for doctype in CHILD_DOCTYPES:
		parent_doctype = CHILD_PARENT_DOCTYPES[doctype]
		parent_names = sorted(row["name"] for row in documents.get(parent_doctype, []))
		if not source.has_doctype(doctype) or not parent_names:
			continue
		children[doctype] = source.get_records(
			doctype,
			filters={"parent": ["in", parent_names], "parenttype": parent_doctype},
			fields=CHILD_FIELDS,
			order_by="parent asc, idx asc, name asc",
			limit=scope.max_records_per_doctype,
		)
	versions = source.get_records(
		"Version",
		filters={
			"ref_doctype": ["in", list(PURCHASING_CANDIDATES)],
			"docname": ["in", sorted(document_names)],
		},
		fields=("name", "ref_doctype", "docname", "data", "creation", "owner"),
		limit=scope.max_records_per_doctype,
	) if document_names and source.has_doctype("Version") else []
	workflow_actions = source.get_records(
		"Workflow Action",
		filters={
			"reference_doctype": ["in", list(PURCHASING_CANDIDATES)],
			"reference_name": ["in", sorted(document_names)],
		},
		fields=(
			"name",
			"reference_doctype",
			"reference_name",
			"workflow_state",
			"status",
			"completed_by",
			"creation",
			"modified",
		),
		limit=scope.max_records_per_doctype,
	) if document_names and source.has_doctype("Workflow Action") else []
	return {
		"collected_at": collected_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
		"documents": documents,
		"children": children,
		"versions": versions,
		"workflow_actions": workflow_actions,
	}
