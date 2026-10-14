"""Static checks for code-defined workflow graphs. Pure Python so it is unit-testable."""

from __future__ import annotations

END = "END"


def _edges(workflow: dict) -> dict[str, list[tuple[str, str]]]:
	return {node["id"]: [tuple(edge) for edge in node.get("next", [])] for node in workflow["nodes"]}


def _reachable(start: str, edges: dict, stop_at: set[str] | None = None) -> set[str]:
	"""Nodes reachable from start. Nodes in stop_at are visited but not expanded."""
	seen, stack = set(), [start]
	while stack:
		node = stack.pop()
		if node in seen or node == END:
			continue
		seen.add(node)
		if stop_at and node in stop_at and node != start:
			continue
		stack.extend(target for _, target in edges.get(node, []))
	return seen


def _cycles_without(edges: dict, blockers: set[str]) -> bool:
	"""True if a cycle exists that does not pass through any blocker node."""
	nodes = [n for n in edges if n not in blockers]
	state: dict[str, int] = {}

	def visit(node: str) -> bool:
		state[node] = 1
		for _, target in edges.get(node, []):
			if target == END or target in blockers:
				continue
			if state.get(target) == 1 or (state.get(target) is None and visit(target)):
				return True
		state[node] = 2
		return False

	return any(state.get(n) is None and visit(n) for n in nodes)


def validate_workflow(
	workflow: dict, tool_access: dict[str, str], max_steps: int | None = None
) -> list[dict]:
	"""Return [{check, result: PASS|WARN|FAIL, detail}] for the graph.

	tool_access maps tool name -> Agent Tool access ("Read", "Write (draft)", ...).
	"""
	edges = _edges(workflow)
	nodes = {node["id"]: node for node in workflow["nodes"]}
	human = {n for n, node in nodes.items() if node["kind"] == "human"}
	results = []

	def add(check, ok, detail, warn=False):
		results.append(
			{"check": check, "result": "PASS" if ok else ("WARN" if warn else "FAIL"), "detail": detail}
		)

	unknown = sorted({t for e in edges.values() for _, t in e if t != END and t not in nodes})
	add("Every edge points to an existing node", not unknown, ", ".join(unknown) or "All targets exist")

	reachable = _reachable(workflow["entry"], edges)
	orphans = sorted(set(nodes) - reachable)
	add(
		"Every node is reachable from the entry point",
		not orphans,
		", ".join(orphans) or f"{len(nodes)} of {len(nodes)} reachable",
	)

	dead_ends = sorted(n for n, e in edges.items() if not e)
	add(
		"Every path ends at END or a human pause",
		not dead_ends,
		f"No outgoing edge: {', '.join(dead_ends)}" if dead_ends else "Every node has an exit",
	)

	write_nodes = {
		n
		for n, node in nodes.items()
		if any(tool_access.get(t, "Read") != "Read" for t in node.get("tools", []))
	}
	before_approval = _reachable(workflow["entry"], edges, stop_at=human) - human
	unguarded = sorted(write_nodes & before_approval)
	add(
		"Write tools are only reachable after a human approval node",
		not unguarded,
		f"Reachable without approval: {', '.join(unguarded)}"
		if unguarded
		else f"{len(write_nodes)} write step(s), all behind approval",
	)

	bad_routers = sorted(
		n
		for n, e in edges.items()
		if (nodes[n]["kind"] == "router" and len(e) < 2) or (len(e) > 1 and any(not cond for cond, _ in e))
	)
	add(
		"Router edges cover every possible outcome",
		not bad_routers,
		f"Unlabelled or single branch: {', '.join(bad_routers)}"
		if bad_routers
		else "Every branch has a labelled condition",
	)

	free_loop = _cycles_without(edges, human)
	add(
		"Loops pause for a person or are bounded by the step limit",
		not free_loop,
		f"A loop without a human pause exists; bounded only by max steps ({max_steps or 'unset'})"
		if free_loop
		else "Every loop passes through a human pause",
		warn=bool(max_steps),
	)
	return results
