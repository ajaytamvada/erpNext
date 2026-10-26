const AUTOMATIONS_API = "pridict.automation.api";
const AUTOMATION_STATUS_COLORS = { Draft: "gray", Active: "green", Paused: "orange", Disabled: "red", Archived: "gray" };
const DOCUMENT_EVENTS = [
	["after_insert", __("is created")],
	["on_update", __("is saved")],
	["on_submit", __("is submitted")],
	["on_cancel", __("is cancelled")],
	["on_trash", __("is deleted")],
];

frappe.pages["automations"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Automations"), single_column: true });
	wrapper.automations = new AutomationsPage(page);
};

frappe.pages["automations"].on_page_show = (wrapper) => wrapper.automations.refresh();

class AutomationsPage {
	constructor(page) {
		this.page = page;
		this.$body = $('<div class="automations-page"></div>').appendTo(page.main);
		if (frappe.model.can_create("Automation")) {
			page.set_primary_action(__("New Automation"), () => this.create(), "add");
			page.set_secondary_action(__("Import"), () => this.importFile());
		}
		page.add_menu_item(__("Automation Settings"), () => frappe.set_route("Form", "Automation Settings"));
	}

	async refresh() {
		const [list, health] = await Promise.all([
			frappe.call({ method: `${AUTOMATIONS_API}.list_automations` }),
			frappe.call({ method: "pridict.automation.maintenance.health" }),
		]);
		this.render(list.message || []);
		this.renderHealth(health.message);
	}

	renderHealth(h) {
		if (!h) return;
		const tile = (label, value, tone = "") =>
			`<div class="automations-tile ${tone}"><div class="automations-tile-value">${value}</div><div class="automations-tile-label">${label}</div></div>`;
		const strip = $(`<div class="automations-health">
			${h.enabled ? "" : `<div class="automations-off">${__("Automations are switched off on this site. Turn them on in Automation Settings.")}</div>`}
			${tile(__("Active"), h.active)}
			${tile(__("Runs (24 h)"), h.runs_24h)}
			${tile(__("Failure rate"), `${h.failure_rate}%`, h.failure_rate > 10 ? "bad" : "")}
			${tile(__("Waiting for people"), h.waiting)}
			${tile(__("Paused"), h.paused, h.paused ? "warn" : "")}
			${tile(__("Emails today"), h.emails_today)}
			${h.queued === null || h.queued === undefined ? "" : tile(__("In queue"), h.queued, h.queued > 50 ? "warn" : "")}
		</div>`);
		this.$body.prepend(strip);
	}

	render(rows) {
		const esc = frappe.utils.escape_html;
		if (!rows.length) {
			this.$body.html(`
				<div class="automations-empty">
					<h4>${__("No automations yet")}</h4>
					<p class="text-muted">${__("An automation does work for you when something happens in ERPNext: a document is saved, a schedule comes round, or someone clicks Run.")}</p>
				</div>`);
			return;
		}
		this.$body.html(`
			<table class="table automations-table">
				<thead><tr>
					<th>${__("Automation")}</th><th>${__("Starts when")}</th><th>${__("Status")}</th>
					<th class="text-right">${__("Runs (24 h)")}</th><th class="text-right">${__("Failed (24 h)")}</th>
					<th>${__("Last run")}</th><th></th>
				</tr></thead>
				<tbody>${rows
					.map(
						(row) => `
					<tr data-name="${esc(row.name)}">
						<td><a href="/app/automation-builder/${encodeURIComponent(row.name)}" class="automations-title">${esc(row.title)}</a>
							<div class="text-muted small">${esc(row.name)}${row.version ? ` · ${__("version {0}", [row.version])}` : ""}</div></td>
						<td>${esc(this.triggerSummary(row))}</td>
						<td><span class="indicator-pill ${AUTOMATION_STATUS_COLORS[row.status] || "gray"}" title="${esc(row.paused_reason || "")}">${__(row.status)}</span></td>
						<td class="text-right">${row.runs_24h || 0}</td>
						<td class="text-right ${row.failures_24h ? "text-danger" : ""}">${row.failures_24h || 0}</td>
						<td>${row.last_run_at ? `${frappe.datetime.prettyDate(row.last_run_at, true)} · ${esc(__(row.last_run_status || ""))}` : '<span class="text-muted">—</span>'}</td>
						<td class="text-right automations-actions">${this.actions(row)}</td>
					</tr>`
					)
					.join("")}</tbody>
			</table>`);
		this.$body.find("[data-action]").on("click", (event) => {
			const $button = $(event.currentTarget);
			this.act($button.data("action"), $button.closest("tr").data("name"));
		});
	}

	triggerSummary(row) {
		if (row.trigger_type === "trigger.document_event") {
			const event = DOCUMENT_EVENTS.find(([key]) => key === row.trigger_event);
			return row.trigger_doctype ? `${__(row.trigger_doctype)} ${event ? event[1] : row.trigger_event || ""}` : __("Document event");
		}
		if (row.trigger_type === "trigger.schedule") return row.trigger_cron ? __("On a schedule ({0})", [row.trigger_cron]) : __("On a schedule");
		if (row.trigger_type === "trigger.manual") return __("Someone clicks Run");
		return row.trigger_type || "";
	}

	actions(row) {
		if (!frappe.model.can_write("Automation")) return "";
		const buttons = [];
		if (row.status === "Active") buttons.push(["pause", __("Pause")]);
		if (row.status === "Paused" && row.active_version) buttons.push(["resume", __("Resume")]);
		buttons.push(["duplicate", __("Duplicate")]);
		return buttons.map(([action, label]) => `<button class="btn btn-xs btn-default" data-action="${action}">${label}</button>`).join(" ");
	}

