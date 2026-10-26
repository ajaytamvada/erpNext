"""Metadata and permission checks shared by node types (used by live validation)."""

from __future__ import annotations

import frappe
from frappe.model import child_table_fields, default_fields

from pridict.automation.nodes import Issue

# Fields every DocType has, beyond those in its meta (child tables add parent fields).
STANDARD_FIELDS = frozenset({*default_fields, *child_table_fields, "name"})


def is_expression(value) -> bool:
	return isinstance(value, str) and ("{{" in value or "{%" in value)


def doctype_issues(
	doctype, run_as: str | None, ptype: str = "read", *, for_create=False, parent_doctype=None
) -> list[Issue]:
	"""The DocType exists, suits the action, and the Run As user has the permission.

	Child tables are allowed only for reads that name their parent_doctype; permission is
	then checked on the parent.
	"""
	if not doctype or is_expression(doctype):
		return []
	if not frappe.db.exists("DocType", doctype):
		return [Issue("error", f"DocType {doctype!r} does not exist.")]
	meta = frappe.get_meta(doctype)
	issues = []
	if for_create and (meta.issingle or meta.istable or meta.is_virtual):
		issues.append(Issue("error", f"{doctype} documents cannot be created by an automation."))
		return issues
	checked = doctype
	if meta.istable:
		if not parent_doctype:
			return [Issue("error", f"{doctype} is a child table; set its parent DocType.")]
		if not frappe.db.exists("DocType", parent_doctype):
			return [Issue("error", f"DocType {parent_doctype!r} does not exist.")]
		tables = {field.options for field in frappe.get_meta(parent_doctype).get_table_fields()}
		if doctype not in tables:
			return [Issue("error", f"{doctype} is not a table of {parent_doctype}.")]
		checked = parent_doctype
	if run_as and not frappe.has_permission(checked, ptype, user=run_as):
		issues.append(Issue("error", f"Run As user {run_as} has no {ptype} permission on {checked}."))
	return issues


def field_issues(doctype, fieldnames, label: str = "field") -> list[Issue]:
	"""Every field name exists on the DocType (expressions are skipped)."""
	if not doctype or is_expression(doctype) or not frappe.db.exists("DocType", doctype):
		return []
	meta = frappe.get_meta(doctype)
	issues = []
	for fieldname in fieldnames or []:
		if not isinstance(fieldname, str) or is_expression(fieldname):
			continue
		if fieldname not in STANDARD_FIELDS and not meta.has_field(fieldname):
			issues.append(Issue("error", f"{doctype} has no {label} {fieldname!r}."))
	return issues


def filter_fields(filters) -> list[str]:
	"""Field names used by Frappe filters given as a dict or a list of [field, op, value]."""
	if isinstance(filters, dict):
		return list(filters)
	names = []
	for row in filters or []:
		if isinstance(row, list | tuple) and row:
			# [field, op, value] or [doctype, field, op, value]
			names.append(row[1] if len(row) == 4 else row[0])
	return names


def submittable(doctype) -> bool:
	return bool(doctype) and frappe.get_meta(doctype).is_submittable
