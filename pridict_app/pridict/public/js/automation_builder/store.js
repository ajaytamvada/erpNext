// Builder state and the only way the canvas changes a spec: operations sent to apply_ops.
// Operations are queued so each one is applied on top of the revision the last one produced.
import { reactive, computed } from "vue";
import { layout } from "./layout";

const API = "pridict.automation.api";
const UPDATE_EVENT = "automation_update";
const RUN_EVENT = "agent_run_update";

export function createStore() {
	const state = reactive({
		name: null,
		data: null,
		error: null,
		selectedNode: null,
		selectedRun: null,
		pinnedRun: null,
		tab: "step",
		picker: null, // {after, branch} while the node picker is open
		saving: 0,
		history: null,
		refs: {}, // node id -> expression references, cached per revision
	});
	let queue = Promise.resolve();
	let subscribed = null;

	const canEdit = computed(() => Boolean(state.data?.automation.can_edit));
	const revision = () => state.data?.automation.draft_revision || 0;

	async function load(name, run = null, follow = false) {
		if (name !== state.name) {
			state.selectedNode = null;
			state.selectedRun = null;
			state.history = null;
			subscribe(name);
		}
		state.name = name;
		// A refresh follows the newest run unless a past run was picked (pinned).
		if (!follow) state.pinnedRun = run;
		const wanted = follow ? state.pinnedRun : run;
		try {
			const { message } = await frappe.call({ method: `${API}.get_builder`, args: { name, run: wanted } });
			state.data = message;
			state.selectedRun = message.run?.name || null;
			state.error = null;
			state.refs = {};
			if (state.selectedNode && !nodeById(state.selectedNode)) state.selectedNode = null;
			if (state.tab === "history") loadHistory();
		} catch (error) {
			state.error = __("Could not load automation {0}.", [name]);
		}
	}

	function subscribe(name) {
		if (subscribed) frappe.realtime.doc_unsubscribe("Automation", subscribed);
		subscribed = name;
		frappe.realtime.doc_subscribe("Automation", name);
	}

	// Another tab (or the AI architect) changed the draft, or a run made progress.
	function onRealtime(event, data) {
		if (frappe.get_route()[0] !== "automation-builder" || !state.name) return;
		if (event === UPDATE_EVENT) {
			if (data.automation !== state.name || (data.revision === revision() && data.status === state.data?.automation.status)) return;
		}
		clearTimeout(onRealtime.timer);
		onRealtime.timer = setTimeout(() => load(state.name, null, true), 300);
	}
	frappe.realtime.on(UPDATE_EVENT, (data) => onRealtime(UPDATE_EVENT, data));
	frappe.realtime.on(RUN_EVENT, (data) => onRealtime(RUN_EVENT, data));

	function nodeById(id) {
		const spec = state.data?.spec;
		if (!spec) return null;
		if (spec.trigger && (spec.trigger.id || "trigger") === id) return spec.trigger;
		return spec.nodes.find((n) => n.id === id) || null;
	}

	function applyOps(ops, summary = null) {
		const run = async () => {
			state.saving += 1;
			try {
				const { message } = await frappe.call({
					method: `${API}.apply_ops`,
					args: { name: state.name, base_revision: revision(), ops, source: "canvas", summary },
				});
				if (message.ok) {
					state.data.spec = message.spec;
					state.data.validation = message.validation;
					state.data.automation.draft_revision = message.revision;
					state.data.automation.draft_matches_active = false;
					state.refs = {};
					if (state.tab === "history") loadHistory();
					return message;
				}
				if (message.conflict) {
					frappe.show_alert({ message: __("Someone else changed this automation. Showing the latest version."), indicator: "orange" });
				} else {
					frappe.show_alert({ message: message.error, indicator: "red" }, 7);
				}
				await load(state.name, state.selectedRun, true);
				return message;
			} finally {
				state.saving -= 1;
			}
		};
		queue = queue.then(run, run);
		return queue;
	}

	async function addNode(type, after, branch) {
		const before = new Set(state.data.spec.nodes.map((n) => n.id));
		const op = { op: "add_node", type };
		if (after) {
			op.after = after;
			if (branch) op.branch = branch;
		}
		const result = await applyOps([op]);
		const added = result?.ok && state.data.spec.nodes.find((n) => !before.has(n.id));
		if (added) select(added.id);
	}

	function select(id) {
		state.selectedNode = id;
		if (id) state.tab = "step";
	}

	async function getRefs(nodeId) {
		if (!state.refs[nodeId]) {
			const { message } = await frappe.call({ method: `${API}.get_references`, args: { name: state.name, node_id: nodeId } });
			state.refs[nodeId] = message;
		}
		return state.refs[nodeId];
	}

	async function loadHistory() {
		const { message } = await frappe.call({ method: `${API}.get_history`, args: { name: state.name } });
		state.history = message;
	}

	async function restore(change) {
		await frappe.call({ method: `${API}.restore`, args: { name: state.name, change }, freeze: true });
		await load(state.name, state.selectedRun, true);
	}

	function autoLayout() {
		const positions = layout(state.data.spec);
		const ops = Object.entries(positions)
			.filter(([id, position]) => {
				const current = nodeById(id)?.position || [0, 0];
				return current[0] !== position[0] || current[1] !== position[1];
			})
			.map(([id, position]) => ({ op: "move_node", id, position }));
		if (ops.length) return applyOps(ops, __("Tidied the layout"));
	}

	return {
		state,
		canEdit,
		load,
		nodeById,
		applyOps,
		addNode,
		select,
		getRefs,
		loadHistory,
		restore,
		autoLayout,
		removeNode: (id) => applyOps([{ op: "remove_node", id, reconnect: true }]),
		moveNode: (id, position) => applyOps([{ op: "move_node", id, position }]),
		connect: (from, to, branch) => applyOps([{ op: "connect", from, to, ...(branch ? { branch } : {}) }]),
		disconnect: (edge) => applyOps([{ op: "disconnect", from: edge.from, to: edge.to, ...(edge.branch ? { branch: edge.branch } : {}) }]),
		updateNode: (id, changes) => applyOps([{ op: "update_node", id, ...changes }]),
		setTrigger: (type, config = {}) => applyOps([{ op: "set_trigger", type, config }]),
	};
}
