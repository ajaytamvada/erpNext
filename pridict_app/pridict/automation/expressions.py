"""Expressions inside automation specs.

Text fields are Jinja templates rendered in Frappe's sandboxed environment; conditions go
through frappe.safe_eval, the restricted evaluator Frappe Notifications use. Document
values are always passed in as data (the scope), never pasted into the expression.
"""

from __future__ import annotations

import json

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


class ExpressionError(Exception):
	pass


def to_data(value):
	"""JSON-safe copy (dates become strings) so values can live in LangGraph checkpoints."""
	return json.loads(frappe.as_json(value))


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
		return frappe.safe_eval(str(condition), dict(CONDITION_BUILTINS), dict(scope))
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


def check_condition(condition) -> str | None:
	if not condition or not str(condition).strip():
		return _("The condition is empty.")
	try:
		compile(str(condition), "<condition>", "eval")
	except SyntaxError as error:
		return _("Condition does not parse: {0}").format(error.msg)
	return None
