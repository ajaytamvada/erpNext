"""Automation spec: the JSON document that both editors change and the engine compiles.

Format (schema 1), see automation/examples/ for full specs:

- schema, title, description
- trigger: {id, type, label, config, position}
- nodes: [{id, type, label, config, position}]
- edges: [{from, to, branch?}]; "END" is the implicit final node
- settings: {on_error, max_steps}

Pure Python apart from the node catalog lookup, so validation is unit-testable.
"""

from __future__ import annotations

import hashlib
import json

from pridict.automation import nodes as catalog

SCHEMA_VERSION = 1
END = "END"
MAX_STEPS_LIMIT = 200
DEFAULT_SETTINGS = {"on_error": "stop_and_notify", "max_steps": 50}


def load(value) -> dict:
	"""Parse a spec from JSON text or a dict and fill in defaults."""
	spec = json.loads(value) if isinstance(value, str) else dict(value or {})
	spec.setdefault("schema", SCHEMA_VERSION)
	spec.setdefault("nodes", [])
	spec.setdefault("edges", [])
	spec["settings"] = {**DEFAULT_SETTINGS, **(spec.get("settings") or {})}
	return spec


def canonical(spec: dict) -> str:
	"""Stable JSON text: the same spec always gives the same string (and hash)."""
	return json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def spec_hash(spec: dict) -> str:
	return hashlib.sha256(canonical(spec).encode()).hexdigest()


def all_nodes(spec: dict) -> dict[str, dict]:
	"""Every node by id, the trigger included."""
	found = {}
	if spec.get("trigger"):
		found[spec["trigger"].get("id") or "trigger"] = spec["trigger"]
	for node in spec.get("nodes", []):
		found[node.get("id")] = node
	return found


def outgoing(spec: dict) -> dict[str, list[dict]]:
	edges: dict[str, list[dict]] = {node_id: [] for node_id in all_nodes(spec)}
	for edge in spec.get("edges", []):
		edges.setdefault(edge.get("from"), []).append(edge)
	return edges


def trigger_summary(spec: dict) -> dict:
	"""Indexed copy of the trigger kept on the Automation document."""
	trigger = spec.get("trigger") or {}
	config = trigger.get("config") or {}
	return {
		"trigger_type": trigger.get("type"),
		"trigger_doctype": config.get("doctype"),
		"trigger_event": config.get("event"),
	}


def validate(spec: dict) -> list[dict]:
	"""Structural checks. Returns [{node_id, level: error|warning, message}]."""
	issues: list[dict] = []

	def error(node_id, message):
		issues.append({"node_id": node_id, "level": "error", "message": message})

	def warning(node_id, message):
		issues.append({"node_id": node_id, "level": "warning", "message": message})

	if spec.get("schema") != SCHEMA_VERSION:
		error(None, f"Unsupported spec schema {spec.get('schema')!r}; expected {SCHEMA_VERSION}.")
		return issues

	trigger = spec.get("trigger")
	if not trigger:
		error(None, "The automation has no trigger.")
		return issues
	trigger_id = trigger.get("id") or "trigger"
	trigger_type = catalog.get(trigger.get("type"))
	if not trigger_type or trigger_type.category != "trigger":
		error(trigger_id, f"Unknown trigger type {trigger.get('type')!r}.")

	seen: set[str] = {trigger_id}
	for node in spec.get("nodes", []):
		node_id = node.get("id")
		if not node_id or node_id == END:
			error(node_id, "Every node needs an id other than END.")
			continue
		if node_id in seen:
			error(node_id, f"Duplicate node id {node_id!r}.")
		seen.add(node_id)
		node_type = catalog.get(node.get("type"))
		if not node_type:
			error(node_id, f"Unknown node type {node.get('type')!r}.")
		elif node_type.category == "trigger":
			error(node_id, "Only one trigger is allowed, and it belongs in 'trigger'.")

	nodes = all_nodes(spec)
	edges = outgoing(spec)
	for edge in spec.get("edges", []):
		source, target = edge.get("from"), edge.get("to")
		if source not in nodes:
			error(None, f"An edge starts at unknown node {source!r}.")
		if target != END and target not in nodes:
			error(source, f"An edge points to unknown node {target!r}.")
		if target == trigger_id:
			error(source, "Nothing can lead back to the trigger.")

	for node_id, node in nodes.items():
		node_type = catalog.get(node.get("type"))
		if not node_type:
			continue
		out = edges.get(node_id, [])
		if not out:
			error(node_id, "This step leads nowhere. Connect it to another step or to END.")
			continue
		if node_type.branches:
			labels = [edge.get("branch") for edge in out]
			for label in labels:
				if label not in node_type.branches:
					error(
						node_id, f"Unknown branch {label!r}; expected one of {', '.join(node_type.branches)}."
					)
			for label in node_type.branches:
				if labels.count(label) == 0:
					error(node_id, f"The {label!r} branch is not connected.")
				elif labels.count(label) > 1:
					error(node_id, f"The {label!r} branch is connected more than once.")
		else:
			if len(out) > 1:
				error(node_id, "Only branching steps (If, Switch) can have more than one next step.")
			if any(edge.get("branch") for edge in out):
				error(node_id, "This step has no branches; remove the branch label.")

	reachable = _reachable(trigger_id, edges)
	for node_id in nodes:
		if node_id not in reachable:
			warning(node_id, "No path from the trigger reaches this step.")
	if _has_cycle(edges):
		# Loops arrive with logic.loop in Phase 4; until then every cycle is an error.
		error(None, "The graph has a cycle. Use a Loop step to repeat work.")

	max_steps = spec.get("settings", {}).get("max_steps")
	if not isinstance(max_steps, int) or not 1 <= max_steps <= MAX_STEPS_LIMIT:
		error(None, f"settings.max_steps must be between 1 and {MAX_STEPS_LIMIT}.")

	for node_id, node in nodes.items():
		node_type = catalog.get(node.get("type"))
		if node_type:
			for message in node_type.check_config(node.get("config") or {}):
				error(node_id, message)
	return issues


def has_errors(issues: list[dict]) -> bool:
	return any(issue["level"] == "error" for issue in issues)


def _reachable(start: str, edges: dict[str, list[dict]]) -> set[str]:
	seen, stack = set(), [start]
	while stack:
		node = stack.pop()
		if node in seen or node == END:
			continue
		seen.add(node)
		stack.extend(edge.get("to") for edge in edges.get(node, []))
	return seen


def _has_cycle(edges: dict[str, list[dict]]) -> bool:
	state: dict[str, int] = {}

	def visit(node: str) -> bool:
		state[node] = 1
		for edge in edges.get(node, []):
			target = edge.get("to")
			if target == END or target not in edges:
				continue
			if state.get(target) == 1 or (state.get(target) is None and visit(target)):
				return True
		state[node] = 2
		return False

	return any(state.get(node) is None and visit(node) for node in list(edges))
