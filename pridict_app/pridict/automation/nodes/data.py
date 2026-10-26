"""Data node types: read documents and reports, always with the Run As user's permissions."""

from __future__ import annotations

import frappe
from frappe import _

from pridict.automation import expressions
from pridict.automation.nodes import Issue, NodeResult, NodeType, meta, register

MAX_ROWS = expressions.MAX_LIST_ITEMS
AGGREGATES = ("count", "sum", "avg", "min", "max")


def _filters_schema():
	return {
		"title": "Filters",
		"description": "Frappe filters: {field: value} or [[field, operator, value], ...]",
		"oneOf": [{"type": "object"}, {"type": "array"}],
	}


def _filters(config: dict, scope: dict):
	filters = expressions.resolve_all(config.get("filters") or {}, scope)
	if not isinstance(filters, dict | list):
		raise ValueError(_("Filters must be a mapping or a list of conditions."))
	return filters


def _order_by(doctype: str, order_by: str | None) -> str:
	"""Validated 'field asc|desc' (field names come from the spec, so never trust them raw)."""
	if not order_by:
		return "creation desc"
	parts = str(order_by).split()
	field = parts[0]
	direction = parts[1].lower() if len(parts) > 1 else "asc"
	if direction not in ("asc", "desc") or len(parts) > 2:
		raise ValueError(_("Order by must look like 'field asc' or 'field desc'."))
	if field not in meta.STANDARD_FIELDS and not frappe.get_meta(doctype).has_field(field):
		raise ValueError(_("{0} has no field {1}.").format(doctype, field))
	return f"`{field}` {direction}"


