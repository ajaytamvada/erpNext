<template>
	<div
		class="ab-node"
		:class="[`ab-cat-${category}`, status && `ab-node-${status}`, issue && `ab-has-${issue}`, { 'is-selected': selected }]"
	>
		<Handle v-if="!isTrigger" type="target" :position="Position.Top" :connectable="false" />
		<div class="ab-node-head">
			<span class="ab-node-icon">{{ icon }}</span>
			<span class="ab-node-type">{{ isTrigger ? __("Trigger") : typeLabel }}</span>
			<span v-if="issue" class="ab-node-issue" :title="issue === 'error' ? __('Has errors') : __('Has warnings')">!</span>
			<span v-if="status" class="ab-node-status" :title="statusLabel"></span>
		</div>
		<div class="ab-node-label">{{ label }}</div>
		<template v-if="branches.length">
			<Handle
				v-for="(branch, index) in branches"
				:id="`branch-${branch}`"
				:key="branch"
				type="source"
				:position="Position.Bottom"
				:connectable="false"
				:style="{ left: `${((index + 1) * 100) / (branches.length + 1)}%` }"
			/>
		</template>
		<Handle v-else type="source" :position="Position.Bottom" :connectable="false" />
	</div>
</template>

<script setup>
import { computed } from "vue";
import { Handle, Position } from "@vue-flow/core";

const props = defineProps({
	label: String,
	typeLabel: String,
	category: String,
	icon: String,
	branches: Array,
	isTrigger: Boolean,
	status: String,
	issue: String,
	selected: Boolean,
});

const STATUS_LABELS = {
	completed: __("Completed in this run"),
	failed: __("Failed in this run"),
	interrupted: __("Waiting"),
	"not-reached": __("Not reached in this run"),
};
const statusLabel = computed(() => STATUS_LABELS[props.status] || props.status);
</script>

<style>
.ab-node {
	width: 220px;
	padding: 8px 12px 10px;
	border-radius: var(--border-radius-lg);
	border: 1px solid var(--border-color);
	border-left: 4px solid var(--gray-400);
	background: var(--fg-color);
	box-shadow: var(--shadow-sm);
	cursor: pointer;
}
.ab-node.is-selected {
	box-shadow: 0 0 0 2px var(--blue-400);
}
.ab-cat-trigger {
	border-left-color: var(--orange-500);
}
.ab-cat-logic {
	border-left-color: var(--purple-500, var(--blue-600));
}
.ab-cat-action {
	border-left-color: var(--blue-500);
}
.ab-cat-data {
	border-left-color: var(--cyan-500, var(--teal-500));
}
.ab-cat-human {
	border-left-color: var(--pink-500, var(--red-400));
}
.ab-cat-ai {
	border-left-color: var(--green-600);
}
.ab-node-head {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: var(--text-xs);
	color: var(--text-muted);
	text-transform: uppercase;
	letter-spacing: 0.03em;
}
.ab-node-type {
	flex: 1;
}
.ab-node-label {
	margin-top: 2px;
	font-weight: 600;
	font-size: var(--text-md);
	color: var(--text-color);
	line-height: 1.3;
}
.ab-node-status {
	width: 10px;
	height: 10px;
	border-radius: 50%;
	background: var(--gray-300);
}
.ab-node-completed .ab-node-status {
	background: var(--green-500);
}
.ab-node-failed .ab-node-status {
	background: var(--red-500);
}
.ab-node-interrupted .ab-node-status {
	background: var(--orange-500);
}
.ab-node-not-reached {
	opacity: 0.55;
}
.ab-node-failed {
	border-color: var(--red-400);
}
.ab-node-issue {
	width: 16px;
	height: 16px;
	border-radius: 50%;
	text-align: center;
	line-height: 16px;
	font-weight: 700;
	color: #fff;
	background: var(--orange-500);
}
.ab-has-error .ab-node-issue {
	background: var(--red-500);
}
.ab-node .vue-flow__handle {
	width: 8px;
	height: 8px;
	background: var(--gray-400);
	border: 0;
}
</style>
