"""Expressions inside automation specs.

Text fields are Jinja templates rendered in Frappe's sandboxed environment; conditions go
through frappe.safe_eval, the restricted evaluator Frappe Notifications use. Document
values are always passed in as data (the scope), never pasted into the expression.
"""

from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.utils import now_datetime, nowdate

# Side-effect-free builtins conditions may use, on top of frappe.safe_eval's own whitelist.
CONDITION_BUILTINS = {
	"abs": abs,
	"all": all,
	"any": any,
	"bool": bool,
	"len": len,
	"max": max,
	"min": min,
	"sorted": sorted,
	"str": str,
	"sum": sum,
}


MAX_LIST_ITEMS = 500
MAX_STRING_LENGTH = 100_000
# A value that is exactly one {{ expression }} keeps its type (list, number, dict...).
WHOLE_EXPRESSION = re.compile(r"^\s*\{\{(?P<expr>(?:(?!\{\{|\}\}).)*)\}\}\s*$", re.DOTALL)
NODE_REFERENCE = re.compile(r"\bnodes\.([A-Za-z_][A-Za-z0-9_]*)")


class ExpressionError(Exception):
	pass


def to_data(value):
	"""JSON-safe copy (dates become strings) so values can live in LangGraph checkpoints."""
	return json.loads(frappe.as_json(value))


def cap(value):
	"""Limit node outputs (lists to 500 items, strings to 100 kB) to keep run state small."""
	if isinstance(value, dict):
		return {key: cap(item) for key, item in value.items()}
	if isinstance(value, list):
		return [cap(item) for item in value[:MAX_LIST_ITEMS]]
	if isinstance(value, str) and len(value) > MAX_STRING_LENGTH:
		return value[:MAX_STRING_LENGTH]
	return value


def attr_dicts(value):
	"""Nested frappe._dict so expressions can write trigger.doc.supplier_name."""
	if isinstance(value, dict):
		return frappe._dict({key: attr_dicts(item) for key, item in value.items()})
	if isinstance(value, list):
		return [attr_dicts(item) for item in value]
	return value


def scope_from_state(state: dict) -> dict:
	return attr_dicts(
		{
			"trigger": state.get("trigger") or {},
			"nodes": state.get("nodes") or {},
			"vars": state.get("vars") or {},
			"run": state.get("run") or {},
			"loops": state.get("loops") or {},
		}
	) | {"now": now_datetime(), "today": nowdate()}


def render(template, scope: dict):
	"""Render a template string; other values (and plain strings without {{ or {%) pass through."""
	if not isinstance(template, str) or ("{{" not in template and "{%" not in template):
		return template
	if ".__" in template:
		raise ExpressionError(_("Templates may not use names that start with an underscore."))
	try:
		# Calls the jinja environment directly: frappe.render_template guesses that one-line
		# strings ending in ".txt" or ".html" are file paths.
		from frappe.utils.jinja import get_jenv, safe_render_flags

		with safe_render_flags():
			return get_jenv().from_string(template).render(scope)
	except Exception as error:
		raise ExpressionError(_("Could not fill in {0}: {1}").format(template, error)) from error


def resolve(value, scope: dict):
	"""Like render(), but a value that is exactly one {{ expression }} keeps its native type."""
	if not isinstance(value, str):
		return value
	match = WHOLE_EXPRESSION.match(value)
	if not match:
		return render(value, scope)
	expression = match.group("expr")
	if ".__" in expression:
		raise ExpressionError(_("Templates may not use names that start with an underscore."))
	try:
		from frappe.utils.jinja import get_jenv, safe_render_flags

		with safe_render_flags():
			return get_jenv().compile_expression(expression, undefined_to_none=True)(**scope)
	except Exception as error:
		raise ExpressionError(_("Could not fill in {0}: {1}").format(value, error)) from error


def resolve_all(value, scope: dict):
	"""resolve() every string inside a config value (dicts and lists included).

	{"$each": "{{ list }}", "field": "{{ row.x }}", ...} builds one dict per list item, with
	the item available as `row`; this is how child table rows are written.
	"""
	if isinstance(value, dict) and "$each" in value:
		items = resolve(value["$each"], scope)
		if items is None:
			return []
		if not isinstance(items, list | tuple):
			raise ExpressionError(_("$each needs a list, got {0}.").format(type(items).__name__))
		template = {key: item for key, item in value.items() if key != "$each"}
		return [resolve_all(template, {**scope, "row": attr_dicts(item)}) for item in items]
	if isinstance(value, dict):
		return {key: resolve_all(item, scope) for key, item in value.items()}
	if isinstance(value, list):
		return [resolve_all(item, scope) for item in value]
	return resolve(value, scope)


def render_all(value, scope: dict):
	"""Render every template string inside a config value (dicts and lists included)."""
	if isinstance(value, dict):
		return {key: render_all(item, scope) for key, item in value.items()}
	if isinstance(value, list):
		return [render_all(item, scope) for item in value]
	return render(value, scope)


def evaluate(condition: str, scope: dict):
	if not condition or not str(condition).strip():
		raise ExpressionError(_("The condition is empty."))
	try:
		# The scope goes in as globals: nested generator expressions cannot see eval locals.
		return frappe.safe_eval(str(condition), {**CONDITION_BUILTINS, **scope}, None)
	except Exception as error:
		raise ExpressionError(_("Could not evaluate {0}: {1}").format(condition, error)) from error


def check_template(template) -> str | None:
	"""Return an error message if a template does not parse, else None."""
	if not isinstance(template, str) or ("{{" not in template and "{%" not in template):
		return None
	if ".__" in template:
		return _("Templates may not use names that start with an underscore.")
	try:
		from frappe.utils.jinja import get_jenv

		get_jenv().parse(template)
	except Exception as error:
		return _("Template does not parse: {0}").format(error)
	return None


def check_templates(value) -> list[str]:
	"""check_template() for every string inside a config value."""
	if isinstance(value, dict):
		return [problem for item in value.values() for problem in check_templates(item)]
	if isinstance(value, list):
		return [problem for item in value for problem in check_templates(item)]
	problem = check_template(value)
	return [problem] if problem else []


def references(value) -> set[str]:
	"""Node ids referenced as nodes.<id> anywhere inside a config value."""
	if isinstance(value, dict):
		return set().union(*(references(item) for item in value.values())) if value else set()
	if isinstance(value, list):
		return set().union(*(references(item) for item in value)) if value else set()
	if isinstance(value, str):
		return set(NODE_REFERENCE.findall(value))
	return set()


def check_condition(condition) -> str | None:
	if not condition or not str(condition).strip():
		return _("The condition is empty.")
	try:
		compile(str(condition), "<condition>", "eval")
	except SyntaxError as error:
		return _("Condition does not parse: {0}").format(error.msg)
	return None
