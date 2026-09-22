from __future__ import annotations

from pridict.schema_intelligence.models import Diagnostic, DocTypeSchema, RelationshipSchema


def resolve_relationships(
	doctypes: list[DocTypeSchema],
	discovered_doctype_names: set[str],
) -> tuple[list[RelationshipSchema], list[Diagnostic]]:
	relationships: list[RelationshipSchema] = []
	diagnostics: list[Diagnostic] = []
	doctype_map = {doctype.name: doctype for doctype in doctypes}

	for doctype in doctypes:
		field_map = {field.fieldname: field for field in doctype.fields}
		for field in doctype.fields:
			if field.fieldtype == "Link":
				_relationship_for_static_link(field, discovered_doctype_names, relationships, diagnostics)
			elif field.fieldtype == "Table":
				_relationship_for_child_table(
					field, doctype_map, discovered_doctype_names, relationships, diagnostics
				)
			elif field.fieldtype == "Table MultiSelect":
				_relationship_for_table_multiselect(
					field, doctype_map, discovered_doctype_names, relationships, diagnostics
				)
			elif field.fieldtype == "Dynamic Link":
				_relationship_for_dynamic_link(
					field, field_map, discovered_doctype_names, relationships, diagnostics
				)

	return relationships, diagnostics


def _relationship_id(source_doctype: str, source_field: str, relationship_type: str) -> str:
	return f"{source_doctype}.{source_field}:{relationship_type}"


def _target_option(field) -> str | None:
	return field.options.strip() if isinstance(field.options, str) and field.options.strip() else None


def _relationship_for_static_link(field, discovered_names, relationships, diagnostics):
	target = _target_option(field)
	if not target:
		diagnostics.append(
			Diagnostic(
				severity="warning",
				code="link_target_missing",
				stage="relationship_resolution",
				message="Link field has no static target DocType.",
				doctype=field.doctype,
				fieldname=field.fieldname,
			)
		)
	elif target not in discovered_names:
		diagnostics.append(
			Diagnostic(
				severity="warning",
				code="link_target_not_discovered",
				stage="relationship_resolution",
				message=f"Link target {target} was not discovered on the site.",
				doctype=field.doctype,
				fieldname=field.fieldname,
				details={"target_doctype": target},
			)
		)

	relationships.append(
		RelationshipSchema(
			relationship_id=_relationship_id(field.doctype, field.fieldname, "LINK"),
			relationship_type="LINK",
			source_doctype=field.doctype,
			source_field=field.fieldname,
			target_doctype=target,
			selector_field=None,
			discoverable_targets=(target,) if target in discovered_names else (),
			properties={},
			provenance=field.provenance,
		)
	)


def _relationship_for_child_table(field, doctype_map, discovered_names, relationships, diagnostics):
	target = _target_option(field)
	_validate_child_target(field, target, doctype_map, discovered_names, diagnostics)
	relationships.append(
		RelationshipSchema(
			relationship_id=_relationship_id(field.doctype, field.fieldname, "CHILD_TABLE"),
			relationship_type="CHILD_TABLE",
			source_doctype=field.doctype,
			source_field=field.fieldname,
			target_doctype=target,
			selector_field=None,
			discoverable_targets=(target,) if target in discovered_names else (),
			properties={},
			provenance=field.provenance,
		)
	)


def _relationship_for_table_multiselect(field, doctype_map, discovered_names, relationships, diagnostics):
	target = _target_option(field)
	_validate_child_target(field, target, doctype_map, discovered_names, diagnostics)
	link_fields = []
	if target and target in doctype_map:
		link_fields = [child_field for child_field in doctype_map[target].fields if child_field.fieldtype == "Link"]
		if not link_fields:
			diagnostics.append(
				Diagnostic(
					severity="warning",
					code="table_multiselect_link_missing",
					stage="relationship_resolution",
					message="Table MultiSelect child DocType has no Link field.",
					doctype=field.doctype,
					fieldname=field.fieldname,
					details={"child_doctype": target},
				)
			)

	relationships.append(
		RelationshipSchema(
			relationship_id=_relationship_id(field.doctype, field.fieldname, "TABLE_MULTISELECT"),
			relationship_type="TABLE_MULTISELECT",
			source_doctype=field.doctype,
			source_field=field.fieldname,
			target_doctype=target,
			selector_field=None,
			discoverable_targets=(target,) if target in discovered_names else (),
			properties={
				"child_link_fields": [
					{"fieldname": item.fieldname, "target_doctype": item.options} for item in link_fields
				]
			},
			provenance=field.provenance,
		)
	)


