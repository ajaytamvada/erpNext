frappe.pages["agent-registry"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/common.js",
	]);
	const studio = window.pridict.agentStudio;
	const { t, escape, badge, formLink } = studio;

	const modes = {
		readonly: ["Read-only analysis", "Reads business data and explains. Cannot create anything."],
		recommend: ["Recommend and prepare drafts", "Prepares a proposal; a human must approve before a draft document is created."],
		execute: ["Execute authorized actions after approval", "After approval, may create permitted draft documents automatically."],
	};

	class AgentRegistryPage extends studio.StudioPage {
		constructor(wrapper) {
			super(wrapper, {
				route: "agent-registry",
				title: "Agent Registry",
				eyebrow: "Agent Studio · Step 2",
				intro: "Each agent is a managed record: what it is for, which model it uses, which tools it may call, how far it may go on its own, and who owns it.",
			});
			this.selected = null;
			this.reload();
		}

		fetch() {
			return studio.call("get_agents");
		}

		render() {
			const { agents } = this.data;
			if (!agents.some((a) => a.name === this.selected)) this.selected = agents[0]?.name;
			const agent = agents.find((a) => a.name === this.selected);
			return `
				<section class="as-panel">
					<div class="as-panel-head">
						<h2>${t("Agents")}</h2>
						${formLink("New agent", "Agent Definition", "", "btn btn-primary btn-sm")}
					</div>
					${agents.length ? `
						<div class="as-table-scroll">
							<table class="as-table">
								<thead><tr><th>${t("Agent")}</th><th>${t("Module")}</th><th>${t("Type")}</th><th>${t("Model")}</th><th>${t("Mode")}</th><th>${t("Version")}</th><th>${t("Status")}</th></tr></thead>
								<tbody>
									${agents.map((a) => `
										<tr class="is-selectable ${a.name === this.selected ? "is-selected" : ""}" data-name="${escape(a.name)}">
											<td><strong>${escape(a.name)}</strong><div class="as-muted">${escape(a.owner || "")}</div></td>
											<td>${escape(a.module || "—")}</td>
											<td>${escape(a.type)}</td>
											<td><code>${escape(a.model_config || "—")}</code></td>
											<td>${t(modes[a.mode]?.[0] || a.mode)}</td>
											<td>${escape(a.version)}</td>
											<td>${badge(a.status)}</td>
										</tr>`).join("")}
								</tbody>
							</table>
						</div>` : studio.empty("No agents yet.")}
				</section>
				${agent ? this.renderAgent(agent) : ""}`;
		}

		renderAgent(agent) {
			const tools = this.data.tools;
			const granted = new Set(agent.tools);
			return `
				<div class="as-split">
					<section class="as-panel">
						<div class="as-panel-head">
							<h2>${escape(agent.name)} <span class="as-muted">${escape(agent.version)}</span></h2>
							${formLink("Edit agent", "Agent Definition", agent.name, "btn btn-primary btn-sm")}
						</div>
						<h3>${t("Execution mode")}</h3>
						<p><strong>${t(modes[agent.mode]?.[0] || agent.mode)}</strong><br><span class="as-help">${t(modes[agent.mode]?.[1] || "")}</span></p>
						<h3>${t("Allowed tools")} <span class="as-help">${granted.size} ${t("of")} ${tools.length}</span></h3>
						<div class="as-tool-checks">
							${tools.map((tool) => `
								<span class="as-check ${granted.has(tool.name) ? "" : "as-muted"}">
									<i class="fa ${granted.has(tool.name) ? "fa-check-square-o" : "fa-square-o"}" aria-hidden="true"></i>
									<span><code>${escape(tool.name)}</code> <span class="as-help">${t(tool.access)}${tool.status !== "Enabled" ? ` · ${t(tool.status)}` : ""}</span></span>
								</span>`).join("")}
						</div>
						<h3 style="margin-top:14px">${t("System instructions")}</h3>
						<pre class="as-code">${escape(agent.instructions || "")}</pre>
					</section>

					<aside class="as-panel as-preview">
						<h2>${t("Configuration")}</h2>
						<div class="as-config-preview">${this.renderPreview(agent)}</div>
						<h3 style="margin-top:14px">${t("Output schema")}</h3>
						${studio.json(agent.output_schema)}
						<h3 style="margin-top:14px">${t("Change history")}</h3>
						${agent.history.length ? `
							<ul class="as-muted" style="padding-left:18px;margin:0">
								${agent.history.map((h) => `<li>${h.version ? `<strong>${escape(h.version)}</strong> · ` : ""}${escape(h.date)} · ${escape(h.author)}${h.note ? ` · ${escape(h.note)}` : ""}</li>`).join("")}
							</ul>` : `<p class="as-muted">${t("No changes since the agent was created.")}</p>`}
					</aside>
				</div>`;
		}

		renderPreview(agent) {
			const config = this.data.modelConfigs.find((c) => c.name === agent.model_config);
			const rows = [
				["Provider", config?.provider || "—"],
				["Model", config?.model_id || "—"],
				["Temperature", config ? config.temperature : "—"],
				["Step limit", agent.max_steps],
				["Max runtime", `${agent.max_runtime_s}s`],
				["Token budget", Number(agent.token_budget).toLocaleString()],
				["Tools", `${agent.tools.length} ${__("allowed")}`],
				["Approval gate", agent.approval_required ? __("Required") : __("Not required")],
			];
			return `
				<div class="as-table-scroll"><table class="as-table"><tbody>
					${rows.map(([k, v]) => `<tr><td class="as-muted">${t(k)}</td><td><strong>${escape(v)}</strong></td></tr>`).join("")}
				</tbody></table></div>`;
		}

		bind(body) {
			body.querySelectorAll("tr[data-name]").forEach((row) =>
				row.addEventListener("click", () => {
					this.selected = row.dataset.name;
					this.refresh();
				})
			);
		}
	}

	wrapper.agent_studio = new AgentRegistryPage(wrapper);
};
