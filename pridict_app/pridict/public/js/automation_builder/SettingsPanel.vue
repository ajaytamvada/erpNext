<template>
	<section class="ab-panel ab-settings">
		<template v-if="node">
			<div class="ab-settings-head">
				<span class="ab-muted">{{ meta.label || node.type }} · <code>{{ node.id }}</code></span>
				<button v-if="canEdit && !isTrigger" type="button" class="btn btn-xs btn-default ab-danger" @click="remove">
					{{ __("Delete step") }}
				</button>
			</div>
			<label class="ab-settings-label">{{ __("Name on the canvas") }}</label>
			<input
				v-model="label"
				class="form-control input-sm ab-label-input"
				:readonly="!canEdit"
				@change="saveLabel"
				@keydown.enter.prevent="$event.target.blur()"
			/>
			<template v-if="isTrigger">
				<label class="ab-settings-label">{{ __("Starts when") }}</label>
				<select class="form-control input-sm" :value="node.type" :disabled="!canEdit" @change="changeTrigger($event.target.value)">
					<option v-for="t in triggerTypes" :key="t.type" :value="t.type">{{ t.label }}</option>
				</select>
			</template>
			<p v-if="meta.description" class="ab-muted ab-settings-desc">{{ meta.description }}</p>
			<div v-for="issue in issues" :key="issue.message" class="ab-issue-line" :class="'ab-issue-' + issue.level">
				{{ issue.message }}
			</div>
			<div ref="form" class="ab-settings-form"></div>
			<div v-if="refMenu" class="ab-ref-menu" :style="{ top: refMenu.top + 'px' }">
				<input v-model="refQuery" class="form-control input-xs" :placeholder="__('Filter…')" />
				<div class="ab-ref-list">
					<template v-for="group in refGroups" :key="group.name">
						<div class="ab-picker-group">{{ group.name }}</div>
						<button v-for="r in group.items" :key="r.value" type="button" class="ab-ref-item" @click="insertRef(r.value)">
							{{ r.label }}
						</button>
					</template>
				</div>
				<button type="button" class="btn btn-xs btn-default" @click="refMenu = null">{{ __("Close") }}</button>
			</div>
			<template v-if="step">
				<h5>{{ __("Last run") }}</h5>
				<div>{{ step.summary }}</div>
				<pre v-if="step.output" class="ab-json">{{ JSON.stringify(step.output, null, 2) }}</pre>
			</template>
		</template>
		<template v-else>
			<h4>{{ __("Automation") }}</h4>
			<div ref="form" class="ab-settings-form"></div>
			<div v-for="issue in generalIssues" :key="issue.message" class="ab-issue-line" :class="'ab-issue-' + issue.level">
				{{ issue.message }}
			</div>
			<p class="ab-muted">{{ __("Select a step on the canvas to change it, or use + to add one.") }}</p>
		</template>
	</section>
</template>

<script setup>
import { computed, ref, watch, nextTick, onMounted, onBeforeUnmount } from "vue";

const LONG_TEXT = new Set(["message", "description", "comment", "condition", "value"]);
const LINKS = {
	doctype: "DocType",
	role: "Role",
	email_account: "Email Account",
	report: "Report",
	print_format: "Print Format",
};

const props = defineProps({ store: Object });
const store = props.store;
const form = ref(null);
const label = ref("");
const refMenu = ref(null);
const refQuery = ref("");
let group = null;
let quiet = 0; // > 0 while the panel itself fills in values
let fieldList = []; // our fields (FieldGroup adds its own section breaks to group.fields)
let built = null; // what the form was built for: `${id}|${type}`
const timers = {};

