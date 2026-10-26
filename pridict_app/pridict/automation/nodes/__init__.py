"""Node catalog: every step type an automation can use.

Each node type is a NodeType subclass registered with @register. The catalog is code; the
canvas and (later) the AI architect read it through describe().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

CATEGORIES = ("trigger", "data", "logic", "action", "human", "ai")
_REGISTRY: dict[str, type[NodeType]] = {}


@dataclass
class NodeResult:
	output: dict = field(default_factory=dict)  # stored under nodes.<id> for later steps
	route: str | None = None  # branch to follow, for branching nodes
	summary: str = ""  # one line for the run trace
	vars: dict = field(default_factory=dict)  # values to store under vars.<name>
	stop: dict | None = None  # {"status", "message"} ends the run (logic.stop)
	loops: dict = field(default_factory=dict)  # loop bookkeeping (logic.loop)


@dataclass
class Issue:
	level: str  # "error" | "warning"
	message: str
	# "design": the automation itself is wrong. "setup": the site needs something first
	# (the Run As user's permissions, an email account) that only an administrator can give.
	kind: str = "design"


class NodeType:
	type: ClassVar[str]
	label: ClassVar[str]
	category: ClassVar[str]
	description: ClassVar[str] = ""
	icon: ClassVar[str] = ""
	# Branch labels for branching nodes, in display order; empty for single-exit nodes.
	branches: ClassVar[tuple[str, ...]] = ()
	# Terminal nodes end the run and have no outgoing edge.
	terminal: ClassVar[bool] = False
	# Nodes whose DocType/name default to the trigger document (checked against it).
	defaults_to_trigger_doc: ClassVar[bool] = False
	# JSON Schema for config. Later phases build the settings form and AI tools from it.
	config_schema: ClassVar[dict] = {"type": "object", "properties": {}}
	outputs: ClassVar[tuple[str, ...]] = ()

	def branch_names(self, config: dict) -> tuple[str, ...]:
		"""Branches for this node's config (Switch derives them from its cases)."""
		return self.branches

	def check_config(self, config: dict) -> list[str]:
		"""Static checks on a node's config; return error messages."""
		messages = []
		for key in self.config_schema.get("required", []):
			if config.get(key) in (None, "", [], {}):
				messages.append(f"'{key}' is required.")
		return messages

	def check_live(self, config: dict, run_as: str | None) -> list[Issue]:
		"""Checks against this site's metadata and the Run As user's permissions."""
		return []

	def execute(self, ctx, config: dict, scope: dict) -> NodeResult:
		raise NotImplementedError

	@classmethod
	def describe(cls) -> dict[str, Any]:
		return {
			"type": cls.type,
			"label": cls.label,
			"category": cls.category,
			"description": cls.description,
			"icon": cls.icon,
			"branches": list(cls.branches),
			"terminal": cls.terminal,
			"outputs": list(cls.outputs),
			"config_schema": cls.config_schema,
		}


def register(cls: type[NodeType]) -> type[NodeType]:
	assert cls.category in CATEGORIES, cls.category
	_REGISTRY[cls.type] = cls
	return cls


def get(node_type: str | None) -> NodeType | None:
	cls = _REGISTRY.get(node_type or "")
	return cls() if cls else None


def describe_all() -> list[dict]:
	return [cls.describe() for cls in _REGISTRY.values()]


# Import the modules that register node types.
from pridict.automation.nodes import actions, data, logic, triggers  # noqa: E402, F401
