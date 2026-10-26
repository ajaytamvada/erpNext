"""Logic node types: control which path a run takes."""

from __future__ import annotations

from frappe import _

from pridict.automation import expressions
from pridict.automation.nodes import NodeResult, NodeType, register

MAX_LOOP_ITEMS = expressions.MAX_LIST_ITEMS


def _condition_messages(condition) -> list[str]:
	problem = expressions.check_condition(condition)
	return [problem] if problem else []


@register
class If(NodeType):
	type = "logic.if"
	label = "If"
	category = "logic"
	icon = "◆"
	description = "Follows the 'true' branch when the condition holds, otherwise 'false'."
	branches = ("true", "false")
	config_schema = {
		"type": "object",
		"required": ["condition"],
		"properties": {"condition": {"type": "string", "title": "Condition", "format": "condition"}},
	}

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config)
		if config.get("condition"):
			messages += _condition_messages(config["condition"])
		return messages

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		result = bool(expressions.evaluate(config["condition"], scope))
		branch = "true" if result else "false"
		return NodeResult(
			output={"result": result}, route=branch, summary=f"{config['condition']} → {branch}"
		)


@register
class Switch(NodeType):
	type = "logic.switch"
	label = "Switch"
	category = "logic"
	icon = "⑂"
	description = "Follows the first case whose condition holds, otherwise 'default'."
	config_schema = {
		"type": "object",
		"required": ["cases"],
		"properties": {
			"cases": {
				"type": "array",
				"title": "Cases",
				"items": {
					"type": "object",
					"required": ["name", "condition"],
					"properties": {
						"name": {"type": "string", "title": "Branch name"},
						"condition": {"type": "string", "title": "Condition", "format": "condition"},
					},
				},
			}
		},
	}

	def branch_names(self, config: dict) -> tuple[str, ...]:
		cases = [case.get("name") for case in config.get("cases") or [] if isinstance(case, dict)]
		return (*cases, "default")

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config)
		names = []
		for case in config.get("cases") or []:
			name = case.get("name") if isinstance(case, dict) else None
			if not name:
				messages.append("Every case needs a name.")
				continue
			if name == "default" or name in names:
				messages.append(f"Case name {name!r} is reserved or used twice.")
			names.append(name)
			messages += _condition_messages(case.get("condition"))
		return messages

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		for case in config["cases"]:
			if expressions.evaluate(case["condition"], scope):
				return NodeResult(
					output={"case": case["name"]}, route=case["name"], summary=f"→ {case['name']}"
				)
		return NodeResult(output={"case": "default"}, route="default", summary="→ default")


@register
class SetVariable(NodeType):
	type = "logic.set_variable"
	label = "Set variable"
	category = "logic"
	icon = "𝑥"
	description = "Computes a value and stores it as vars.<name> for later steps."
	outputs = ("value",)
	config_schema = {
		"type": "object",
		"required": ["name", "value"],
		"properties": {
			"name": {"type": "string", "title": "Variable name"},
			"value": {"title": "Value", "format": "template"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config) + expressions.check_templates(config.get("value"))
		if config.get("name") and not str(config["name"]).isidentifier():
			messages.append("The variable name must be letters, digits and underscores.")
		return messages

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		value = expressions.resolve_all(config["value"], scope)
		return NodeResult(
			output={"value": value},
			vars={config["name"]: value},
			summary=_("{0} = {1}").format(config["name"], str(value)[:120]),
		)


@register
class Stop(NodeType):
	type = "logic.stop"
	label = "Stop"
	category = "logic"
	icon = "■"
	description = "Ends the run with a status and a message."
	terminal = True
	config_schema = {
		"type": "object",
		"properties": {
			"status": {"type": "string", "title": "Status", "enum": ["Completed", "Failed"]},
			"message": {"type": "string", "title": "Message", "format": "template"},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config) + expressions.check_templates(config.get("message"))
		if config.get("status") not in (None, "Completed", "Failed"):
			messages.append("status must be Completed or Failed.")
		return messages

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		status = config.get("status") or "Completed"
		message = expressions.render(config.get("message") or "", scope)
		return NodeResult(
			output={"status": status, "message": message},
			stop={"status": status, "message": message},
			summary=_("Stopped ({0}): {1}").format(status, message),
		)


@register
class Loop(NodeType):
	type = "logic.loop"
	label = "Loop"
	category = "logic"
	icon = "↻"
	description = "Runs the 'body' branch once per item (nodes.<id>.item), then follows 'done'."
	branches = ("body", "done")
	outputs = ("item", "index", "count")
	config_schema = {
		"type": "object",
		"required": ["items"],
		"properties": {
			"items": {"type": "string", "title": "Items", "format": "template"},
			"max_items": {"type": "integer", "title": "Max items", "minimum": 1, "maximum": MAX_LOOP_ITEMS},
		},
	}

	def check_config(self, config: dict) -> list[str]:
		messages = super().check_config(config) + expressions.check_templates(config.get("items"))
		limit = config.get("max_items")
		if limit is not None and (not isinstance(limit, int) or not 1 <= limit <= MAX_LOOP_ITEMS):
			messages.append(f"max_items must be between 1 and {MAX_LOOP_ITEMS}.")
		return messages

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		node_id = scope["node"]["id"]
		current = (scope.get("loops") or {}).get(node_id)
		if current:
			items, index = current["items"], current["index"] + 1
		else:
			items = expressions.resolve(config["items"], scope)
			if items is None:
				items = []
			if not isinstance(items, list):
				raise ValueError(_("Loop items must be a list, got {0}.").format(type(items).__name__))
			items = items[: int(config.get("max_items") or MAX_LOOP_ITEMS)]
			index = 0
		if index < len(items):
			return NodeResult(
				output={"item": items[index], "index": index, "count": len(items)},
				route="body",
				loops={node_id: {"items": items, "index": index}},
				summary=_("Item {0} of {1}").format(index + 1, len(items)),
			)
		return NodeResult(
			output={"item": None, "index": None, "count": len(items)},
			route="done",
			loops={node_id: None},
			summary=_("Done after {0} items").format(len(items)),
		)