const data = computed(() => store.state.data);
const canEdit = computed(() => store.canEdit.value);
const node = computed(() => (store.state.selectedNode ? store.nodeById(store.state.selectedNode) : null));
const meta = computed(() => (node.value && data.value.catalog[node.value.type]) || {});
const isTrigger = computed(() => node.value && node.value === data.value.spec.trigger);
const issues = computed(() => data.value.validation.filter((i) => i.node_id === store.state.selectedNode));
const generalIssues = computed(() => data.value.validation.filter((i) => !i.node_id));
const step = computed(() => data.value.run?.steps?.[store.state.selectedNode] || null);
const triggerTypes = computed(() => Object.values(data.value.catalog).filter((t) => t.category === "trigger"));
const refGroups = computed(() => {
	if (!refMenu.value) return [];
	const q = refQuery.value.toLowerCase();
	const groups = {};
	for (const r of refMenu.value.items) {
		if (q && !r.label.toLowerCase().includes(q) && !r.value.toLowerCase().includes(q)) continue;
		(groups[r.group] ||= []).push(r);
	}
	return Object.entries(groups).map(([name, items]) => ({ name, items: items.slice(0, 60) }));
});

// --- schema -> Frappe fields ------------------------------------------------------

function kindOf(key, schema) {
	if (schema.enum) return "select";
	if (schema.type === "boolean") return "check";
	if (schema.type === "integer") return "int";
	if (schema.type === "array" && schema.items?.type === "string") return "lines";
	if (schema.type === "object" || schema.type === "array" || schema.oneOf) return "json";
	if (LINKS[schema.format]) return "link";
	return LONG_TEXT.has(key) ? "text" : "data";
}

function toField(key, schema, required) {
	const kind = kindOf(key, schema);
	const df = {
		fieldname: key,
		label: schema.title || key,
		description: schema.description,
		reqd: required ? 1 : 0,
		read_only: canEdit.value ? 0 : 1,
		onchange: () => queueChange(key, kind),
	};
	const types = {
		select: () => ({ fieldtype: "Select", options: ["", ...schema.enum].join("\n") }),
		check: () => ({ fieldtype: "Check" }),
		int: () => ({ fieldtype: "Int" }),
		lines: () => ({ fieldtype: "Small Text", description: __("One per line") }),
		json: () => ({ fieldtype: "Code", options: "JSON" }),
		link: () => ({ fieldtype: "Link", options: LINKS[schema.format] }),
		text: () => ({ fieldtype: "Small Text" }),
		data: () => ({ fieldtype: "Data" }),
	};
	return {
		...df,
		...types[kind](),
		_kind: kind,
		_expression: ["template", "condition"].includes(schema.format) || key === "value",
	};
}

function toFormValue(kind, value) {
	if (value === undefined || value === null) return kind === "check" ? 0 : "";
	if (kind === "json") return JSON.stringify(value, null, 2);
	if (kind === "lines") return (value || []).join("\n");
	if (kind === "check") return value ? 1 : 0;
	return typeof value === "string" ? value : JSON.stringify(value);
}

function fromFormValue(kind, raw) {
	if (kind === "check") return Boolean(raw);
	if (raw === "" || raw === null || raw === undefined) return null;
	if (kind === "int") return parseInt(raw, 10);
	if (kind === "lines") return String(raw).split("\n").map((s) => s.trim()).filter(Boolean);
	if (kind === "json") return JSON.parse(raw);
	return raw;
}

function generalFields() {
	const settings = data.value.spec.settings || {};
	const ro = canEdit.value ? 0 : 1;
	return [
		{ fieldname: "title", fieldtype: "Data", label: __("Title"), reqd: 1, read_only: ro, default: data.value.spec.title, onchange: () => queueGeneral("title") },
		{ fieldname: "description", fieldtype: "Small Text", label: __("Description"), read_only: ro, default: data.value.spec.description, onchange: () => queueGeneral("description") },
		{ fieldname: "on_error", fieldtype: "Select", label: __("When a step fails"), options: "stop_and_notify\ncontinue", read_only: ro, default: settings.on_error, onchange: () => queueGeneral("on_error") },
		{ fieldname: "max_steps", fieldtype: "Int", label: __("Max steps per run"), read_only: ro, default: settings.max_steps, onchange: () => queueGeneral("max_steps") },
	];
}

// --- building and syncing the form ------------------------------------------------

