<template>
	<VueFlow
		v-model:nodes="nodes"
		v-model:edges="edges"
		:nodes-draggable="canEdit"
		:nodes-connectable="canEdit"
		:edges-updatable="false"
		:delete-key-code="canEdit ? ['Delete', 'Backspace'] : null"
		:zoom-on-double-click="false"
		:min-zoom="0.2"
		:max-zoom="1.5"
		:default-edge-options="{ type: 'add' }"
		fit-view-on-init
		@node-click="({ node }) => store.select(node.id === END ? null : node.id)"
		@pane-click="store.select(null)"
		@node-drag-stop="onDragStop"
		@connect="onConnect"
		@nodes-change="onNodesChange"
		@edges-change="onEdgesChange"
	>
		<Background pattern-color="var(--gray-300)" :gap="20" />
		<Panel position="top-right" class="ab-toolbar">
			<button v-if="canEdit" type="button" class="btn btn-xs btn-default" @click="store.state.picker = { after: null }">
				{{ __("Add step") }}
			</button>
			<button v-if="canEdit" type="button" class="btn btn-xs btn-default" @click="tidy">{{ __("Tidy layout") }}</button>
			<button type="button" class="btn btn-xs btn-default" @click="fitView({ padding: 0.2 })">{{ __("Fit") }}</button>
			<span v-if="store.state.saving" class="ab-saving">{{ __("Saving…") }}</span>
		</Panel>
		<template #node-automation="{ data }">
			<NodeCard v-bind="data" />
		</template>
		<template #node-end>
			<div class="ab-end">
				<Handle type="target" :position="Position.Top" />
				{{ __("END") }}
			</div>
		</template>
		<template #edge-add="edgeProps">
			<AddEdge v-bind="edgeProps" />
		</template>
	</VueFlow>
</template>

<script setup>
import { computed, ref, watch, nextTick } from "vue";
import { VueFlow, Handle, Position, MarkerType, Panel, useVueFlow } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import NodeCard from "./NodeCard.vue";
import AddEdge from "./AddEdge.vue";

const END = "END";
const BRANCH_LABELS = { true: __("yes"), false: __("no"), body: __("each"), done: __("done") };

const props = defineProps({ store: Object });
const store = props.store;
const { fitView } = useVueFlow();

const data = computed(() => store.state.data);
const spec = computed(() => data.value.spec);
const canEdit = computed(() => store.canEdit.value);
const triggerId = computed(() => spec.value.trigger?.id || "trigger");
const steps = computed(() => data.value.run?.steps || {});

const nodes = ref([]);
const edges = ref([]);

function branchesOf(node) {
	const meta = data.value.catalog[node.type] || {};
	if (node.type === "logic.switch") {
		return [...(node.config?.cases || []).map((c) => c.name).filter(Boolean), "default"];
	}
	return meta.branches || [];
}

function nodeStatus(node, isTrigger) {
	if (!data.value.run) return null;
	if (isTrigger) return "completed";
	const step = steps.value[node.id];
	return step ? step.status.toLowerCase() : "not-reached";
}

// A trigger edge is taken when the run started; any other edge when its source ran and
// (for branching steps) chose this branch.
function edgeTaken(edge) {
	if (!data.value.run) return false;
	if (edge.from === triggerId.value) return true;
	const step = steps.value[edge.from];
	if (!step || step.status !== "Completed") return false;
	if (edge.branch) return step.route === edge.branch;
	return true;
}

function build() {
	const all = [spec.value.trigger ? { ...spec.value.trigger, id: triggerId.value } : null, ...spec.value.nodes].filter(Boolean);
	const outgoing = {};
	for (const edge of spec.value.edges) (outgoing[edge.from] ||= []).push(edge);
	const built = all.map((node) => {
		const meta = data.value.catalog[node.type] || {};
		const isTrigger = node.id === triggerId.value;
		const issues = data.value.validation.filter((i) => i.node_id === node.id);
		const branches = isTrigger ? [] : branchesOf(node);
		const used = new Set((outgoing[node.id] || []).map((e) => e.branch || null));
		const ends = meta.terminal ? [] : branches.length ? branches.filter((b) => !used.has(b)) : used.size ? [] : [null];
		const [x, y] = node.position || [0, 0];
		return {
			id: node.id,
			type: "automation",
			position: { x, y },
			deletable: canEdit.value && !isTrigger,
			data: {
				label: node.label || meta.label || node.id,
				typeLabel: meta.label || node.type,
				category: meta.category || "unknown",
				icon: meta.icon || "•",
				branches,
				terminal: Boolean(meta.terminal),
				isTrigger,
				status: nodeStatus(node, isTrigger),
				times: steps.value[node.id]?.times || 0,
				issue: issues.some((i) => i.level === "error") ? "error" : issues.length ? "warning" : null,
				selected: store.state.selectedNode === node.id,
				openEnds: canEdit.value ? ends : [],
				onAdd: (branch) => (store.state.picker = { after: node.id, branch }),
			},
		};
	});
	const endSources = spec.value.edges.filter((e) => e.to === END).map((e) => e.from);
	const positions = all.map((n) => n.position || [0, 0]);
	const sourceXs = all.filter((n) => endSources.includes(n.id)).map((n) => (n.position || [0, 0])[0]);
	built.push({
		id: END,
		type: "end",
		deletable: false,
		position: {
			x: (sourceXs.length ? sourceXs.reduce((a, b) => a + b, 0) / sourceXs.length : 0) + 70,
			y: Math.max(0, ...positions.map((p) => p[1])) + 150,
		},
		data: {},
	});
	nodes.value = built;
	edges.value = spec.value.edges.map((edge) => {
		const taken = edgeTaken(edge);
		return {
			id: edgeId(edge),
			source: edge.from,
			target: edge.to,
			sourceHandle: edge.branch ? `branch-${edge.branch}` : null,
			type: "add",
			markerEnd: MarkerType.ArrowClosed,
			animated: taken && data.value.run?.status === "Running",
			class: taken ? "ab-edge-taken" : data.value.run ? "ab-edge-idle" : "",
			deletable: canEdit.value,
			data: {
				spec: edge,
				label: edge.branch ? BRANCH_LABELS[edge.branch] || edge.branch : "",
				canAdd: canEdit.value,
				onAdd: () => (store.state.picker = { after: edge.from, branch: edge.branch || null }),
			},
		};
	});
}

