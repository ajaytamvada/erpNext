from __future__ import annotations

from dataclasses import dataclass

from pridict.schema_intelligence.models import Diagnostic, DocTypeSchema, RelationshipSchema, SchemaSnapshot


PURCHASING_CANDIDATES = (
	"Material Request",
	"Request for Quotation",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Payment Entry",
)


class IncompatibleSchemaSnapshotError(ValueError):
	pass


@dataclass(frozen=True)
class PurchasingSchemaView:
	snapshot_id: str
	metadata_hash: str
	schema_format_version: str
	frappe_version: str
	erpnext_version: str | None
	site_identifier_hash: str
	completeness: str
	diagnostics: tuple[Diagnostic, ...]
	doctypes: tuple[DocTypeSchema, ...]
	relationships: tuple[RelationshipSchema, ...]
	missing_candidates: tuple[str, ...]

	@property
	def doctype_names(self) -> tuple[str, ...]:
		return tuple(item.name for item in self.doctypes)

	def get_doctype(self, name: str) -> DocTypeSchema | None:
		return next((item for item in self.doctypes if item.name == name), None)


class SchemaSnapshotAdapter:
	SUPPORTED_MAJOR_VERSION = "1"

	def adapt_purchasing(self, snapshot: SchemaSnapshot) -> PurchasingSchemaView:
		if snapshot.schema_format_version.split(".", 1)[0] != self.SUPPORTED_MAJOR_VERSION:
			raise IncompatibleSchemaSnapshotError(
				f"SchemaSnapshot {snapshot.schema_format_version} is not supported"
			)
		available = {item.name: item for item in snapshot.doctypes}
		doctypes = tuple(available[name] for name in PURCHASING_CANDIDATES if name in available)
		relevant_names = set(PURCHASING_CANDIDATES)
		child_doctypes = {
			field.options
			for doctype in doctypes
			for field in doctype.fields
			if field.fieldtype in {"Table", "Table MultiSelect"} and isinstance(field.options, str)
		}
		relationships = tuple(
			item
			for item in snapshot.relationships
			if item.source_doctype in relevant_names | child_doctypes
			and (item.target_doctype in relevant_names or item.source_doctype in relevant_names)
		)
		relevant_diagnostics = tuple(
			item
			for item in snapshot.diagnostics
			if item.doctype is None or item.doctype in relevant_names | child_doctypes
		)
		return PurchasingSchemaView(
			snapshot_id=snapshot.snapshot_id,
			metadata_hash=snapshot.metadata_hash,
			schema_format_version=snapshot.schema_format_version,
			frappe_version=snapshot.frappe_version,
			erpnext_version=snapshot.erpnext_version,
			site_identifier_hash=snapshot.site_identifier_hash,
			completeness=snapshot.completeness,
			diagnostics=relevant_diagnostics,
			doctypes=doctypes,
			relationships=relationships,
			missing_candidates=tuple(name for name in PURCHASING_CANDIDATES if name not in available),
		)
