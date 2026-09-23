from __future__ import annotations

from collections import deque

from pridict.schema_intelligence.models import SchemaSnapshot


def relationship_subgraph(
	snapshot: SchemaSnapshot,
	root_doctype: str,
	*,
	hops: int = 1,
	direction: str = "both",
	relationship_types: set[str] | None = None,
	node_limit: int = 100,
	edge_limit: int = 250,
):
	if hops not in (1, 2):
		raise ValueError("hops must be 1 or 2")
	if direction not in {"incoming", "outgoing", "both"}:
		raise ValueError("unsupported relationship direction")
	if root_doctype not in {item.name for item in snapshot.doctypes}:
		raise ValueError(f"DocType {root_doctype} is not present in the snapshot")
	relationship_types = relationship_types or {"LINK", "DYNAMIC_LINK", "CHILD_TABLE", "TABLE_MULTISELECT"}
	edges = [item for item in snapshot.relationships if item.relationship_type in relationship_types]
	visible_nodes = {root_doctype}
	visible_edges = []
	visible_edge_ids = set()
	queue = deque([(root_doctype, 0)])
	seen = {root_doctype}
	truncated = False

	while queue:
		current, depth = queue.popleft()
		if depth >= hops:
			continue
		for relationship in edges:
			targets = list(relationship.discoverable_targets) or ([relationship.target_doctype] if relationship.target_doctype else [])
			candidates = []
			if direction in {"outgoing", "both"} and relationship.source_doctype == current:
				candidates.extend(targets)
			if direction in {"incoming", "both"} and current in targets:
				candidates.append(relationship.source_doctype)
			if not candidates:
				continue
			if relationship.relationship_id in visible_edge_ids:
				continue
			if len(visible_edges) >= edge_limit:
				truncated = True
				break
			for candidate in candidates:
				if candidate not in visible_nodes and len(visible_nodes) >= node_limit:
					truncated = True
					continue
				visible_nodes.add(candidate)
				if candidate not in seen:
					seen.add(candidate)
					queue.append((candidate, depth + 1))
			edge = relationship.to_dict()
			edge["discoverable_targets"] = [
				item for item in edge["discoverable_targets"] if item in visible_nodes
			]
			visible_edges.append(edge)
			visible_edge_ids.add(relationship.relationship_id)
		if truncated and len(visible_edges) >= edge_limit:
			break

	return {
		"root_doctype": root_doctype,
		"hops": hops,
		"direction": direction,
		"nodes": sorted(visible_nodes),
		"edges": visible_edges,
		"truncated": truncated,
		"node_limit": node_limit,
		"edge_limit": edge_limit,
	}
