import { createApp, watch } from "vue";
import App from "./App.vue";
import { createStore } from "./store";

const API = "pridict.automation.api";
const STATUS_COLORS = { Draft: "gray", Active: "green", Paused: "orange", Disabled: "red", Archived: "gray" };

class Builder {
	constructor({ wrapper, page }) {
		this.page = page;
		this.store = createStore();
		const mount = document.createElement("div");
		mount.className = "ab-root";
		$(wrapper).find(".layout-main-section").empty().append(mount);
		this.app = createApp(App, { store: this.store });
		this.app.config.globalProperties.__ = window.__;
		this.app.mount(mount);

		const state = this.store.state;
		watch(
			() =>
				state.data &&
				[
					state.data.automation.status,
					state.data.automation.draft_matches_active,
					state.data.automation.tested,
					state.data.automation.title,
				].join("|"),
			() => state.data && this.setupActions()
		);
		this.store.onTestRun = () => this.testRun();
	}

	load(name) {
		return this.store.load(name);
	}

	setupActions() {
		const { automation, spec } = this.store.state.data;
		const page = this.page;
		page.set_title(automation.title);
		page.set_indicator(__(automation.status), STATUS_COLORS[automation.status] || "gray");
		page.clear_actions();
		page.clear_menu();
		page.clear_custom_actions?.();
		if (automation.can_edit) {
			const changed = automation.status === "Active" && !automation.draft_matches_active;
			const needsActivation = automation.status !== "Active" || changed;
			// A draft must pass a test run before it can be activated (any edit needs a new test).
			if (needsActivation && automation.tested) {
				page.set_primary_action(changed ? __("Activate Changes") : __("Activate"), () => this.activate());
				page.add_menu_item(__("Test Run"), () => this.testRun());
			} else if (needsActivation) {
				page.set_primary_action(__("Test Run"), () => this.testRun(), "play");
			} else {
				page.add_menu_item(__("Test Run"), () => this.testRun());
			}
			if (automation.status === "Active") page.set_secondary_action(__("Pause"), () => this.call("pause"));
			if (automation.status === "Paused" && automation.active_version) {
				page.set_secondary_action(__("Resume"), () => this.call("resume"));
			}
			const runnable = ["trigger.manual", "trigger.document_event"].includes(spec.trigger?.type);
			if (automation.status === "Active" && runnable) page.add_menu_item(__("Run Now"), () => this.runNow());
			page.add_menu_item(__("Duplicate"), () => this.duplicate());
		}
		page.add_menu_item(__("Export JSON"), () => this.exportSpec());
		page.add_menu_item(__("Open Settings Form"), () => frappe.set_route("Form", "Automation", automation.name));
		page.add_menu_item(__("All Automations"), () => frappe.set_route("automations"));
	}

	async call(method, args = {}) {
		await frappe.call({ method: `${API}.${method}`, args: { name: this.store.state.name, ...args }, freeze: true });
		await this.store.load(this.store.state.name, null, true);
	}

	activate() {
		const { automation } = this.store.state.data;
		frappe.prompt(
			{ fieldname: "change_note", fieldtype: "Small Text", label: __("What changed? (shown in the version history)") },
			(values) => this.call("activate", values),
			automation.active_version ? __("Activate Changes") : __("Activate"),
			__("Activate")
		);
	}

	testRun() {
		const { spec, automation } = this.store.state.data;
		const trigger = spec.trigger || {};
		const doctype = trigger.config?.doctype;
		const start = (docname) =>
			frappe
				.call({
					method: `${API}.test_run`,
					args: { name: automation.name, doctype: docname ? doctype : null, docname: docname || null },
					freeze: true,
				})
				.then(({ message }) => {
					frappe.show_alert({ message: __("Test run {0} started. Nothing it does is kept.", [message.run]), indicator: "blue" });
					this.store.state.tab = "runs";
					this.store.load(automation.name, message.run);
				});
		if (trigger.type === "trigger.document_event" || (trigger.type === "trigger.manual" && doctype)) {
			frappe.prompt(
				{ fieldname: "docname", fieldtype: "Link", options: doctype, label: __(doctype), reqd: trigger.type === "trigger.document_event" ? 1 : 0 },
				(values) => start(values.docname),
				__("Test with which {0}?", [__(doctype)]),
				__("Start test")
			);
		} else {
			start(null);
		}
	}

	runNow() {
		const { spec, automation } = this.store.state.data;
		const doctype = spec.trigger?.config?.doctype;
		const start = (name) =>
			frappe
				.call({
					method: "pridict.automation.triggers.run_now",
					args: { automation: automation.name, doctype: name ? doctype : null, name: name || null },
				})
				.then(({ message }) => {
					frappe.show_alert({ message: __("Started run {0}", [message.run]), indicator: "green" });
					this.store.state.tab = "runs";
				});
		if (!doctype) return start(null);
		frappe.prompt(
			{ fieldname: "name", fieldtype: "Link", options: doctype, label: __(doctype), reqd: 1 },
			(values) => start(values.name),
			__("Run on which {0}?", [__(doctype)])
		);
	}

	async duplicate() {
		const { message } = await frappe.call({ method: `${API}.duplicate`, args: { name: this.store.state.name }, freeze: true });
		frappe.set_route("automation-builder", message.name);
	}

	async exportSpec() {
		const { message } = await frappe.call({ method: `${API}.export_spec`, args: { name: this.store.state.name } });
		const blob = new Blob([JSON.stringify(message, null, 1)], { type: "application/json" });
		const link = document.createElement("a");
		link.href = URL.createObjectURL(blob);
		link.download = `${frappe.scrub(message.title || this.store.state.name)}.automation.json`;
		link.click();
		URL.revokeObjectURL(link.href);
	}
}

frappe.provide("pridict.automation");
pridict.automation.Builder = Builder;
