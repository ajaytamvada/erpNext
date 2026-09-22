from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


SCHEMA_FORMAT_VERSION = "1.0.0"
DiagnosticSeverity = Literal["warning", "error"]
CompletenessStatus = Literal["complete", "incomplete"]
RelationshipType = Literal["LINK", "CHILD_TABLE", "DYNAMIC_LINK", "TABLE_MULTISELECT"]


def _require_text(value: str, field_name: str) -> None:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True)
class Provenance:
	source_type: str
	source_path: str
	source_name: str | None = None

	def __post_init__(self):
		_require_text(self.source_type, "source_type")
		_require_text(self.source_path, "source_path")

	def to_dict(self) -> dict[str, Any]:
		return {
			"source_type": self.source_type,
			"source_path": self.source_path,
			"source_name": self.source_name,
		}

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "Provenance":
		return cls(
			source_type=value["source_type"],
			source_path=value["source_path"],
			source_name=value.get("source_name"),
		)


@dataclass(frozen=True)
class Diagnostic:
	severity: DiagnosticSeverity
	code: str
	stage: str
	message: str
	doctype: str | None = None
	fieldname: str | None = None
	details: dict[str, Any] = field(default_factory=dict)

	def __post_init__(self):
		if self.severity not in ("warning", "error"):
			raise ValueError("severity must be warning or error")
		_require_text(self.code, "code")
		_require_text(self.stage, "stage")
		_require_text(self.message, "message")

	def to_dict(self) -> dict[str, Any]:
		return {
			"severity": self.severity,
			"code": self.code,
			"stage": self.stage,
			"message": self.message,
			"doctype": self.doctype,
			"fieldname": self.fieldname,
			"details": self.details,
		}

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "Diagnostic":
		return cls(
			severity=value["severity"],
			code=value["code"],
			stage=value["stage"],
			message=value["message"],
			doctype=value.get("doctype"),
			fieldname=value.get("fieldname"),
			details=value.get("details", {}),
		)


@dataclass(frozen=True)
class FieldSchema:
	doctype: str
	fieldname: str
	fieldtype: str
	idx: int
	label: str | None
	options: Any
	required: bool | None
	read_only: bool | None
	hidden: bool | None
	virtual: bool | None
	custom: bool
	properties: dict[str, Any]
	provenance: tuple[Provenance, ...]

	def __post_init__(self):
		_require_text(self.doctype, "doctype")
		_require_text(self.fieldname, "fieldname")
		_require_text(self.fieldtype, "fieldtype")
		if self.idx < 0:
			raise ValueError("idx must not be negative")
		if not self.provenance:
			raise ValueError("field provenance is required")

	def to_dict(self) -> dict[str, Any]:
		return {
			"doctype": self.doctype,
			"fieldname": self.fieldname,
			"fieldtype": self.fieldtype,
			"idx": self.idx,
			"label": self.label,
			"options": self.options,
			"required": self.required,
			"read_only": self.read_only,
			"hidden": self.hidden,
			"virtual": self.virtual,
			"custom": self.custom,
			"properties": self.properties,
			"provenance": [item.to_dict() for item in self.provenance],
		}

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "FieldSchema":
		return cls(
			doctype=value["doctype"],
			fieldname=value["fieldname"],
			fieldtype=value["fieldtype"],
			idx=value["idx"],
			label=value.get("label"),
			options=value.get("options"),
			required=value.get("required"),
			read_only=value.get("read_only"),
			hidden=value.get("hidden"),
			virtual=value.get("virtual"),
			custom=value["custom"],
			properties=value.get("properties", {}),
			provenance=tuple(Provenance.from_dict(item) for item in value["provenance"]),
		)


@dataclass(frozen=True)
class PermissionSchema:
	doctype: str
	role: str
	permlevel: int
	permissions: dict[str, bool | int | str | None]
	if_owner: bool | None
	source: Literal["DocPerm", "Custom DocPerm"]
	provenance: tuple[Provenance, ...]

	def __post_init__(self):
		_require_text(self.doctype, "doctype")
		_require_text(self.role, "role")
		if self.permlevel < 0:
			raise ValueError("permlevel must not be negative")
		if self.source not in ("DocPerm", "Custom DocPerm"):
			raise ValueError("permission source must be DocPerm or Custom DocPerm")
		if not self.provenance:
			raise ValueError("permission provenance is required")

	def to_dict(self) -> dict[str, Any]:
		return {
			"doctype": self.doctype,
			"role": self.role,
			"permlevel": self.permlevel,
			"permissions": self.permissions,
			"if_owner": self.if_owner,
			"source": self.source,
			"provenance": [item.to_dict() for item in self.provenance],
		}

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "PermissionSchema":
		return cls(
			doctype=value["doctype"],
			role=value["role"],
			permlevel=value["permlevel"],
			permissions=value.get("permissions", {}),
			if_owner=value.get("if_owner"),
			source=value["source"],
			provenance=tuple(Provenance.from_dict(item) for item in value["provenance"]),
		)


