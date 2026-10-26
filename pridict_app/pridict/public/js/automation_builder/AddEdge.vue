<template>
	<BaseEdge :id="id" :path="path[0]" :marker-end="markerEnd" :style="style" />
	<EdgeLabelRenderer>
		<div
			class="ab-edge-label nodrag nopan"
			:style="{ transform: `translate(-50%, -50%) translate(${path[1]}px, ${path[2]}px)` }"
		>
			<span v-if="data.label" class="ab-edge-branch">{{ data.label }}</span>
			<button
				v-if="data.canAdd"
				type="button"
				class="ab-edge-add"
				:title="__('Insert a step here')"
				@click.stop="data.onAdd()"
			>
				+
			</button>
		</div>
	</EdgeLabelRenderer>
</template>

<script setup>
import { computed } from "vue";
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from "@vue-flow/core";

const props = defineProps({
	id: String,
	sourceX: Number,
	sourceY: Number,
	targetX: Number,
	targetY: Number,
	sourcePosition: String,
	targetPosition: String,
	markerEnd: String,
	style: Object,
	data: Object,
});

const path = computed(() =>
	getSmoothStepPath({
		sourceX: props.sourceX,
		sourceY: props.sourceY,
		sourcePosition: props.sourcePosition,
		targetX: props.targetX,
		targetY: props.targetY,
		targetPosition: props.targetPosition,
	})
);
</script>

<style>
.ab-edge-label {
	position: absolute;
	display: flex;
	gap: 4px;
	align-items: center;
	pointer-events: all;
}
.ab-edge-branch {
	font-size: 11px;
	padding: 0 6px;
	border-radius: 999px;
	background: var(--card-bg);
	border: 1px solid var(--border-color);
	color: var(--text-muted);
}
.ab-edge-add {
	width: 18px;
	height: 18px;
	line-height: 14px;
	border-radius: 50%;
	border: 1px solid var(--gray-400);
	background: var(--card-bg);
	color: var(--text-muted);
	font-size: 14px;
	padding: 0;
	opacity: 0;
	transition: opacity 0.1s;
}
.vue-flow__edge:hover ~ * .ab-edge-add,
.ab-edge-label:hover .ab-edge-add,
.ab-canvas:hover .ab-edge-add {
	opacity: 0.85;
}
.ab-edge-add:hover {
	border-color: var(--blue-500);
	color: var(--blue-500);
	opacity: 1;
}
</style>
