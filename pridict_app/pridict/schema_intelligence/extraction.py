from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from pridict.schema_intelligence.models import (
	Diagnostic,
	DocTypeSchema,
	FieldSchema,
	PermissionSchema,
	Provenance,
)
from pridict.schema_intelligence.normalization import UnsupportedValueError, normalize_value, optional_bool
from pridict.schema_intelligence.relationships import resolve_relationships
from pridict.schema_intelligence.snapshots import build_snapshot


DOCTYPE_FLAGS = (
	"custom",
	"istable",
	"issingle",
	"is_tree",
	"is_virtual",
	"is_submittable",
	"read_only",
	"track_changes",
	"track_seen",
	"track_views",
	"allow_rename",
	"allow_import",
	"allow_copy",
	"allow_guest_to_view",
)
FIELD_KEYS = {
	"doctype",
	"name",
	"parent",
	"parentfield",
	"parenttype",
	"fieldname",
	"fieldtype",
	"idx",
	"label",
	"options",
	"reqd",
	"read_only",
	"hidden",
	"is_virtual",
	"is_custom_field",
}
PERMISSION_IDENTITY_KEYS = {
	"doctype",
	"name",
	"parent",
	"parentfield",
	"parenttype",
	"idx",
	"role",
	"permlevel",
	"if_owner",
}
DOCTYPE_CHILD_KEYS = {"fields", "permissions"}
VOLATILE_METADATA_KEYS = {"creation", "modified", "modified_by", "owner", "_last_update"}


class MetadataSource(Protocol):
	@property
	def site(self) -> str: ...

	@property
	def frappe_version(self) -> str: ...

	@property
	def erpnext_version(self) -> str | None: ...

	def discover_doctypes(self) -> list[str]: ...

	def get_raw_metadata(self, doctype: str) -> dict[str, Any]: ...

	def get_effective_metadata(self, doctype: str) -> dict[str, Any]: ...


def extract_schema(source: MetadataSource):
	diagnostics: list[Diagnostic] = []
	raw_metadata: dict[str, Any] = {"doctypes": {}}
	doctypes: list[DocTypeSchema] = []

	try:
		discovered_names = sorted(set(source.discover_doctypes()))
	except Exception as exc:
		diagnostics.append(_exception_diagnostic("discovery_failed", "discovery", exc))
		discovered_names = []

	for doctype_name in discovered_names:
		try:
			raw = source.get_raw_metadata(doctype_name)
			effective = source.get_effective_metadata(doctype_name)
			raw_bundle = normalize_value({
				**raw,
				"effective": effective,
			}, f"doctypes.{doctype_name}.raw")
			raw_metadata["doctypes"][doctype_name] = raw_bundle
			doctypes.append(normalize_doctype(doctype_name, effective, raw, diagnostics=diagnostics))
		except Exception as exc:
			diagnostics.append(
				_exception_diagnostic("doctype_extraction_failed", "doctype_extraction", exc, doctype_name)
			)

	relationships, relationship_diagnostics = resolve_relationships(doctypes, set(discovered_names))
	diagnostics.extend(relationship_diagnostics)

	return build_snapshot(
		frappe_version=source.frappe_version,
		erpnext_version=source.erpnext_version,
		site=source.site,
		doctypes=doctypes,
		relationships=relationships,
		raw_metadata=raw_metadata,
		diagnostics=diagnostics,
	)


def normalize_doctype(
	doctype_name: str,
	effective: Mapping[str, Any],
	raw: Mapping[str, Any],
	*,
	diagnostics: list[Diagnostic] | None = None,
) -> DocTypeSchema:
	fields = []
	for field in sorted(
		effective.get("fields", []),
		key=lambda item: (int(item.get("idx") or 0), item.get("fieldname") or ""),
	):
		try:
			fields.append(normalize_field(doctype_name, field, raw))
		except Exception as exc:
			if diagnostics is None:
				raise
			diagnostics.append(
				_exception_diagnostic(
					"field_normalization_failed",
					"field_normalization",
					exc,
					doctype_name,
					field.get("fieldname"),
				)
			)

	permissions = []
	for permission in sorted(
		effective.get("permissions", []),
		key=lambda item: (int(item.get("permlevel") or 0), item.get("role") or "", int(item.get("idx") or 0)),
	):
		try:
			permissions.append(normalize_permission(doctype_name, permission, raw))
		except Exception as exc:
			if diagnostics is None:
				raise
			diagnostics.append(
				_exception_diagnostic(
					"permission_normalization_failed",
					"permission_normalization",
					exc,
					doctype_name,
				)
			)
	flags = {key: optional_bool(effective[key]) for key in DOCTYPE_FLAGS if key in effective}
	properties = {
		key: normalize_value(value, f"doctypes.{doctype_name}.effective.{key}")
		for key, value in effective.items()
		if key not in DOCTYPE_CHILD_KEYS | VOLATILE_METADATA_KEYS | {"name", "doctype", *DOCTYPE_FLAGS}
		and value is not None
		and not key.startswith("_")
	}
	provenance = [
		Provenance(
			source_type="DocType",
			source_name=doctype_name,
			source_path=f"doctypes/{doctype_name}/doctype",
		)
	]
	for setter in raw.get("property_setters", []):
		if setter.get("doctype_or_field") == "DocType":
			provenance.append(_property_setter_provenance(doctype_name, setter))

	return DocTypeSchema(
		name=doctype_name,
		module=effective.get("module"),
		flags=flags,
		properties=properties,
		fields=tuple(fields),
		permissions=tuple(permissions),
		provenance=tuple(provenance),
	)


