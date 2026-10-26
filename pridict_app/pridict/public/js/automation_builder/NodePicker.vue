<template>
	<div class="ab-picker-backdrop" @click.self="close" @keydown.esc="close">
		<div class="ab-picker" role="dialog" :aria-label="__('Add a step')">
			<div class="ab-picker-head">
				<strong>{{ title }}</strong>
				<button type="button" class="btn btn-xs btn-default" @click="close">{{ __("Cancel") }}</button>
			</div>
			<input
				ref="search"
				v-model="query"
				type="search"
				class="form-control input-sm"
				:placeholder="__('Search steps…')"
				@keydown.enter.prevent="pickFirst"
			/>
			<div class="ab-picker-list">
				<template v-for="group in groups" :key="group.category">
					<div class="ab-picker-group">{{ group.label }}</div>
					<button
						v-for="item in group.items"
						:key="item.type"
						type="button"
						class="ab-picker-item"
						@click="pick(item.type)"
					>
						<span class="ab-picker-icon">{{ item.icon }}</span>
						<span>
							<span class="ab-picker-label">{{ item.label }}</span>
							<span class="ab-picker-desc">{{ item.description }}</span>
						</span>
					</button>
				</template>
				<div v-if="!groups.length" class="ab-muted">{{ __("No step matches {0}.", [query]) }}</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, onMounted } from "vue";

const CATEGORY_LABELS = {
	data: __("Find data"),
	logic: __("Logic"),
	action: __("Actions"),
	human: __("People"),
	ai: __("AI"),
};

const props = defineProps({ store: Object });
const store = props.store;
const query = ref("");
const search = ref(null);

const picker = computed(() => store.state.picker);
const title = computed(() => {
	const after = picker.value.after && store.nodeById(picker.value.after);
	if (!after) return __("Add a step");
	const name = after.label || after.id;
	return picker.value.branch ? __("Add after {0} ({1})", [name, picker.value.branch]) : __("Add after {0}", [name]);
});

const groups = computed(() => {
	const q = query.value.trim().toLowerCase();
	const items = Object.values(store.state.data.catalog).filter(
		(item) =>
			item.category !== "trigger" &&
			(!q || item.label.toLowerCase().includes(q) || (item.description || "").toLowerCase().includes(q))
	);
	return Object.keys(CATEGORY_LABELS)
		.map((category) => ({
			category,
			label: CATEGORY_LABELS[category],
			items: items.filter((item) => item.category === category),
		}))
		.filter((group) => group.items.length);
});

function close() {
	store.state.picker = null;
}

function pick(type) {
	const { after, branch } = picker.value;
	close();
	store.addNode(type, after, branch);
}

function pickFirst() {
	const first = groups.value[0]?.items[0];
	if (first) pick(first.type);
}

onMounted(() => search.value?.focus());
</script>

<style>
.ab-picker-backdrop {
	position: absolute;
	inset: 0;
	z-index: 20;
	background: rgba(0, 0, 0, 0.08);
	display: flex;
	justify-content: center;
	align-items: flex-start;
	padding-top: 48px;
}
.ab-picker {
	width: 380px;
	max-height: calc(100% - 80px);
	display: flex;
	flex-direction: column;
	gap: 8px;
	padding: 12px;
	border-radius: var(--border-radius-lg);
	background: var(--card-bg);
	border: 1px solid var(--border-color);
	box-shadow: var(--shadow-lg);
}
.ab-picker-head {
	display: flex;
	justify-content: space-between;
	align-items: center;
}
.ab-picker-list {
	overflow-y: auto;
}
.ab-picker-group {
	font-size: var(--text-xs);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	color: var(--text-muted);
	margin: 8px 0 4px;
}
.ab-picker-item {
	display: flex;
	gap: 10px;
	width: 100%;
	text-align: left;
	border: 0;
	background: none;
	padding: 6px;
	border-radius: var(--border-radius);
}
.ab-picker-item:hover {
	background: var(--subtle-fg);
}
.ab-picker-icon {
	width: 20px;
	text-align: center;
}
.ab-picker-label {
	display: block;
	font-weight: 500;
}
.ab-picker-desc {
	display: block;
	font-size: var(--text-xs);
	color: var(--text-muted);
}
</style>
