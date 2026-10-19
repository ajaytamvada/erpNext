frappe.pages["agent-tools"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/common.js",
	]);
	const studio = window.pridict.agentStudio;
	const { t, escape, badge } = studio;

	class AgentToolsPage extends studio.StudioPage {
		constructor(wrapper) {
			super(wrapper, {
				route: "agent-tools",
				title: "Tools & Connectors",
				eyebrow: "Agent Studio · Step 4",
				intro: "Tools are the only way an agent can touch your data. Each one is a tested Python function with a fixed input, a fixed output, a permission scope and an audit log.",
			});
			this.selected = "get_open_purchase_orders";
			this.filter = "all";
			this.reload();
		}

		fetch() {
			return studio.call("get_tools");
		}

		render() {
			const tools = this.data.tools.filter((tool) =>
				this.filter === "all" ? true : this.filter === "read" ? tool.access === "Read" : tool.access !== "Read"
			);
			const tool = this.data.tools.find((x) => x.name === this.selected) || this.data.tools[0];
			const reads = this.data.tools.filter((x) => x.access === "Read").length;
			const calls = this.data.tools.reduce((s, x) => s + x.calls_7d, 0);
			const errors = this.data.tools.reduce((s, x) => s + x.errors_7d, 0);
			return `
				<div class="as-metrics">
					${studio.metric("Read tools", reads, t("Safe: only look at data"))}
					${studio.metric("Write tools", this.data.tools.length - reads, t("Create drafts; need approval"))}
					${studio.metric("Calls (7 days)", calls)}
					${studio.metric("Error rate", calls ? `${((100 * errors) / calls).toFixed(1)}%` : "—", calls ? `${errors} ${t("failed call(s)")}` : t("No calls yet"))}
					${studio.metric("Blocked", this.data.tools.filter((x) => x.status === "Blocked for agents").length, t("Never callable by agents"))}
				</div>
				<div class="as-split">
					<section class="as-panel">
						<div class="as-panel-head">
							<h2>${t("Tool registry")}</h2>
							<div class="as-actions">
								${["all", "read", "write"].map((f) => `<button type="button" class="btn btn-xs ${this.filter === f ? "btn-primary" : "btn-default"} as-filter" data-filter="${f}">${t(f === "all" ? "All" : f === "read" ? "Read" : "Write")}</button>`).join("")}
							</div>
						</div>
						<div class="as-table-scroll">
							<table class="as-table">
								<thead><tr><th>${t("Tool")}</th><th>${t("Access")}</th><th>${t("Target")}</th><th>${t("Calls 7d")}</th><th>${t("Status")}</th></tr></thead>
								<tbody>
									${tools.map((x) => `
										<tr class="is-selectable ${x.name === this.selected ? "is-selected" : ""}" data-name="${escape(x.name)}">
											<td><code>${escape(x.name)}</code></td>
											<td>${badge(x.access)}</td>
											<td>${escape(x.target)}</td>
											<td>${x.calls_7d}</td>
											<td>${badge(x.status)}</td>
										</tr>`).join("")}
								</tbody>
							</table>
						</div>
					</section>

					<aside class="as-panel">
						<div class="as-panel-head">
							<h2><code>${escape(tool.name)}</code></h2>
							${badge(tool.status)}
						</div>
						<p>${escape(tool.description || "")}</p>
						<div class="as-table-scroll"><table class="as-table"><tbody>
							<tr><td class="as-muted">${t("Access")}</td><td>${escape(tool.access)}</td></tr>
							<tr><td class="as-muted">${t("Target")}</td><td>${escape(tool.target)}</td></tr>
							<tr><td class="as-muted">${t("Permission scope")}</td><td>${escape(tool.scope)}</td></tr>
							<tr><td class="as-muted">${t("Timeout")}</td><td>${tool.timeout_s}s</td></tr>
							<tr><td class="as-muted">${t("Error rate (7d)")}</td><td>${tool.calls_7d ? `${tool.error_pct}%` : "—"}</td></tr>
							<tr><td class="as-muted">${t("Implementation")}</td><td><code>${escape(tool.python_method || "")}</code></td></tr>
						</tbody></table></div>
						<h3 style="margin-top:14px">${t("Input schema")}</h3>
						${studio.json(tool.input)}
						<h3 style="margin-top:14px">${t("Output schema")}</h3>
						${studio.json(tool.output)}
						<div class="as-callout" style="margin-top:14px">
							${tool.access === "Read"
								? t("Runs as the user who started the run, so that user's permissions still apply. The agent never gets more access than the person using it.")
								: t("Write tools need an approval_id. The server checks the approval is valid, unused and matches this exact action before running.")}
						</div>
						<div class="as-actions">
							${studio.formLink("Change status", "Agent Tool", tool.name)}
							${tool.access === "Read" && tool.status === "Enabled" ? `<button type="button" class="btn btn-default btn-sm as-try" data-tool="${escape(tool.name)}">${t("Try it")}</button>` : ""}
						</div>
					</aside>
				</div>`;
		}

		bind(body) {
			body.querySelectorAll("tr[data-name]").forEach((row) =>
				row.addEventListener("click", () => {
					this.selected = row.dataset.name;
					this.refresh();
				})
			);
			body.querySelector(".as-try")?.addEventListener("click", (event) => this.tryTool(event.currentTarget.dataset.tool));
			body.querySelectorAll(".as-filter").forEach((button) =>
				button.addEventListener("click", () => {
					this.filter = button.dataset.filter;
					this.refresh();
				})
			);
		}
	}

	AgentToolsPage.prototype.tryTool = function (name) {
		const tool = this.data.tools.find((x) => x.name === name);
		// Pre-fill the arguments with the schema's field names so the admin only fills values.
		const example = Object.fromEntries(Object.entries(tool.input.properties || {}).map(([key, spec]) => [key, spec.type === "array" ? [] : spec.type === "string" ? "" : null]));
		const dialog = new frappe.ui.Dialog({
			title: __("Try {0}", [name]),
			size: "large",
			fields: [
				{ fieldname: "arguments", fieldtype: "Code", options: "JSON", label: __("Arguments"), default: JSON.stringify(example, null, 2) },
				{ fieldname: "result", fieldtype: "HTML" },
			],
			primary_action_label: __("Run as me"),
			primary_action: async ({ arguments: args }) => {
				const r = await frappe.xcall("pridict.agent_studio.tools.try_tool", { name, arguments: args });
				dialog.fields_dict.result.$wrapper.html(
					`<p class="as-muted">${r.ok ? __("Succeeded") : __("Failed")} · ${r.duration_ms ?? 0} ms</p>
					<pre style="max-height:360px;overflow:auto;font-size:12px;padding:10px;border-radius:6px;background:var(--control-bg)">${escape(r.ok ? JSON.stringify(r.result, null, 2) : r.error)}</pre>`
				);
			},
		});
		dialog.show();
	};

	wrapper.agent_studio = new AgentToolsPage(wrapper);
};
