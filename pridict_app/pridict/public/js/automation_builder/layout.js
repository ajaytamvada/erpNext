// A small layered layout: top to bottom by longest path from the trigger, branches side by side.
const ROW = 150;
const COLUMN = 260;
const END = "END";

export function layout(spec) {
	const triggerId = spec.trigger?.id || "trigger";
	const ids = [triggerId, ...spec.nodes.map((n) => n.id)];
	const out = Object.fromEntries(ids.map((id) => [id, []]));
	for (const edge of spec.edges) {
		if (edge.to !== END && out[edge.from] && out[edge.to]) out[edge.from].push(edge);
	}
	// Drop back edges (a loop body returning to its Loop step) so the rest is a DAG.
	const forward = Object.fromEntries(ids.map((id) => [id, []]));
	const state = {};
	const visit = (id) => {
		state[id] = 1;
		for (const edge of out[id]) {
			if (state[edge.to] === 1) continue;
			forward[id].push(edge);
			if (!state[edge.to]) visit(edge.to);
		}
		state[id] = 2;
	};
	visit(triggerId);
	ids.filter((id) => !state[id]).forEach(visit);

	// Layer = longest path from the trigger.
	const layer = Object.fromEntries(ids.map((id) => [id, 0]));
	const order = topological(ids, forward);
	for (const id of order) {
		for (const edge of forward[id]) layer[edge.to] = Math.max(layer[edge.to], layer[id] + 1);
	}

	// Within a layer, order by the parents' x (and branch order), then centre the row.
	const x = { [triggerId]: 0 };
	const parents = Object.fromEntries(ids.map((id) => [id, []]));
	for (const id of ids) forward[id].forEach((edge, index) => parents[edge.to].push({ id, index, count: forward[id].length }));
	const layers = {};
	for (const id of order) (layers[layer[id]] ||= []).push(id);
	for (const depth of Object.keys(layers).map(Number).sort((a, b) => a - b)) {
		const row = layers[depth];
		const score = (id) => {
			const ps = parents[id].filter((p) => p.id in x);
			if (!ps.length) return 0;
			return ps.reduce((sum, p) => sum + x[p.id] + (p.index - (p.count - 1) / 2) * COLUMN, 0) / ps.length;
		};
		row.sort((a, b) => score(a) - score(b));
		const width = (row.length - 1) * COLUMN;
		const centre = row.reduce((sum, id) => sum + score(id), 0) / row.length;
		row.forEach((id, index) => {
			x[id] = Math.round(centre - width / 2 + index * COLUMN);
		});
	}
	return Object.fromEntries(ids.map((id) => [id, [x[id] ?? 0, layer[id] * ROW]]));
}

function topological(ids, forward) {
	const indegree = Object.fromEntries(ids.map((id) => [id, 0]));
	for (const id of ids) for (const edge of forward[id]) indegree[edge.to] += 1;
	const ready = ids.filter((id) => indegree[id] === 0);
	const order = [];
	while (ready.length) {
		const id = ready.shift();
		order.push(id);
		for (const edge of forward[id]) {
			indegree[edge.to] -= 1;
			if (indegree[edge.to] === 0) ready.push(edge.to);
		}
	}
	return order;
}
