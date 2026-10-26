<template>
	<div class="ab-app">
		<div v-if="state.error" class="ab-empty">{{ state.error }}</div>
		<div v-else-if="!data" class="ab-empty">{{ __("Loading…") }}</div>
		<template v-else>
			<div class="ab-summary">
				<span class="ab-pill">{{ triggerSummary }}</span>
				<span class="ab-muted">{{ __("Revision {0}", [data.automation.draft_revision || 0]) }}</span>
				<span class="ab-muted">{{ __("Runs as {0}", [data.automation.run_as]) }}</span>
				<span v-if="errors.length" class="ab-issue ab-issue-error">{{ __("{0} errors", [errors.length]) }}</span>
				<span v-else-if="warnings.length" class="ab-issue ab-issue-warning">{{ __("{0} warnings", [warnings.length]) }}</span>
				<span v-else class="ab-issue ab-issue-ok">{{ __("No problems found") }}</span>
				<span class="ab-muted ab-readonly">{{ __("Read-only preview") }}</span>
			</div>
			<p v-if="data.automation.description" class="ab-description">{{ data.automation.description }}</p>

			<div class="ab-body">
				<div class="ab-canvas">
					<Canvas
						:spec="data.spec"
						:catalog="data.catalog"
						:validation="data.validation"
						:run="data.run"
						:selected="state.selectedNode"
						@select="(id) => (state.selectedNode = id)"
					/>
				</div>

				<aside class="ab-side">
					<section class="ab-panel ab-runs">
						<h4>{{ __("Runs") }}</h4>
						<div v-if="!data.runs.length" class="ab-muted">
							{{ __("No runs yet. Activate the automation and trigger it to see a run here.") }}
						</div>
						<button
							v-for="run in data.runs"
							:key="run.name"
							type="button"
							class="ab-run"
							:class="{ 'is-selected': run.name === state.selectedRun }"
							@click="onSelectRun(run.name)"
						>
							<span class="ab-dot" :class="'ab-status-' + statusKey(run.status)"></span>
							<span class="ab-run-main">
								<span class="ab-run-name">{{ run.name }}<span v-if="run.is_test"> · {{ __("test") }}</span></span>
								<span class="ab-muted">{{ run.trigger_doctype }} {{ run.trigger_name }}</span>
							</span>
							<span class="ab-muted ab-run-when">{{ when(run.started_at) }}</span>
						</button>
					</section>

					<section v-if="data.run" class="ab-panel">
						<h4>
							<a :href="`/app/agent-run/${data.run.name}`">{{ data.run.name }}</a>
							<span class="ab-badge" :class="'ab-status-' + statusKey(data.run.status)">{{ __(data.run.status) }}</span>
						</h4>
						<div class="ab-muted">
							<a v-if="data.run.trigger.name" :href="docUrl(data.run.trigger.doctype, data.run.trigger.name)">
								{{ data.run.trigger.doctype }} {{ data.run.trigger.name }}
							</a>
							· {{ data.run.trigger.event }}
							<span v-if="data.run.duration_s"> · {{ data.run.duration_s.toFixed(1) }}s</span>
						</div>
						<div v-if="data.run.error" class="ab-error">{{ data.run.error }}</div>
					</section>

					<section v-if="node" class="ab-panel">
						<h4>{{ node.label || node.id }}</h4>
						<div class="ab-muted">{{ (data.catalog[node.type] || {}).label || node.type }} · <code>{{ node.id }}</code></div>
						<div v-for="issue in nodeIssues" :key="issue.message" class="ab-issue-line" :class="'ab-issue-' + issue.level">
							{{ issue.message }}
						</div>
						<template v-if="step">
							<h5>{{ __("Last run") }}</h5>
							<div>{{ step.summary }}</div>
							<pre v-if="step.output" class="ab-json">{{ pretty(step.output) }}</pre>
						</template>
						<h5>{{ __("Settings") }}</h5>
						<pre class="ab-json">{{ pretty(node.config) }}</pre>
					</section>
					<section v-else-if="generalIssues.length" class="ab-panel">
						<h4>{{ __("Problems") }}</h4>
						<div v-for="issue in generalIssues" :key="issue.message" class="ab-issue-line" :class="'ab-issue-' + issue.level">
							{{ issue.message }}
						</div>
					</section>
				</aside>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed } from "vue";
import Canvas from "./Canvas.vue";

const props = defineProps({ state: Object, onSelectRun: Function });
const data = computed(() => props.state.data);
const errors = computed(() => data.value.validation.filter((i) => i.level === "error"));
const warnings = computed(() => data.value.validation.filter((i) => i.level === "warning"));
const generalIssues = computed(() => data.value.validation.filter((i) => !i.node_id));

