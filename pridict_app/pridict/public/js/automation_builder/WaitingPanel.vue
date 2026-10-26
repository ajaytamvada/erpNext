<template>
	<div class="ab-waiting">
		<div class="ab-waiting-title">
			{{ run.is_test ? __("Test is waiting at: {0}", [stepLabel]) : __("Waiting at: {0}", [stepLabel]) }}
		</div>
		<div class="ab-waiting-message">{{ pending.message || pending.question }}</div>

		<!-- Test runs: the admin plays the part of the approver, the person asked, or the clock. -->
		<template v-if="run.is_test && canEdit">
			<div class="ab-muted">{{ __("Simulate what happens next. The test replays from the start with your choice.") }}</div>
			<template v-if="pending.type === 'approval'">
				<input v-model="note" class="form-control input-sm" :placeholder="__('Note (optional)')" />
				<div class="ab-waiting-actions">
					<button class="btn btn-xs btn-primary" @click="store.simulate(run.name, pending.node, 'approved', note)">{{ __("Approve") }}</button>
					<button class="btn btn-xs btn-default" @click="store.simulate(run.name, pending.node, 'rejected', note)">{{ __("Reject") }}</button>
					<button class="btn btn-xs btn-default" @click="store.simulate(run.name, pending.node, 'expired')">{{ __("Let it expire") }}</button>
				</div>
			</template>
			<template v-else-if="pending.type === 'ask'">
				<div v-if="pending.choices?.length" class="ab-waiting-actions">
					<button v-for="choice in pending.choices" :key="choice" class="btn btn-xs btn-default" @click="store.simulate(run.name, pending.node, choice)">
						{{ choice }}
					</button>
				</div>
				<form v-else class="ab-waiting-actions" @submit.prevent="text && store.simulate(run.name, pending.node, text)">
					<input v-model="text" class="form-control input-sm" :placeholder="__('Answer as the person asked')" />
					<button class="btn btn-xs btn-primary" :disabled="!text">{{ __("Answer") }}</button>
				</form>
			</template>
			<div v-else class="ab-waiting-actions">
				<button class="btn btn-xs btn-primary" @click="store.simulate(run.name, pending.node, 'skip')">{{ __("Skip the wait") }}</button>
			</div>
		</template>

		<!-- Live runs: real people decide. -->
		<template v-else-if="!run.is_test">
			<div v-if="pending.type === 'approval' && run.approval">
				<a :href="`/app/agent-approval/${run.approval}`">{{ __("Open the approval {0}", [run.approval]) }}</a>
				<span class="ab-muted"> · {{ __("Approvers: {0}", [(pending.roles || []).join(", ")]) }}</span>
			</div>
			<template v-else-if="pending.type === 'ask'">
				<div class="ab-muted">{{ __("Asked: {0}", [(pending.users || []).join(", ")]) }}</div>
				<div v-if="pending.choices?.length" class="ab-waiting-actions">
					<button v-for="choice in pending.choices" :key="choice" class="btn btn-xs btn-default" @click="store.answer(run.name, choice)">
						{{ choice }}
					</button>
				</div>
				<form v-else class="ab-waiting-actions" @submit.prevent="text && store.answer(run.name, text)">
					<input v-model="text" class="form-control input-sm" :placeholder="__('Your answer')" />
					<button class="btn btn-xs btn-primary" :disabled="!text">{{ __("Answer") }}</button>
				</form>
			</template>
			<div v-else-if="pending.type === 'wait'" class="ab-muted">{{ __("Resumes by itself at {0}.", [pending.resume_at]) }}</div>
		</template>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({ store: Object, run: Object });
const note = ref("");
const text = ref("");
const pending = computed(() => props.run.pending || {});
const canEdit = computed(() => props.store.canEdit.value);
const stepLabel = computed(() => {
	const node = props.store.nodeById(pending.value.node);
	return node ? node.label || node.id : pending.value.node;
});
</script>

<style>
.ab-waiting {
	margin-top: 10px;
	padding: 10px;
	border-radius: var(--border-radius);
	background: var(--bg-orange);
	color: var(--text-on-orange);
	display: flex;
	flex-direction: column;
	gap: 6px;
}
.ab-waiting-title {
	font-weight: 600;
}
.ab-waiting-message {
	white-space: pre-wrap;
	font-size: var(--text-sm);
}
.ab-waiting-actions {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
}
.ab-waiting .form-control {
	background: var(--card-bg);
}
</style>