def normalize_field(doctype_name: str, field: Mapping[str, Any], raw: Mapping[str, Any]) -> FieldSchema:
	fieldname = field.get("fieldname")
	fieldtype = field.get("fieldtype")
	if not fieldname or not fieldtype:
		raise ValueError(f"field in {doctype_name} is missing fieldname or fieldtype")

	is_custom = optional_bool(field.get("is_custom_field")) is True
	source_type = "Custom Field" if is_custom else "DocField"
	source_collection = "custom_fields" if is_custom else "docfields"
	provenance = [
		Provenance(
			source_type=source_type,
			source_name=_find_raw_name(raw.get(source_collection, []), fieldname=fieldname),
			source_path=f"doctypes/{doctype_name}/{source_collection}/{fieldname}",
		),
		Provenance(
			source_type="effective_meta",
			source_name=fieldname,
			source_path=f"doctypes/{doctype_name}/effective/fields/{fieldname}",
		),
	]
	for setter in raw.get("property_setters", []):
		if setter.get("doctype_or_field") == "DocField" and setter.get("field_name") == fieldname:
			provenance.append(_property_setter_provenance(doctype_name, setter))

	properties = {
		key: normalize_value(value, f"doctypes.{doctype_name}.effective.fields.{fieldname}.{key}")
		for key, value in field.items()
		if key not in FIELD_KEYS | VOLATILE_METADATA_KEYS and value is not None and not key.startswith("_")
	}
	return FieldSchema(
		doctype=doctype_name,
		fieldname=fieldname,
		fieldtype=fieldtype,
		idx=int(field.get("idx") or 0),
		label=field.get("label"),
		options=normalize_value(field.get("options"), f"doctypes.{doctype_name}.fields.{fieldname}.options"),
		required=optional_bool(field.get("reqd")) if "reqd" in field else None,
		read_only=optional_bool(field.get("read_only")) if "read_only" in field else None,
		hidden=optional_bool(field.get("hidden")) if "hidden" in field else None,
		virtual=optional_bool(field.get("is_virtual")) if "is_virtual" in field else None,
		custom=is_custom,
		properties=properties,
		provenance=tuple(provenance),
	)


def normalize_permission(
	doctype_name: str,
	permission: Mapping[str, Any],
	raw: Mapping[str, Any],
) -> PermissionSchema:
	role = permission.get("role")
	if not role:
		raise ValueError(f"permission in {doctype_name} is missing role")
	source_type = "Custom DocPerm" if raw.get("custom_docperms") else "DocPerm"
	collection = "custom_docperms" if source_type == "Custom DocPerm" else "docperms"
	permlevel = int(permission.get("permlevel") or 0)
	provenance = Provenance(
		source_type=source_type,
		source_name=_find_raw_name(raw.get(collection, []), role=role, permlevel=permlevel),
		source_path=f"doctypes/{doctype_name}/{collection}/{role}:{permlevel}",
	)
	permissions = {
		key: normalize_value(value, f"doctypes.{doctype_name}.permissions.{role}.{key}")
		for key, value in permission.items()
		if key not in PERMISSION_IDENTITY_KEYS | VOLATILE_METADATA_KEYS
		and value is not None
		and not key.startswith("_")
	}
	return PermissionSchema(
		doctype=doctype_name,
		role=role,
		permlevel=permlevel,
		permissions=permissions,
		if_owner=optional_bool(permission.get("if_owner")) if "if_owner" in permission else None,
		source=source_type,
		provenance=(provenance,),
	)


def _find_raw_name(rows: list[Mapping[str, Any]], **criteria) -> str | None:
	for row in rows:
		if all(row.get(key) == value for key, value in criteria.items()):
			return row.get("name")
	return None


def _property_setter_provenance(doctype_name: str, setter: Mapping[str, Any]) -> Provenance:
	name = setter.get("name")
	scope = setter.get("doctype_or_field") or "unknown"
	field_name = setter.get("field_name") or "@doctype"
	property_name = setter.get("property") or "unknown"
	return Provenance(
		source_type="Property Setter",
		source_name=name,
		source_path=f"doctypes/{doctype_name}/property_setters/{scope}/{field_name}/{property_name}",
	)


def _exception_diagnostic(
	code: str,
	stage: str,
	exc: Exception,
	doctype: str | None = None,
	fieldname: str | None = None,
) -> Diagnostic:
	message = str(exc).strip() or exc.__class__.__name__
	if isinstance(exc, UnsupportedValueError):
		code = "unsupported_metadata_value"
	return Diagnostic(
		severity="error",
		code=code,
		stage=stage,
		message=message,
		doctype=doctype,
		fieldname=fieldname,
		details={"exception_type": f"{exc.__class__.__module__}.{exc.__class__.__name__}"},
	)