const node = computed(() => {
	const id = props.state.selectedNode;
	if (!id || !data.value) return null;
	const spec = data.value.spec;
	if (spec.trigger && (spec.trigger.id || "trigger") === id) return spec.trigger;
	return spec.nodes.find((n) => n.id === id) || null;
});
const nodeIssues = computed(() => data.value.validation.filter((i) => i.node_id === props.state.selectedNode));
const step = computed(() => data.value.run?.steps?.[props.state.selectedNode] || null);

const triggerSummary = computed(() => {
	const config = data.value.spec.trigger?.config || {};
	const label = data.value.catalog[data.value.spec.trigger?.type]?.label || __("No trigger");
	return config.doctype ? `${config.doctype} · ${config.event}` : label;
});

const statusKey = (status) => (status || "").toLowerCase().replace(/\s+/g, "-");
const pretty = (value) => JSON.stringify(value, null, 2);
const when = (value) => (value ? frappe.datetime.prettyDate(value, true) : "");
const docUrl = (doctype, name) => `/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}`;
</script>

<style>
.ab-app {
	padding: var(--padding-md) 0;
}
.ab-empty {
	padding: 48px;
	text-align: center;
	color: var(--text-muted);
}
.ab-summary {
	display: flex;
	flex-wrap: wrap;
	gap: 12px;
	align-items: center;
	margin-bottom: 8px;
}
.ab-pill {
	padding: 2px 10px;
	border-radius: 999px;
	background: var(--bg-blue);
	color: var(--text-on-blue);
	font-weight: 500;
}
.ab-muted {
	color: var(--text-muted);
	font-size: var(--text-sm);
}
.ab-readonly {
	margin-left: auto;
}
.ab-description {
	color: var(--text-muted);
	margin-bottom: 12px;
}
.ab-issue {
	font-size: var(--text-sm);
	font-weight: 500;
}
.ab-issue-error {
	color: var(--red-600);
}
.ab-issue-warning {
	color: var(--orange-600);
}
.ab-issue-ok {
	color: var(--green-600);
}
.ab-issue-line {
	font-size: var(--text-sm);
	margin-top: 4px;
}
.ab-body {
	display: grid;
	grid-template-columns: minmax(0, 1fr) 340px;
	gap: 16px;
}
.ab-canvas {
	height: calc(100vh - 230px);
	min-height: 480px;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-lg);
	background: var(--card-bg);
	overflow: hidden;
}
.ab-side {
	display: flex;
	flex-direction: column;
	gap: 12px;
	max-height: calc(100vh - 230px);
	overflow-y: auto;
}
.ab-panel {
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-lg);
	background: var(--card-bg);
	padding: 12px;
}
.ab-panel h4 {
	font-size: var(--text-base);
	font-weight: 600;
	margin: 0 0 8px;
	display: flex;
	gap: 8px;
	align-items: center;
}
.ab-panel h5 {
	font-size: var(--text-sm);
	font-weight: 600;
	margin: 12px 0 4px;
}
.ab-run {
	display: flex;
	width: 100%;
	gap: 8px;
	align-items: center;
	text-align: left;
	border: 0;
	background: none;
	padding: 6px;
	border-radius: var(--border-radius);
}
.ab-run:hover,
.ab-run.is-selected {
	background: var(--subtle-fg);
}
.ab-run-main {
	display: flex;
	flex-direction: column;
	flex: 1;
	min-width: 0;
}
.ab-run-name {
	font-weight: 500;
}
.ab-run-main > span {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.ab-run-when {
	flex: none;
	white-space: nowrap;
}
.ab-runs {
	max-height: 260px;
	overflow-y: auto;
	flex: none;
}
.ab-dot {
	width: 8px;
	height: 8px;
	border-radius: 50%;
	background: var(--gray-400);
	flex: none;
}
.ab-badge {
	font-size: var(--text-xs);
	padding: 1px 8px;
	border-radius: 999px;
	background: var(--gray-100);
	color: var(--gray-700);
}
.ab-dot.ab-status-completed {
	background: var(--green-500);
}
.ab-dot.ab-status-failed {
	background: var(--red-500);
}
.ab-dot.ab-status-running,
.ab-dot.ab-status-queued {
	background: var(--blue-500);
}
.ab-badge.ab-status-completed {
	background: var(--bg-green);
	color: var(--text-on-green);
}
.ab-badge.ab-status-failed {
	background: var(--bg-red);
	color: var(--text-on-red);
}
.ab-badge.ab-status-running,
.ab-badge.ab-status-queued {
	background: var(--bg-blue);
	color: var(--text-on-blue);
}
.ab-error {
	color: var(--red-600);
	margin-top: 8px;
	white-space: pre-wrap;
}
.ab-json {
	font-size: var(--text-xs);
	background: var(--subtle-fg);
	padding: 8px;
	border-radius: var(--border-radius);
	max-height: 260px;
	overflow: auto;
	white-space: pre-wrap;
	word-break: break-word;
}
@media (max-width: 991px) {
	.ab-body {
		grid-template-columns: 1fr;
	}
	.ab-side {
		max-height: none;
	}
}
</style>