const edgeId = (edge) => `${edge.from}->${edge.to}:${edge.branch || ""}`;

watch(() => [data.value.spec, data.value.validation, data.value.run, store.state.selectedNode, canEdit.value], build, {
	immediate: true,
	deep: true,
});

// Re-fit when a different automation is shown.
watch(
	() => store.state.name,
	() => nextTick(() => fitView({ padding: 0.2 }))
);

function onDragStop({ node }) {
	if (!canEdit.value || node.id === END) return;
	store.moveNode(node.id, [Math.round(node.position.x), Math.round(node.position.y)]);
}

function onConnect(params) {
	if (!canEdit.value || params.source === params.target) return;
	const branch = params.sourceHandle?.startsWith("branch-") ? params.sourceHandle.slice(7) : null;
	store.connect(params.source, params.target, branch);
}

// Deleting a node also removes its edges; collect both from one tick and send one batch.
const pending = { nodes: new Set(), edges: [] };

function onNodesChange(changes) {
	for (const change of changes) {
		if (change.type === "remove" && change.id !== END && change.id !== triggerId.value) pending.nodes.add(change.id);
	}
	flushSoon();
}

function onEdgesChange(changes) {
	for (const change of changes) {
		if (change.type === "remove") pending.edges.push(change.id);
	}
	flushSoon();
}

function flushSoon() {
	clearTimeout(flushSoon.timer);
	flushSoon.timer = setTimeout(() => {
		const removedNodes = [...pending.nodes];
		const ops = removedNodes.map((id) => ({ op: "remove_node", id, reconnect: true }));
		for (const id of pending.edges) {
			const edge = spec.value.edges.find((e) => edgeId(e) === id);
			if (edge && !pending.nodes.has(edge.from) && !pending.nodes.has(edge.to)) {
				ops.push({ op: "disconnect", from: edge.from, to: edge.to, ...(edge.branch ? { branch: edge.branch } : {}) });
			}
		}
		pending.nodes.clear();
		pending.edges = [];
		if (!ops.length || !canEdit.value) return build();
		if (removedNodes.includes(store.state.selectedNode)) store.select(null);
		store.applyOps(ops);
	}, 0);
}

async function tidy() {
	await store.autoLayout();
	nextTick(() => fitView({ padding: 0.2 }));
}
</script>

<style>
@import "@vue-flow/core/dist/style.css";
@import "@vue-flow/core/dist/theme-default.css";

.ab-end {
	padding: 6px 16px;
	border-radius: 999px;
	border: 1px solid var(--border-color);
	background: var(--fg-color);
	color: var(--text-muted);
	font-size: var(--text-sm);
	font-weight: 600;
}
.ab-end .vue-flow__handle {
	opacity: 0;
}
.ab-toolbar {
	display: flex;
	gap: 6px;
	align-items: center;
}
.ab-saving {
	font-size: var(--text-xs);
	color: var(--text-muted);
}
.ab-canvas .vue-flow__edge-path {
	stroke: var(--gray-400);
	stroke-width: 1.5;
}
.ab-canvas .vue-flow__edge.selected .vue-flow__edge-path {
	stroke: var(--blue-500);
	stroke-width: 2.5;
}
.ab-canvas .ab-edge-taken .vue-flow__edge-path {
	stroke: var(--green-500);
	stroke-width: 2.5;
}
.ab-canvas .ab-edge-idle .vue-flow__edge-path {
	stroke-dasharray: 4 4;
}
</style>