function build() {
	if (!form.value) return;
	form.value.innerHTML = "";
	refMenu.value = null;
	const key = node.value ? `${node.value.id}|${node.value.type}` : "general";
	built = key;
	let fields;
	if (node.value) {
		const schema = meta.value.config_schema || { properties: {} };
		const required = new Set(schema.required || []);
		fields = Object.entries(schema.properties || {}).map(([k, s]) => toField(k, s, required.has(k)));
		label.value = node.value.label || "";
	} else {
		fields = generalFields();
	}
	fieldList = fields;
	// FieldGroup adds section breaks to the array it is given, so give it a copy.
	group = new frappe.ui.FieldGroup({ fields: [...fields], body: form.value });
	group.make();
	if (node.value) {
		const config = node.value.config || {};
		setQuietly(fields.map((df) => [df.fieldname, toFormValue(df._kind, config[df.fieldname])]));
		if (canEdit.value) addRefButtons(fields);
	}
}

// Setting a control fires its onchange; those echoes must not be saved back.
async function setQuietly(pairs) {
	quiet += 1;
	try {
		await Promise.all(pairs.map(([fieldname, value]) => group.fields_dict[fieldname]?.set_value(value)));
		await new Promise((resolve) => setTimeout(resolve, 50));
	} finally {
		quiet -= 1;
	}
}

// The spec changed (this tab or another): refresh values, except in the field being edited.
function sync() {
	if (!group) return;
	const key = node.value ? `${node.value.id}|${node.value.type}` : "general";
	if (key !== built) return build();
	if (!node.value) {
		// Automation-level form: rebuild unless someone is typing in it.
		if (!form.value?.contains(document.activeElement) && !Object.keys(timers).length) build();
		return;
	}
	label.value = document.activeElement?.classList.contains("ab-label-input") ? label.value : node.value.label || "";
	const config = node.value.config || {};
	for (const df of fieldList) {
		const control = group.fields_dict[df.fieldname];
		if (control.$wrapper?.[0]?.contains(document.activeElement) || timers[df.fieldname]) continue;
		const wanted = toFormValue(df._kind, config[df.fieldname]);
		if (String(control.get_value() ?? "") !== String(wanted ?? "")) setQuietly([[df.fieldname, wanted]]);
	}
}

// Field edits are saved after a short pause. Each pending save remembers its own step and
// form, so selecting another step meanwhile cannot send the value to the wrong place.
const pending = {};

function schedule(key, fire) {
	clearTimeout(timers[key]);
	pending[key] = fire;
	timers[key] = setTimeout(() => {
		delete timers[key];
		delete pending[key];
		fire();
	}, 500);
}

function flushPending() {
	for (const key of Object.keys(pending)) {
		clearTimeout(timers[key]);
		delete timers[key];
		const fire = pending[key];
		delete pending[key];
		fire();
	}
}

function queueChange(key, kind) {
	if (quiet) return;
	const nodeId = node.value?.id;
	const fieldGroup = group;
	schedule(key, () => {
		if (!nodeId || !canEdit.value) return;
		let value;
		try {
			value = fromFormValue(kind, fieldGroup.get_value(key));
		} catch (error) {
			frappe.show_alert({ message: __("{0} is not valid JSON yet.", [key]), indicator: "orange" });
			return;
		}
		const target = store.nodeById(nodeId);
		if (!target) return;
		const current = (target.config || {})[key] ?? null;
		if (JSON.stringify(current) === JSON.stringify(value)) return;
		store.updateNode(nodeId, { config_patch: { [key]: value } });
	});
}

function queueGeneral(key) {
	if (quiet) return;
	const fieldGroup = group;
	schedule(key, () => {
		if (!canEdit.value) return;
		const value = fieldGroup.get_value(key);
		const spec = data.value.spec;
		if (key === "title" || key === "description") {
			if ((spec[key] || "") === (value || "") || (key === "title" && !value)) return;
			store.applyOps([{ op: "set_meta", [key]: value }]);
		} else {
			const parsed = key === "max_steps" ? parseInt(value, 10) : value;
			if ((spec.settings || {})[key] === parsed) return;
			store.applyOps([{ op: "set_settings", settings_patch: { [key]: parsed } }]);
		}
	});
}