@register
class GetDocument(NodeType):
	type = "data.get_document"
	label = "Get document"
	category = "data"
	icon = "📄"
	description = "Loads one document by name."
	outputs = ("doc",)
	config_schema = {
		"type": "object",
		"required": ["doctype", "name"],
		"properties": {
			"doctype": {"type": "string", "title": "DocType", "format": "doctype"},
			"name": {"type": "string", "title": "Document", "format": "template"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		return super().check_config(config) + expressions.check_templates(config)

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		return meta.doctype_issues(config.get("doctype"), run_as, "read")

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		doctype = expressions.resolve(config["doctype"], scope)
		name = expressions.resolve(config["name"], scope)
		if not name:
			raise ValueError(_("No document name to load."))
		doc = frappe.get_doc(doctype, name)
		doc.check_permission("read")
		return NodeResult(output={"doc": doc.as_dict()}, summary=_("Loaded {0} {1}").format(doctype, name))


@register
class FindDocuments(NodeType):
	type = "data.find_documents"
	label = "Find documents"
	category = "data"
	icon = "🔎"
	description = "Lists documents that match filters (up to 500)."
	outputs = ("rows", "count")
	config_schema = {
		"type": "object",
		"required": ["doctype"],
		"properties": {
			"doctype": {"type": "string", "title": "DocType", "format": "doctype"},
			"parent_doctype": {
				"type": "string",
				"title": "Parent DocType (for child tables)",
				"format": "doctype",
			},
			"filters": _filters_schema(),
			"fields": {"type": "array", "title": "Fields", "items": {"type": "string"}},
			"order_by": {"type": "string", "title": "Order by"},
			"limit": {"type": "integer", "title": "Limit", "minimum": 1, "maximum": MAX_ROWS},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config) + expressions.check_templates(config)
		limit = config.get("limit")
		if limit is not None and (not isinstance(limit, int) or not 1 <= limit <= MAX_ROWS):
			messages.append(f"limit must be between 1 and {MAX_ROWS}.")
		bad = [str(f) for f in config.get("fields") or [] if not str(f).isidentifier()]
		if bad:
			messages.append(f"fields must be plain field names: {', '.join(bad)}.")
		return messages

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		doctype = config.get("doctype")
		return (
			meta.doctype_issues(doctype, run_as, "read", parent_doctype=config.get("parent_doctype"))
			+ meta.field_issues(doctype, config.get("fields"))
			+ meta.field_issues(doctype, meta.filter_fields(config.get("filters")), "filter field")
		)

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		doctype = config["doctype"]
		fields = config.get("fields") or ["name"]
		if not all(str(field).isidentifier() for field in fields):
			raise ValueError(_("Fields must be plain field names."))
		extra = {"parent_doctype": config["parent_doctype"]} if config.get("parent_doctype") else {}
		rows = frappe.get_list(
			doctype,
			filters=_filters(config, scope),
			fields=[f"`{field}`" for field in fields],
			order_by=_order_by(doctype, config.get("order_by")),
			limit_page_length=min(int(config.get("limit") or MAX_ROWS), MAX_ROWS),
			**extra,
		)
		return NodeResult(
			output={"rows": rows, "count": len(rows)}, summary=_("Found {0} {1}").format(len(rows), doctype)
		)


@register
class Aggregate(NodeType):
	type = "data.aggregate"
	label = "Aggregate"
	category = "data"
	icon = "Σ"
	description = "Counts, sums or averages a field, optionally grouped by another field."
	outputs = ("rows", "value")
	config_schema = {
		"type": "object",
		"required": ["doctype", "function"],
		"properties": {
			"doctype": {"type": "string", "title": "DocType", "format": "doctype"},
			"filters": _filters_schema(),
			"function": {"type": "string", "title": "Function", "enum": list(AGGREGATES)},
			"field": {"type": "string", "title": "Field"},
			"group_by": {"type": "string", "title": "Group by"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config) + expressions.check_templates(config)
		if config.get("function") and config["function"] not in AGGREGATES:
			messages.append(f"function must be one of {', '.join(AGGREGATES)}.")
		if config.get("function") not in (None, "count") and not config.get("field"):
			messages.append("'field' is required for this function.")
		for key in ("field", "group_by"):
			if config.get(key) and not str(config[key]).isidentifier():
				messages.append(f"{key} must be a plain field name.")
		return messages

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		doctype = config.get("doctype")
		fields = [config.get(key) for key in ("field", "group_by") if config.get(key)]
		return (
			meta.doctype_issues(doctype, run_as, "read")
			+ meta.field_issues(doctype, fields)
			+ meta.field_issues(doctype, meta.filter_fields(config.get("filters")), "filter field")
		)

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		doctype, function = config["doctype"], config["function"]
		field, group_by = config.get("field"), config.get("group_by")
		for name in filter(None, (field, group_by)):
			if not name.isidentifier() or (
				name not in meta.STANDARD_FIELDS and not frappe.get_meta(doctype).has_field(name)
			):
				raise ValueError(_("{0} has no field {1}.").format(doctype, name))
		target = f"`{field}`" if field else "*"
		fields = [f"{function}({target}) as value"]
		if group_by:
			fields.insert(0, f"`{group_by}` as `group`")
		rows = frappe.get_list(
			doctype,
			filters=_filters(config, scope),
			fields=fields,
			group_by=f"`{group_by}`" if group_by else None,
			order_by="value desc" if group_by else None,
			limit_page_length=MAX_ROWS,
		)
		value = rows[0]["value"] if rows and not group_by else None
		summary = (
			_("{0} groups").format(len(rows))
			if group_by
			else _("{0}({1}) = {2}").format(function, field or "*", value)
		)
		return NodeResult(output={"rows": rows, "value": value}, summary=summary)


@register
class RunReport(NodeType):
	type = "data.run_report"
	label = "Run report"
	category = "data"
	icon = "📊"
	description = "Runs a Query Report or Script Report with filters."
	outputs = ("columns", "rows")
	config_schema = {
		"type": "object",
		"required": ["report"],
		"properties": {
			"report": {"type": "string", "title": "Report", "format": "report"},
			"filters": {"type": "object", "title": "Filters"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		return super().check_config(config) + expressions.check_templates(config)

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		report = config.get("report")
		if not report:
			return []
		report_type = frappe.db.get_value("Report", report, "report_type")
		if not report_type:
			return [Issue("error", f"Report {report!r} does not exist.")]
		if report_type not in ("Query Report", "Script Report"):
			return [Issue("error", f"{report} is a {report_type}; only Query and Script Reports can run.")]
		if run_as and not frappe.has_permission("Report", "read", report, user=run_as):
			return [Issue("error", f"Run As user {run_as} cannot open report {report}.")]
		return []

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		from frappe.desk.query_report import run

		filters = expressions.resolve_all(config.get("filters") or {}, scope)
		result = run(config["report"], filters=filters, ignore_prepared_report=True)
		columns = [
			{"fieldname": c.get("fieldname"), "label": c.get("label")}
			if isinstance(c, dict)
			else {"label": str(c)}
			for c in result.get("columns") or []
		]
		rows = [row for row in result.get("result") or [] if isinstance(row, dict | list)][:MAX_ROWS]
		return NodeResult(
			output={"columns": columns, "rows": rows},
			summary=_("{0}: {1} rows").format(config["report"], len(rows)),
		)