def _validate_child_target(field, target, doctype_map, discovered_names, diagnostics):
	if not target:
		diagnostics.append(
			Diagnostic(
				severity="warning",
				code="child_table_target_missing",
				stage="relationship_resolution",
				message="Child-table field has no target DocType.",
				doctype=field.doctype,
				fieldname=field.fieldname,
			)
		)
		return
	if target not in discovered_names:
		diagnostics.append(
			Diagnostic(
				severity="warning",
				code="child_table_target_not_discovered",
				stage="relationship_resolution",
				message=f"Child-table target {target} was not discovered on the site.",
				doctype=field.doctype,
				fieldname=field.fieldname,
				details={"target_doctype": target},
			)
		)
		return
	if not doctype_map[target].flags.get("istable"):
		diagnostics.append(
			Diagnostic(
				severity="warning",
				code="child_table_target_not_child",
				stage="relationship_resolution",
				message=f"Child-table target {target} is not marked as a child DocType.",
				doctype=field.doctype,
				fieldname=field.fieldname,
				details={"target_doctype": target},
			)
		)


def _relationship_for_dynamic_link(field, field_map, discovered_names, relationships, diagnostics):
	selector_name = _target_option(field)
	discoverable_targets: tuple[str, ...] = ()
	selector_type = None
	selector_options = None

	if not selector_name or selector_name not in field_map:
		diagnostics.append(
			Diagnostic(
				severity="error",
				code="dynamic_link_selector_missing",
				stage="relationship_resolution",
				message="Dynamic Link does not reference an existing selector field.",
				doctype=field.doctype,
				fieldname=field.fieldname,
				details={"selector_field": selector_name},
			)
		)
	else:
		selector = field_map[selector_name]
		selector_type = selector.fieldtype
		selector_options = selector.options
		if selector.fieldtype == "Link" and selector.options == "DocType":
			discoverable_targets = tuple(sorted(discovered_names))
		elif selector.fieldtype == "Select":
			options = {
				item.strip()
				for item in str(selector.options or "").splitlines()
				if item.strip()
			}
			discoverable_targets = tuple(sorted(options & discovered_names))
			missing_options = sorted(options - discovered_names)
			if missing_options:
				diagnostics.append(
					Diagnostic(
						severity="warning",
						code="dynamic_link_selector_targets_not_discovered",
						stage="relationship_resolution",
						message="Dynamic Link selector lists values that are not installed DocTypes.",
						doctype=field.doctype,
						fieldname=field.fieldname,
						details={"selector_field": selector_name, "values": missing_options},
					)
				)
		else:
			diagnostics.append(
				Diagnostic(
					severity="warning",
					code="dynamic_link_selector_invalid",
					stage="relationship_resolution",
					message="Dynamic Link selector must be a Link to DocType or a Select field.",
					doctype=field.doctype,
					fieldname=field.fieldname,
					details={
						"selector_field": selector_name,
						"selector_fieldtype": selector.fieldtype,
						"selector_options": selector.options,
					},
				)
			)

	relationships.append(
		RelationshipSchema(
			relationship_id=_relationship_id(field.doctype, field.fieldname, "DYNAMIC_LINK"),
			relationship_type="DYNAMIC_LINK",
			source_doctype=field.doctype,
			source_field=field.fieldname,
			target_doctype=None,
			selector_field=selector_name,
			discoverable_targets=discoverable_targets,
			properties={
				"selector_fieldtype": selector_type,
				"selector_options": selector_options,
			},
			provenance=field.provenance,
		)
	)