function saveLabel() {
	if (node.value && canEdit.value && label.value !== (node.value.label || "")) {
		store.updateNode(node.value.id, { label: label.value });
	}
}

function changeTrigger(type) {
	if (type === node.value.type) return;
	frappe.confirm(__("Change the trigger? Its settings will be cleared."), () => store.setTrigger(type));
}

function remove() {
	const id = node.value.id;
	store.select(null);
	store.removeNode(id);
}

// --- expression picker -------------------------------------------------------------

function addRefButtons(fields) {
	for (const df of fields.filter((f) => f._expression)) {
		const control = group.fields_dict[df.fieldname];
		const button = document.createElement("button");
		button.type = "button";
		button.className = "btn btn-xs btn-default ab-ref-button";
		button.textContent = "{ }";
		button.title = __("Insert a value from the trigger or an earlier step");
		button.addEventListener("click", () => openRefs(df.fieldname, button));
		control.$wrapper.find(".control-label, .label-area").first().append(button);
	}
}

async function openRefs(fieldname, button) {
	const items = await store.getRefs(node.value.id);
	const panel = form.value.closest(".ab-settings");
	refQuery.value = "";
	refMenu.value = {
		fieldname,
		items,
		top: button.getBoundingClientRect().bottom - panel.getBoundingClientRect().top + panel.scrollTop + 4,
	};
}

function insertRef(value) {
	const { fieldname } = refMenu.value;
	refMenu.value = null;
	const control = group.fields_dict[fieldname];
	const isCondition = (meta.value.config_schema?.properties?.[fieldname]?.format || "") === "condition";
	const text = isCondition ? value : `{{ ${value} }}`;
	const input = control.$input?.[0];
	const current = control.get_value() || "";
	let next = current + text;
	if (input && typeof input.selectionStart === "number" && document.activeElement === input) {
		next = current.slice(0, input.selectionStart) + text + current.slice(input.selectionEnd);
	}
	control.set_value(next);
}

// A string key: an array getter would count as changed on every spec update.
watch(
	() => `${store.state.selectedNode}|${node.value?.type}`,
	() => {
		flushPending();
		nextTick(build);
	}
);
watch(() => data.value.spec, () => nextTick(sync), { deep: true });
watch(canEdit, () => nextTick(build));
onMounted(build);
onBeforeUnmount(flushPending);
</script>

<style>
.ab-settings {
	position: relative;
}
.ab-settings-head {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 8px;
}
.ab-settings-label {
	display: block;
	font-size: var(--text-sm);
	color: var(--text-muted);
	margin: 8px 0 4px;
}
.ab-settings-desc {
	margin: 8px 0;
}
.ab-settings-form {
	margin-top: 8px;
}
.ab-settings-form .frappe-control {
	margin-bottom: 8px;
}
/* Frappe caps short fields at half width (.input-max-width); the panel is narrow already. */
.ab-settings-form .frappe-control.input-max-width {
	max-width: none;
}
.ab-settings-form .form-section {
	padding: 0;
}
.ab-ref-button {
	margin-left: 6px;
	padding: 0 6px;
	font-family: var(--font-stack-monospace, monospace);
	font-size: 11px;
	line-height: 16px;
}
.ab-ref-menu {
	position: absolute;
	left: 12px;
	right: 12px;
	z-index: 10;
	display: flex;
	flex-direction: column;
	gap: 6px;
	padding: 8px;
	border-radius: var(--border-radius-lg);
	background: var(--card-bg);
	border: 1px solid var(--border-color);
	box-shadow: var(--shadow-lg);
}
.ab-ref-list {
	max-height: 260px;
	overflow-y: auto;
}
.ab-ref-item {
	display: block;
	width: 100%;
	text-align: left;
	border: 0;
	background: none;
	padding: 3px 6px;
	font-size: var(--text-sm);
	border-radius: var(--border-radius);
}
.ab-ref-item:hover {
	background: var(--subtle-fg);
}
.ab-danger {
	color: var(--red-600);
}
</style>
