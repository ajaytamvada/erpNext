import { createApp, reactive } from "vue";
import App from "./App.vue";

const RUN_EVENT = "agent_run_update";

class Builder {
	constructor({ wrapper, page }) {
		this.page = page;
		this.state = reactive({ name: null, data: null, selectedRun: null, selectedNode: null, error: null });
		const mount = document.createElement("div");
		mount.className = "ab-root";
		$(wrapper).find(".layout-main-section").empty().append(mount);
		this.app = createApp(App, {
			state: this.state,
			onSelectRun: (run) => this.load(this.state.name, run),
		});
		this.app.config.globalProperties.__ = window.__;
		this.app.mount(mount);

		// Runs report progress over realtime; refresh while this page is open.
		this.onRunUpdate = () => {
			if (frappe.get_route()[0] !== "automation-builder" || !this.state.name) return;
			clearTimeout(this.refreshTimer);
			this.refreshTimer = setTimeout(() => this.load(this.state.name, null, true), 400);
		};
		frappe.realtime.on(RUN_EVENT, this.onRunUpdate);
	}

	async load(name, run = null, follow = false) {
		if (name !== this.state.name) {
			this.state.selectedNode = null;
			this.state.selectedRun = null;
		}
		this.state.name = name;
		// A realtime refresh follows the newest run unless a past run was picked (pinned).
		if (!follow) this.state.pinnedRun = run;
		const wanted = follow ? this.state.pinnedRun : run;
		try {
			const { message } = await frappe.call({
				method: "pridict.automation.api.get_builder",
				args: { name, run: wanted },
			});
			this.state.data = message;
			this.state.selectedRun = message.run?.name || null;
			this.state.error = null;
			this.page.set_title(message.automation.title);
			this.page.set_indicator(__(message.automation.status), STATUS_COLORS[message.automation.status] || "gray");
			this.page.clear_actions();
			this.page.set_secondary_action(__("Open settings"), () => frappe.set_route("Form", "Automation", name));
		} catch (error) {
			this.state.error = __("Could not load automation {0}.", [name]);
		}
	}
}

const STATUS_COLORS = { Draft: "gray", Active: "green", Paused: "orange", Disabled: "red", Archived: "gray" };

frappe.provide("pridict.automation");
pridict.automation.Builder = Builder;
