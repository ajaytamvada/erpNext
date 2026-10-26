<template>
	<VueFlow
		:nodes="flowNodes"
		:edges="flowEdges"
		:nodes-draggable="false"
		:nodes-connectable="false"
		:edges-updatable="false"
		:zoom-on-double-click="false"
		:min-zoom="0.3"
		:max-zoom="1.5"
		fit-view-on-init
		@node-click="({ node }) => emit('select', node.id === END ? null : node.id)"
		@pane-click="emit('select', null)"
	>
		<Background pattern-color="var(--gray-300)" :gap="20" />
		<template #node-automation="{ data }">
			<NodeCard v-bind="data" />
		</template>
		<template #node-end>
			<div class="ab-end">
				<Handle type="target" :position="Position.Top" :connectable="false" />
				{{ __("END") }}
			</div>
		</template>
	</VueFlow>
</template>

<script setup>
import { computed, watch, nextTick } from "vue";
import { VueFlow, Handle, Position, MarkerType, useVueFlow } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import NodeCard from "./NodeCard.vue";

const END = "END";
const BRANCH_LABELS = { true: __("yes"), false: __("no") };

const props = defineProps({
	spec: Object,
	catalog: Object,
	validation: Array,
	run: Object,
	selected: String,
});
const emit = defineEmits(["select"]);
const { fitView } = useVueFlow();

const specNodes = computed(() => {
	const trigger = props.spec.trigger ? [{ ...props.spec.trigger, id: props.spec.trigger.id || "trigger" }] : [];
	return [...trigger, ...props.spec.nodes];
});

const steps = computed(() => props.run?.steps || {});
const ran = (id) => Boolean(steps.value[id]);

function nodeStatus(node, isTrigger) {
	if (!props.run) return null;
	if (isTrigger) return "completed";
	const step = steps.value[node.id];
	return step ? step.status.toLowerCase() : "not-reached";
}

// A trigger edge is taken when the run started; any other edge when its source ran and
// (for branching steps) chose this branch.
function edgeTaken(edge) {
	if (!props.run) return false;
	const triggerId = props.spec.trigger?.id || "trigger";
	if (edge.from === triggerId) return true;
	const step = steps.value[edge.from];
	if (!step || step.status !== "Completed") return false;
	if (edge.branch) return step.route === edge.branch;
	return true;
}

const flowNodes = computed(() => {
	const triggerId = props.spec.trigger?.id || "trigger";
	const nodes = specNodes.value.map((node) => {
		const meta = props.catalog[node.type] || {};
		const isTrigger = node.id === triggerId;
		const issues = props.validation.filter((i) => i.node_id === node.id);
		const [x, y] = node.position || [0, 0];
		return {
			id: node.id,
			type: "automation",
			position: { x, y },
			data: {
				label: node.label || meta.label || node.id,
				typeLabel: meta.label || node.type,
				category: meta.category || "unknown",
				icon: meta.icon || "•",
				branches: meta.branches || [],
				isTrigger,
				status: nodeStatus(node, isTrigger),
				issue: issues.some((i) => i.level === "error") ? "error" : issues.length ? "warning" : null,
				selected: props.selected === node.id,
			},
		};
	});
	const endSources = props.spec.edges.filter((e) => e.to === END).map((e) => e.from);
	if (endSources.length) {
		const positions = specNodes.value.map((n) => n.position || [0, 0]);
		const sourceXs = specNodes.value.filter((n) => endSources.includes(n.id)).map((n) => (n.position || [0, 0])[0]);
		nodes.push({
			id: END,
			type: "end",
			position: {
				x: sourceXs.reduce((a, b) => a + b, 0) / sourceXs.length + 70,
				y: Math.max(...positions.map((p) => p[1])) + 150,
			},
			data: {},
		});
	}
	return nodes;
});

const flowEdges = computed(() =>
	props.spec.edges.map((edge, index) => {
		const taken = edgeTaken(edge);
		return {
			id: `e${index}-${edge.from}-${edge.to}-${edge.branch || ""}`,
			source: edge.from,
			target: edge.to,
			sourceHandle: edge.branch ? `branch-${edge.branch}` : null,
			type: "smoothstep",
			label: edge.branch ? BRANCH_LABELS[edge.branch] || edge.branch : undefined,
			markerEnd: MarkerType.ArrowClosed,
			animated: taken && props.run?.status === "Running",
			class: taken ? "ab-edge-taken" : props.run ? "ab-edge-idle" : "",
		};
	})
);

// Re-fit when a different automation is shown.
watch(
	() => props.spec.title,
	() => nextTick(() => fitView({ padding: 0.2 }))
);
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
.ab-canvas .vue-flow__edge-path {
	stroke: var(--gray-400);
	stroke-width: 1.5;
}
.ab-canvas .ab-edge-taken .vue-flow__edge-path {
	stroke: var(--green-500);
	stroke-width: 2.5;
}
.ab-canvas .ab-edge-idle .vue-flow__edge-path {
	stroke-dasharray: 4 4;
}
.ab-canvas .vue-flow__edge-text {
	font-size: 12px;
	fill: var(--text-color);
}
.ab-canvas .vue-flow__edge-textbg {
	fill: var(--card-bg);
}
</style>
