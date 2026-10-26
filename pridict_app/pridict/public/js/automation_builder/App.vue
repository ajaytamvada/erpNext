<template>
	<div class="ab-app">
		<div v-if="state.error" class="ab-empty">{{ state.error }}</div>
		<div v-else-if="!data" class="ab-empty">{{ __("Loading…") }}</div>
		<template v-else>
			<div class="ab-summary">
				<span class="ab-pill">{{ triggerSummary }}</span>
				<span class="ab-muted">{{ versionLabel }}</span>
				<span class="ab-muted">{{ __("Runs as {0}", [data.automation.run_as]) }}</span>
				<button v-if="errors.length" type="button" class="ab-issue ab-issue-error ab-link" @click="showProblems">
					{{ errors.length === 1 ? __("1 problem") : __("{0} problems", [errors.length]) }}
				</button>
				<button v-else-if="warnings.length" type="button" class="ab-issue ab-issue-warning ab-link" @click="showProblems">
					{{ warnings.length === 1 ? __("1 warning") : __("{0} warnings", [warnings.length]) }}
				</button>
				<span v-else class="ab-issue ab-issue-ok">{{ __("No problems found") }}</span>
				<span v-if="!store.canEdit.value" class="ab-muted ab-readonly">{{ __("Read only") }}</span>
			</div>
			<div v-if="!data.site.enabled" class="ab-banner">
				{{ __("Automations are switched off on this site, so nothing runs. An administrator can turn them on in Automation Settings.") }}
			</div>
			<div v-if="data.automation.status === 'Paused' && data.automation.paused_reason" class="ab-banner">
				{{ data.automation.paused_reason }}
			</div>
			<div v-if="data.automation.status === 'Active' && !data.automation.draft_matches_active" class="ab-banner ab-banner-info">
				{{ __("You are editing a draft. Version {0} keeps running until you activate your changes.", [activeVersionNumber]) }}
			</div>

			<div class="ab-body">
				<div class="ab-canvas">
					<Canvas :store="store" />
					<NodePicker v-if="state.picker" :store="store" />
				</div>

				<aside class="ab-side">
					<div class="ab-tabs">
						<button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: state.tab === tab.key }" @click="openTab(tab.key)">
							{{ tab.label }}
						</button>
					</div>

					<SettingsPanel v-if="state.tab === 'step'" :store="store" />

					<template v-else-if="state.tab === 'runs'">
						<section class="ab-panel ab-runs">
							<div v-if="!data.runs.length" class="ab-muted">
								{{ __("No runs yet. Activate the automation and trigger it to see a run here.") }}
							</div>
							<button
								v-for="run in data.runs"
								:key="run.name"
								type="button"
								class="ab-run"
								:class="{ 'is-selected': run.name === state.selectedRun }"
								@click="store.load(state.name, run.name)"
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
							<div v-if="data.run.outcome && data.run.status !== 'Failed'" class="ab-muted">{{ data.run.outcome }}</div>
							<div v-if="data.run.error" class="ab-error">{{ data.run.error }}</div>
							<p class="ab-muted">{{ __("Click a step on the canvas to see what it did.") }}</p>
						</section>
					</template>

					<section v-else-if="state.tab === 'history'" class="ab-panel ab-history">
						<div v-if="!state.history" class="ab-muted">{{ __("Loading…") }}</div>
						<div v-else-if="!state.history.length" class="ab-muted">{{ __("No changes yet.") }}</div>
						<div v-for="change in state.history || []" :key="change.name" class="ab-change">
							<div>
								<span class="ab-change-rev">{{ __("Revision {0}", [change.revision]) }}</span>
								<span class="ab-badge">{{ sourceLabel(change.source) }}</span>
							</div>
							<div>{{ change.summary }}</div>
							<div class="ab-muted">
								{{ change.owner }} · {{ when(change.creation) }}
								<button
									v-if="store.canEdit.value && change.revision !== data.automation.draft_revision"
									type="button"
									class="btn btn-xs btn-link"
									@click="restore(change)"
								>
									{{ __("Restore") }}
								</button>
							</div>
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
import NodePicker from "./NodePicker.vue";
import SettingsPanel from "./SettingsPanel.vue";

const props = defineProps({ store: Object });
const store = props.store;
const state = store.state;
const data = computed(() => state.data);
const errors = computed(() => data.value.validation.filter((i) => i.level === "error"));
const warnings = computed(() => data.value.validation.filter((i) => i.level === "warning"));
const tabs = [
	{ key: "step", label: __("Step") },
	{ key: "runs", label: __("Runs") },
	{ key: "history", label: __("History") },
];

const activeVersionNumber = computed(() => (data.value.automation.active_version || "").split("-v").pop());
const versionLabel = computed(() => {
	const rev = __("draft revision {0}", [data.value.automation.draft_revision || 0]);
	return data.value.automation.active_version ? `${__("Version {0}", [activeVersionNumber.value])} · ${rev}` : rev;
});

const triggerSummary = computed(() => {
	const trigger = data.value.spec.trigger || {};
	const config = trigger.config || {};
	const label = data.value.catalog[trigger.type]?.label || __("No trigger");
	if (trigger.type === "trigger.document_event" && config.doctype) return `${config.doctype} · ${config.event || "?"}`;
	if (trigger.type === "trigger.schedule") return `${label} · ${config.frequency || config.cron || "?"} ${config.time || ""}`.trim();
	return label;
});

function openTab(key) {
	state.tab = key;
	if (key === "history") store.loadHistory();
}

function showProblems() {
	const first = data.value.validation.find((i) => i.node_id);
	state.tab = "step";
	store.select(first ? first.node_id : null);
}

function restore(change) {
	frappe.confirm(__("Make revision {0} the draft again? This is recorded as a new revision.", [change.revision]), () =>
		store.restore(change.name)
	);
}

const SOURCES = { ai: __("AI"), canvas: __("Canvas"), api: __("Form"), restore: __("Restore") };
const sourceLabel = (source) => SOURCES[source] || source;
const statusKey = (status) => (status || "").toLowerCase().replace(/\s+/g, "-");
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
.ab-link {
	border: 0;
	background: none;
	padding: 0;
	text-decoration: underline dotted;
}
.ab-banner {
	padding: 8px 12px;
	margin-bottom: 8px;
	border-radius: var(--border-radius);
	background: var(--bg-orange);
	color: var(--text-on-orange);
	font-size: var(--text-sm);
}
.ab-banner-info {
	background: var(--bg-blue);
	color: var(--text-on-blue);
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
	grid-template-columns: minmax(0, 1fr) 360px;
	gap: 16px;
}
.ab-canvas {
	position: relative;
	height: calc(100vh - 220px);
	min-height: 520px;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-lg);
	background: var(--card-bg);
	overflow: hidden;
}
.ab-side {
	display: flex;
	flex-direction: column;
	gap: 12px;
	max-height: calc(100vh - 220px);
	overflow-y: auto;
}
.ab-tabs {
	display: flex;
	gap: 4px;
	border-bottom: 1px solid var(--border-color);
	flex: none;
}
.ab-tabs button {
	border: 0;
	background: none;
	padding: 6px 10px;
	color: var(--text-muted);
	border-bottom: 2px solid transparent;
}
.ab-tabs button.active {
	color: var(--text-color);
	border-bottom-color: var(--primary);
	font-weight: 500;
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
	max-height: 300px;
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
.ab-change {
	padding: 8px 0;
	border-bottom: 1px solid var(--border-color);
}
.ab-change:last-child {
	border-bottom: 0;
}
.ab-change-rev {
	font-weight: 500;
	margin-right: 6px;
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
