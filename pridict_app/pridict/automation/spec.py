"""Automation spec: the JSON document that both editors change and the engine compiles.

Format (schema 1), see automation/examples/ for full specs:

- schema, title, description
- trigger: {id, type, label, config, position}
- nodes: [{id, type, label, config, position}]
- edges: [{from, to, branch?}]; "END" is the implicit final node
- settings: {on_error, max_steps}

Editors change a spec only through operations (apply_ops), so the chat and the canvas
never drift apart. Structural validation is pure Python; live validation adds checks
against this site's metadata and the Run As user's permissions.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re

from pridict.automation import expressions
from pridict.automation import nodes as catalog

SCHEMA_VERSION = 1
END = "END"
MAX_STEPS_LIMIT = 2000
ON_ERROR = ("stop_and_notify", "continue")
DEFAULT_SETTINGS = {"on_error": "stop_and_notify", "max_steps": 100}
NODE_ID = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
ROW_GAP = 150


class OpError(ValueError):
	pass


def load(value) -> dict:
	"""Parse a spec from JSON text or a dict and fill in defaults."""
	spec = json.loads(value) if isinstance(value, str) else copy.deepcopy(dict(value or {}))
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


def trigger_id(spec: dict) -> str:
	return (spec.get("trigger") or {}).get("id") or "trigger"


def all_nodes(spec: dict) -> dict[str, dict]:
	"""Every node by id, the trigger included."""
	found = {}
	if spec.get("trigger"):
		found[trigger_id(spec)] = spec["trigger"]
	for node in spec.get("nodes", []):
		found[node.get("id")] = node
	return found


def outgoing(spec: dict) -> dict[str, list[dict]]:
	edges: dict[str, list[dict]] = {node_id: [] for node_id in all_nodes(spec)}
	for edge in spec.get("edges", []):
		edges.setdefault(edge.get("from"), []).append(edge)
	return edges


def needs_checkpoints(spec: dict) -> bool:
	"""Only runs that can pause (approvals, questions, waits) need durable checkpoints."""
	return any(
		(catalog.get(node.get("type")) or catalog.NodeType).category == "human"
		or node.get("type") == "logic.wait"
		for node in spec.get("nodes", [])
	)


def trigger_summary(spec: dict) -> dict:
	"""Indexed copy of the trigger kept on the Automation document."""
	from pridict.automation.nodes.triggers import to_cron

	trigger = spec.get("trigger") or {}
	config = trigger.get("config") or {}
	cron = None
	if trigger.get("type") == "trigger.schedule":
		try:
			cron = to_cron(config)
		except (ValueError, TypeError):
			cron = None
	return {
		"trigger_type": trigger.get("type"),
		"trigger_doctype": config.get("doctype"),
		"trigger_event": config.get("event"),
		"trigger_cron": cron,
	}


# ---------------------------------------------------------------------------
# Validation


def validate(spec: dict, *, live: bool = False, run_as: str | None = None) -> list[dict]:
	"""Returns [{node_id, level: error|warning, message}].

	live=True adds checks against this site's metadata and run_as's permissions.
	"""
	issues: list[dict] = []

	def add(node_id, level, message):
		issues.append({"node_id": node_id, "level": level, "message": message})

	if spec.get("schema") != SCHEMA_VERSION:
		add(None, "error", f"Unsupported spec schema {spec.get('schema')!r}; expected {SCHEMA_VERSION}.")
		return issues

	trigger = spec.get("trigger")
	if not trigger:
		add(None, "error", "The automation has no trigger.")
		return issues
	start = trigger_id(spec)
	trigger_type = catalog.get(trigger.get("type"))
	if not trigger_type or trigger_type.category != "trigger":
		add(start, "error", f"Unknown trigger type {trigger.get('type')!r}.")

	seen: set[str] = {start}
	for node in spec.get("nodes", []):
		node_id = node.get("id")
		if not node_id or node_id == END:
			add(node_id, "error", "Every node needs an id other than END.")
			continue
		if node_id in seen:
			add(node_id, "error", f"Duplicate node id {node_id!r}.")
		seen.add(node_id)
		node_type = catalog.get(node.get("type"))
		if not node_type:
			add(node_id, "error", f"Unknown node type {node.get('type')!r}.")
		elif node_type.category == "trigger":
			add(node_id, "error", "Only one trigger is allowed, and it belongs in 'trigger'.")

	nodes = all_nodes(spec)
	edges = outgoing(spec)
	for edge in spec.get("edges", []):
		source, target = edge.get("from"), edge.get("to")
		if source not in nodes:
			add(None, "error", f"An edge starts at unknown node {source!r}.")
		if target != END and target not in nodes:
			add(source, "error", f"An edge points to unknown node {target!r}.")
		if target == start:
			add(source, "error", "Nothing can lead back to the trigger.")

	for node_id, node in nodes.items():
		node_type = catalog.get(node.get("type"))
		if not node_type:
			continue
		out = edges.get(node_id, [])
		if node_type.terminal:
			if out:
				add(node_id, "error", "This step ends the run, so nothing can follow it.")
			continue
		if not out:
			add(node_id, "error", "This step leads nowhere. Connect it to another step or to END.")
			continue
		if node_id == start and len(out) > 1:
			add(node_id, "error", "The trigger can lead to only one first step.")
		branches = node_type.branch_names(node.get("config") or {})
		if branches:
			labels = [edge.get("branch") for edge in out]
			for label in labels:
				if label not in branches:
					add(node_id, "error", f"Unknown branch {label!r}; expected one of {', '.join(branches)}.")
			for label in branches:
				if labels.count(label) == 0:
					add(node_id, "error", f"The {label!r} branch is not connected.")
				elif labels.count(label) > 1:
					add(node_id, "error", f"The {label!r} branch is connected more than once.")
		elif node_id != start:
			if len(out) > 1:
				add(
					node_id,
					"error",
					"Only branching steps (If, Switch, Loop) can have more than one next step.",
				)
			if any(edge.get("branch") for edge in out):
				add(node_id, "error", "This step has no branches; remove the branch label.")

	reachable = _reachable(start, edges)
	for node_id in nodes:
		if node_id not in reachable:
			add(node_id, "warning", "No path from the trigger reaches this step.")
	loops = {node_id for node_id, node in nodes.items() if node.get("type") == "logic.loop"}
	if _has_cycle(edges, loops):
		add(None, "error", "The graph has a cycle. Only a Loop step may repeat work.")

	settings = spec.get("settings") or {}
	max_steps = settings.get("max_steps")
	if not isinstance(max_steps, int) or not 1 <= max_steps <= MAX_STEPS_LIMIT:
		add(None, "error", f"settings.max_steps must be between 1 and {MAX_STEPS_LIMIT}.")
	if settings.get("on_error") not in ON_ERROR:
		add(None, "error", f"settings.on_error must be one of {', '.join(ON_ERROR)}.")

	for node_id, node in nodes.items():
		node_type = catalog.get(node.get("type"))
		if node_type:
			for message in node_type.check_config(node.get("config") or {}):
				add(node_id, "error", message)

	issues += _reference_issues(spec, nodes, edges, start, reachable)

	if live and not has_errors(issues):
		trigger_doctype = (trigger.get("config") or {}).get("doctype")
		for node_id, node in nodes.items():
			node_type = catalog.get(node.get("type"))
			config = dict(node.get("config") or {})
			if node_type.defaults_to_trigger_doc and not config.get("doctype") and trigger_doctype:
				config["doctype"] = trigger_doctype
			seen_messages = set()
			for issue in node_type.check_live(config, run_as):
				if issue.message not in seen_messages:
					seen_messages.add(issue.message)
					add(node_id, issue.level, issue.message)
	return issues


def has_errors(issues: list[dict]) -> bool:
	return any(issue["level"] == "error" for issue in issues)


def _reference_issues(spec, nodes, edges, start, reachable) -> list[dict]:
	"""nodes.<id> must name a step that always runs before the step that uses it."""
	issues = []
	dominators = _dominators(start, edges, reachable)
	for node_id, node in nodes.items():
		for ref in sorted(expressions.references(node.get("config") or {})):
			if ref not in nodes or ref == start:
				message = f"nodes.{ref} does not exist."
				if ref == start:
					message = f"Use trigger.… instead of nodes.{ref}."
				issues.append({"node_id": node_id, "level": "error", "message": message})
			elif ref == node_id:
				issues.append(
					{"node_id": node_id, "level": "error", "message": "A step cannot use its own output."}
				)
			elif node_id in dominators and ref not in dominators[node_id]:
				issues.append(
					{
						"node_id": node_id,
						"level": "warning",
						"message": f"nodes.{ref} may not have run yet on every path to this step; "
						"it will be empty then.",
					}
				)
	return issues


def _reachable(start: str, edges: dict[str, list[dict]]) -> set[str]:
	seen, stack = set(), [start]
	while stack:
		node = stack.pop()
		if node in seen or node == END:
			continue
		seen.add(node)
		stack.extend(edge.get("to") for edge in edges.get(node, []))
	return seen


def _dominators(start: str, edges: dict[str, list[dict]], reachable: set[str]) -> dict[str, set[str]]:
	"""For each reachable node, the nodes that lie on every path from the trigger to it."""
	preds: dict[str, set[str]] = {node: set() for node in reachable}
	for source in reachable:
		for edge in edges.get(source, []):
			if edge.get("to") in preds:
				preds[edge["to"]].add(source)
	dom = {node: set(reachable) for node in reachable}
	dom[start] = {start}
	changed = True
	while changed:
		changed = False
		for node in reachable - {start}:
			incoming = [dom[p] for p in preds[node]]
			new = (set.intersection(*incoming) if incoming else set()) | {node}
			if new != dom[node]:
				dom[node], changed = new, True
	return {node: found - {node} for node, found in dom.items()}


def _has_cycle(edges: dict[str, list[dict]], blockers: set[str]) -> bool:
	"""True if a cycle exists that does not pass through a blocker (Loop) node."""
	state: dict[str, int] = {}

	def visit(node: str) -> bool:
		state[node] = 1
		for edge in edges.get(node, []):
			target = edge.get("to")
			if target == END or target not in edges or target in blockers:
				continue
			if state.get(target) == 1 or (state.get(target) is None and visit(target)):
				return True
		state[node] = 2
		return False

	return any(state.get(node) is None and visit(node) for node in list(edges) if node not in blockers)


# ---------------------------------------------------------------------------
# Operations


def merge_patch(target, patch):
	"""JSON Merge Patch (RFC 7386): null removes a key, objects merge, anything else replaces."""
	if not isinstance(patch, dict):
		return copy.deepcopy(patch)
	result = copy.deepcopy(target) if isinstance(target, dict) else {}
	for key, value in patch.items():
		if value is None:
			result.pop(key, None)
		else:
			result[key] = merge_patch(result.get(key), value)
	return result


def apply_ops(spec: dict, ops: list[dict]) -> dict:
	"""Return a new spec with the operations applied, or raise OpError."""
	spec = load(spec)
	if not isinstance(ops, list) or not ops:
		raise OpError("No operations given.")
	for index, op in enumerate(ops, 1):
		if not isinstance(op, dict) or op.get("op") not in OPS:
			raise OpError(f"Operation {index}: unknown op {op.get('op') if isinstance(op, dict) else op!r}.")
		try:
			OPS[op["op"]](spec, op)
		except OpError as error:
			raise OpError(f"Operation {index} ({op['op']}): {error}") from None
	return spec


def _node(spec: dict, node_id) -> dict:
	for node in spec["nodes"]:
		if node.get("id") == node_id:
			return node
	raise OpError(f"No step with id {node_id!r}.")


def _new_id(spec: dict, node_type: str) -> str:
	base = node_type.split(".")[-1]
	taken = set(all_nodes(spec))
	if base not in taken:
		return base
	number = 2
	while f"{base}_{number}" in taken:
		number += 1
	return f"{base}_{number}"


def _check_type(node_type) -> catalog.NodeType:
	found = catalog.get(node_type)
	if not found:
		raise OpError(f"Unknown node type {node_type!r}.")
	return found


def _op_set_trigger(spec: dict, op: dict):
	found = _check_type(op.get("type"))
	if found.category != "trigger":
		raise OpError(f"{op.get('type')} is not a trigger.")
	old = spec.get("trigger") or {}
	spec["trigger"] = {
		"id": old.get("id") or "trigger",
		"type": op["type"],
		"label": op.get("label") or old.get("label") or found.label,
		"config": op.get("config") or {},
		"position": old.get("position") or [0, 0],
	}


def _op_add_node(spec: dict, op: dict):
	found = _check_type(op.get("type"))
	if found.category == "trigger":
		raise OpError("Use set_trigger to change the trigger.")
	node_id = op.get("id") or _new_id(spec, op["type"])
	if not NODE_ID.match(node_id):
		raise OpError(f"Step id {node_id!r} must be lower case letters, digits and underscores.")
	if node_id in all_nodes(spec) or node_id == END:
		raise OpError(f"Step id {node_id!r} is already used.")
	after, branch = op.get("after"), op.get("branch")
	nodes = all_nodes(spec)
	if after is not None and after not in nodes:
		raise OpError(f"No step with id {after!r} to add after.")
	position = op.get("position")
	if not position:
		if after:
			x, y = nodes[after].get("position") or [0, 0]
			position = [x, y + ROW_GAP]
		else:
			# Unconnected steps go beside the graph, out of the way of existing edges.
			points = [n.get("position") or [0, 0] for n in nodes.values()] or [[0, 0]]
			position = [max(p[0] for p in points) + 300, min(p[1] for p in points) + ROW_GAP]
	spec["nodes"].append(
		{
			"id": node_id,
			"type": op["type"],
			"label": op.get("label") or found.label,
			"config": op.get("config") or {},
			"position": position,
		}
	)
	if after is not None:
		# Insert between `after` and whatever it led to on that branch.
		existing = [e for e in spec["edges"] if e.get("from") == after and e.get("branch") == branch]
		spec["edges"] = [e for e in spec["edges"] if e not in existing]
		spec["edges"].append(_edge(after, node_id, branch))
		if existing and not found.terminal:
			first = (found.branch_names(op.get("config") or {}) or (None,))[0]
			spec["edges"].append(_edge(node_id, existing[0]["to"], first))


def _op_update_node(spec: dict, op: dict):
	node_id = op.get("id")
	node = spec["trigger"] if node_id == trigger_id(spec) and spec.get("trigger") else _node(spec, node_id)
	if "label" in op:
		node["label"] = op["label"]
	if "config_patch" in op:
		node["config"] = merge_patch(node.get("config") or {}, op["config_patch"])


def _op_remove_node(spec: dict, op: dict):
	node = _node(spec, op.get("id"))
	node_id = node["id"]
	incoming = [e for e in spec["edges"] if e.get("to") == node_id]
	outgoing_edges = [e for e in spec["edges"] if e.get("from") == node_id]
	spec["nodes"].remove(node)
	spec["edges"] = [e for e in spec["edges"] if node_id not in (e.get("from"), e.get("to"))]
	targets = {e.get("to") for e in outgoing_edges}
	if op.get("reconnect") and len(targets) == 1:
		target = targets.pop()
		for edge in incoming:
			spec["edges"].append(_edge(edge["from"], target, edge.get("branch")))


def _op_connect(spec: dict, op: dict):
	source, target, branch = op.get("from"), op.get("to"), op.get("branch")
	nodes = all_nodes(spec)
	if source not in nodes:
		raise OpError(f"No step with id {source!r}.")
	if target != END and target not in nodes:
		raise OpError(f"No step with id {target!r}.")
	# One edge per (source, branch): connecting replaces the old target.
	spec["edges"] = [e for e in spec["edges"] if not (e.get("from") == source and e.get("branch") == branch)]
	spec["edges"].append(_edge(source, target, branch))


def _op_disconnect(spec: dict, op: dict):
	before = len(spec["edges"])
	spec["edges"] = [
		e
		for e in spec["edges"]
		if not (
			e.get("from") == op.get("from")
			and e.get("to") == op.get("to")
			and e.get("branch") == op.get("branch")
		)
	]
	if len(spec["edges"]) == before:
		raise OpError("No such connection.")


def _op_move_node(spec: dict, op: dict):
	position = op.get("position")
	if not (
		isinstance(position, list)
		and len(position) == 2
		and all(isinstance(v, int | float) for v in position)
	):
		raise OpError("position must be [x, y].")
	node_id = op.get("id")
	node = spec["trigger"] if node_id == trigger_id(spec) and spec.get("trigger") else _node(spec, node_id)
	node["position"] = [round(position[0]), round(position[1])]


def _op_set_settings(spec: dict, op: dict):
	spec["settings"] = merge_patch(spec.get("settings") or {}, op.get("settings_patch") or {})


def _op_set_meta(spec: dict, op: dict):
	for key in ("title", "description"):
		if key in op:
			spec[key] = op[key]


def _edge(source: str, target: str, branch: str | None) -> dict:
	edge = {"from": source, "to": target}
	if branch:
		edge["branch"] = branch
	return edge


OPS = {
	"set_trigger": _op_set_trigger,
	"add_node": _op_add_node,
	"update_node": _op_update_node,
	"remove_node": _op_remove_node,
	"connect": _op_connect,
	"disconnect": _op_disconnect,
	"move_node": _op_move_node,
	"set_settings": _op_set_settings,
	"set_meta": _op_set_meta,
}


def describe_ops(ops: list[dict]) -> str:
	"""Short human summary of an op batch, for the change log."""
	words = {
		"set_trigger": "changed the trigger",
		"add_node": "added {label}",
		"update_node": "changed {id}",
		"remove_node": "removed {id}",
		"connect": "connected {from} → {to}",
		"disconnect": "disconnected {from} → {to}",
		"move_node": "moved {id}",
		"set_settings": "changed settings",
		"set_meta": "renamed",
	}
	if all(op.get("op") == "move_node" for op in ops):
		return "moved " + ", ".join(str(op.get("id")) for op in ops)[:480]
	parts = []
	for op in ops:
		template = words.get(op.get("op"), op.get("op") or "?")
		node_type = catalog.get(op.get("type"))
		label = op.get("label") or (node_type.label if node_type else op.get("type"))
		values = {**{k: v for k, v in op.items() if isinstance(v, str)}, "label": label}
		try:
			parts.append(template.format(**values))
		except KeyError:
			parts.append(op.get("op") or "?")
	return "; ".join(parts)[:500]
