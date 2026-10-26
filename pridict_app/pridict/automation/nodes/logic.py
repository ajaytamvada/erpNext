"""Logic node types: control which path a run takes."""

from __future__ import annotations

from pridict.automation import expressions
from pridict.automation.nodes import NodeResult, NodeType, register


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
			problem = expressions.check_condition(config["condition"])
			if problem:
				messages.append(problem)
		return messages

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		result = bool(expressions.evaluate(config["condition"], scope))
		branch = "true" if result else "false"
		return NodeResult(
			output={"result": result}, route=branch, summary=f"{config['condition']} → {branch}"
		)