@dataclass(frozen=True)
class DocTypeSchema:
	name: str
	module: str | None
	flags: dict[str, bool | int | str | None]
	properties: dict[str, Any]
	fields: tuple[FieldSchema, ...]
	permissions: tuple[PermissionSchema, ...]
	provenance: tuple[Provenance, ...]

	def __post_init__(self):
		_require_text(self.name, "name")
		fieldnames = [item.fieldname for item in self.fields]
		if len(fieldnames) != len(set(fieldnames)):
			raise ValueError(f"duplicate fieldname in {self.name}")
		if not self.provenance:
			raise ValueError("doctype provenance is required")

	def to_dict(self) -> dict[str, Any]:
		return {
			"name": self.name,
			"module": self.module,
			"flags": self.flags,
			"properties": self.properties,
			"fields": [item.to_dict() for item in self.fields],
			"permissions": [item.to_dict() for item in self.permissions],
			"provenance": [item.to_dict() for item in self.provenance],
		}

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "DocTypeSchema":
		return cls(
			name=value["name"],
			module=value.get("module"),
			flags=value.get("flags", {}),
			properties=value.get("properties", {}),
			fields=tuple(FieldSchema.from_dict(item) for item in value.get("fields", [])),
			permissions=tuple(PermissionSchema.from_dict(item) for item in value.get("permissions", [])),
			provenance=tuple(Provenance.from_dict(item) for item in value["provenance"]),
		)


@dataclass(frozen=True)
class RelationshipSchema:
	relationship_id: str
	relationship_type: RelationshipType
	source_doctype: str
	source_field: str
	target_doctype: str | None
	selector_field: str | None
	discoverable_targets: tuple[str, ...]
	properties: dict[str, Any]
	provenance: tuple[Provenance, ...]

	def __post_init__(self):
		_require_text(self.relationship_id, "relationship_id")
		if self.relationship_type not in ("LINK", "CHILD_TABLE", "DYNAMIC_LINK", "TABLE_MULTISELECT"):
			raise ValueError("unsupported relationship type")
		_require_text(self.source_doctype, "source_doctype")
		_require_text(self.source_field, "source_field")
		if not self.provenance:
			raise ValueError("relationship provenance is required")

	def to_dict(self) -> dict[str, Any]:
		return {
			"relationship_id": self.relationship_id,
			"relationship_type": self.relationship_type,
			"source_doctype": self.source_doctype,
			"source_field": self.source_field,
			"target_doctype": self.target_doctype,
			"selector_field": self.selector_field,
			"discoverable_targets": list(self.discoverable_targets),
			"properties": self.properties,
			"provenance": [item.to_dict() for item in self.provenance],
		}

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "RelationshipSchema":
		return cls(
			relationship_id=value["relationship_id"],
			relationship_type=value["relationship_type"],
			source_doctype=value["source_doctype"],
			source_field=value["source_field"],
			target_doctype=value.get("target_doctype"),
			selector_field=value.get("selector_field"),
			discoverable_targets=tuple(value.get("discoverable_targets", [])),
			properties=value.get("properties", {}),
			provenance=tuple(Provenance.from_dict(item) for item in value["provenance"]),
		)


@dataclass(frozen=True)
class SchemaSnapshot:
	snapshot_id: str
	captured_at: str
	schema_format_version: str
	frappe_version: str
	erpnext_version: str | None
	site_identifier_hash: str
	doctypes: tuple[DocTypeSchema, ...]
	relationships: tuple[RelationshipSchema, ...]
	raw_metadata: dict[str, Any]
	metadata_hash: str
	completeness: CompletenessStatus
	diagnostics: tuple[Diagnostic, ...]

	def __post_init__(self):
		_require_text(self.snapshot_id, "snapshot_id")
		_require_text(self.captured_at, "captured_at")
		_require_text(self.schema_format_version, "schema_format_version")
		_require_text(self.frappe_version, "frappe_version")
		if len(self.site_identifier_hash) != 64:
			raise ValueError("site_identifier_hash must be a SHA-256 hex digest")
		if len(self.metadata_hash) != 64:
			raise ValueError("metadata_hash must be a SHA-256 hex digest")
		if self.completeness not in ("complete", "incomplete"):
			raise ValueError("invalid completeness status")
		names = [item.name for item in self.doctypes]
		if names != sorted(names):
			raise ValueError("doctypes must use stable name ordering")

	def to_dict(self) -> dict[str, Any]:
		return {
			"snapshot_id": self.snapshot_id,
			"captured_at": self.captured_at,
			"schema_format_version": self.schema_format_version,
			"frappe_version": self.frappe_version,
			"erpnext_version": self.erpnext_version,
			"site_identifier_hash": self.site_identifier_hash,
			"doctypes": [item.to_dict() for item in self.doctypes],
			"relationships": [item.to_dict() for item in self.relationships],
			"raw_metadata": self.raw_metadata,
			"metadata_hash": self.metadata_hash,
			"completeness": self.completeness,
			"diagnostics": [item.to_dict() for item in self.diagnostics],
		}

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "SchemaSnapshot":
		return cls(
			snapshot_id=value["snapshot_id"],
			captured_at=value["captured_at"],
			schema_format_version=value["schema_format_version"],
			frappe_version=value["frappe_version"],
			erpnext_version=value.get("erpnext_version"),
			site_identifier_hash=value["site_identifier_hash"],
			doctypes=tuple(DocTypeSchema.from_dict(item) for item in value.get("doctypes", [])),
			relationships=tuple(
				RelationshipSchema.from_dict(item) for item in value.get("relationships", [])
			),
			raw_metadata=value.get("raw_metadata", {}),
			metadata_hash=value["metadata_hash"],
			completeness=value["completeness"],
			diagnostics=tuple(Diagnostic.from_dict(item) for item in value.get("diagnostics", [])),
		)