	async act(action, name) {
		const { message } = await frappe.call({ method: `${AUTOMATIONS_API}.${action}`, args: { name }, freeze: true });
		if (action === "duplicate") return frappe.set_route("automation-builder", message.name);
		this.refresh();
	}

	async create() {
		if (!this.templates) {
			const { message } = await frappe.call({ method: `${AUTOMATIONS_API}.list_templates` });
			this.templates = message || [];
		}
		const dialog = new frappe.ui.Dialog({
			title: __("New Automation"),
			fields: [
				{
					fieldname: "template",
					fieldtype: "Select",
					label: __("Start from"),
					options: [{ value: "", label: __("A blank automation") }, ...this.templates.map((t) => ({ value: t.key, label: t.title }))],
					onchange: () => {
						const chosen = this.templates.find((t) => t.key === dialog.get_value("template"));
						dialog.set_df_property("template_help", "options", chosen ? `<p class="text-muted">${frappe.utils.escape_html(chosen.description)}</p>` : "");
						if (chosen && !dialog.get_value("title")) dialog.set_value("title", chosen.title);
					},
				},
				{ fieldname: "template_help", fieldtype: "HTML" },
				{ fieldname: "title", fieldtype: "Data", label: __("Title"), reqd: 1 },
				{
					fieldname: "trigger_type",
					depends_on: "eval:!doc.template",
					fieldtype: "Select",
					label: __("Starts when"),
					reqd: 1,
					default: "trigger.document_event",
					options: [
						{ value: "trigger.document_event", label: __("A document changes") },
						{ value: "trigger.schedule", label: __("On a schedule") },
						{ value: "trigger.manual", label: __("Someone clicks Run") },
					],
				},
				{
					fieldname: "doctype",
					fieldtype: "Link",
					options: "DocType",
					label: __("Document type"),
					depends_on: "eval:!doc.template && doc.trigger_type != 'trigger.schedule'",
					mandatory_depends_on: "eval:!doc.template && doc.trigger_type == 'trigger.document_event'",
					get_query: () => ({ filters: { istable: 0, issingle: 0 } }),
				},
				{
					fieldname: "event",
					fieldtype: "Select",
					label: __("When it"),
					default: "after_insert",
					options: DOCUMENT_EVENTS.map(([value, label]) => ({ value, label })),
					depends_on: "eval:!doc.template && doc.trigger_type == 'trigger.document_event'",
				},
				{
					fieldname: "frequency",
					fieldtype: "Select",
					label: __("Every"),
					default: "daily",
					options: ["hourly", "daily", "weekly", "monthly"],
					depends_on: "eval:!doc.template && doc.trigger_type == 'trigger.schedule'",
				},
				{
					fieldname: "time",
					fieldtype: "Data",
					label: __("At (HH:MM)"),
					default: "09:00",
					depends_on: "eval:!doc.template && doc.trigger_type == 'trigger.schedule'",
				},
			],
			primary_action_label: __("Create"),
			primary_action: async (values) => {
				if (values.template) {
					const { message } = await frappe.call({
						method: `${AUTOMATIONS_API}.create_from_template`,
						args: { template: values.template, title: values.title },
						freeze: true,
					});
					dialog.hide();
					frappe.show_alert({ message: __("Created from the template. Check the settings, test it, then activate."), indicator: "green" });
					return frappe.set_route("automation-builder", message.name);
				}
				const config = {};
				if (values.trigger_type === "trigger.document_event") Object.assign(config, { doctype: values.doctype, event: values.event });
				if (values.trigger_type === "trigger.manual" && values.doctype) config.doctype = values.doctype;
				if (values.trigger_type === "trigger.schedule") Object.assign(config, { frequency: values.frequency, time: values.time });
				const { message } = await frappe.call({
					method: `${AUTOMATIONS_API}.create_automation`,
					args: { title: values.title, trigger_type: values.trigger_type, trigger_config: config },
					freeze: true,
				});
				dialog.hide();
				frappe.set_route("automation-builder", message.name);
			},
		});
		dialog.show();
	}

	importFile() {
		const input = document.createElement("input");
		input.type = "file";
		input.accept = ".json,application/json";
		input.addEventListener("change", async () => {
			const file = input.files[0];
			if (!file) return;
			let spec;
			try {
				spec = JSON.parse(await file.text());
			} catch (error) {
				frappe.msgprint(__("That file is not valid JSON."));
				return;
			}
			const { message } = await frappe.call({ method: `${AUTOMATIONS_API}.import_spec`, args: { spec }, freeze: true });
			frappe.show_alert({ message: __("Imported as a draft. Check it, then activate."), indicator: "green" });
			frappe.set_route("automation-builder", message.name);
		});
		input.click();
	}
}

frappe.dom.set_style(`
	.automations-page { padding: var(--padding-md) 0; }
	.automations-table td { vertical-align: middle; }
	.automations-title { font-weight: 600; }
	.automations-empty { text-align: center; padding: 64px 16px; }
	.automations-actions { white-space: nowrap; }
	.automations-health { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
	.automations-off { width: 100%; padding: 8px 12px; border-radius: var(--border-radius); background: var(--bg-orange); color: var(--text-on-orange); }
	.automations-tile { min-width: 120px; padding: 10px 14px; border: 1px solid var(--border-color); border-radius: var(--border-radius-lg); background: var(--card-bg); }
	.automations-tile-value { font-size: var(--text-xl); font-weight: 600; }
	.automations-tile-label { font-size: var(--text-sm); color: var(--text-muted); }
	.automations-tile.bad .automations-tile-value { color: var(--red-600); }
	.automations-tile.warn .automations-tile-value { color: var(--orange-600); }
`);
