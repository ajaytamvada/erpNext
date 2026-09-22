from __future__ import annotations

from typing import Any

import frappe
from frappe.model.meta import Meta


class ExtractionMeta(Meta):
	"""Effective Meta without Frappe's business-table large-table heuristic."""

	def check_if_large_table(self):
		self.is_large_table = False


class FrappeMetadataSource:
	@property
	def site(self) -> str:
		return frappe.local.site

	@property
	def frappe_version(self) -> str:
		return frappe.get_attr("frappe.__version__")

	@property
	def erpnext_version(self) -> str | None:
		if "erpnext" not in frappe.get_installed_apps():
			return None
		return frappe.get_attr("erpnext.__version__")

	def discover_doctypes(self) -> list[str]:
		return frappe.db.get_all("DocType", pluck="name", order_by="name asc")

	def get_effective_metadata(self, doctype: str) -> dict[str, Any]:
		return ExtractionMeta(doctype).as_dict()

	def get_raw_metadata(self, doctype: str) -> dict[str, Any]:
		return {
			"doctype": self._get_one("DocType", {"name": doctype}),
			"docfields": self._get_many("DocField", {"parent": doctype}, "idx asc, name asc"),
			"docperms": self._get_many("DocPerm", {"parent": doctype}, "idx asc, name asc"),
			"custom_fields": self._get_many("Custom Field", {"dt": doctype}, "idx asc, name asc"),
			"property_setters": self._get_many(
				"Property Setter", {"doc_type": doctype}, "doctype_or_field asc, field_name asc, property asc"
			),
			"custom_docperms": self._get_many(
				"Custom DocPerm", {"parent": doctype}, "idx asc, name asc"
			),
			"custom_links": self._get_many(
				"DocType Link", {"parent": doctype, "custom": 1}, "idx asc, name asc", ignore_ddl=True
			),
			"custom_actions": self._get_many(
				"DocType Action", {"parent": doctype, "custom": 1}, "idx asc, name asc", ignore_ddl=True
			),
			"custom_states": self._get_many(
				"DocType State", {"parent": doctype, "custom": 1}, "idx asc, name asc", ignore_ddl=True
			),
		}

	@staticmethod
	def _get_one(doctype: str, filters: dict[str, Any]) -> dict[str, Any]:
		value = frappe.db.get_value(doctype, filters, "*", as_dict=True)
		if value is None:
			raise frappe.DoesNotExistError(f"{doctype} matching {filters} was not found")
		return dict(value)

	@staticmethod
	def _get_many(
		doctype: str,
		filters: dict[str, Any],
		order_by: str,
		*,
		ignore_ddl: bool = False,
	) -> list[dict[str, Any]]:
		if not frappe.db.table_exists(doctype):
			return []
		return [
			dict(row)
			for row in frappe.db.get_all(
				doctype,
				filters=filters,
				fields="*",
				order_by=order_by,
				ignore_ddl=ignore_ddl,
			)
		]
