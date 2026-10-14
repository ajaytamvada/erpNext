frappe.pages["agent-models"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/common.js",
	]);
	const studio = window.pridict.agentStudio;
	const { t, escape, badge, formLink } = studio;

	class AgentModelsPage extends studio.StudioPage {
		constructor(wrapper) {
			super(wrapper, {
				route: "agent-models",
				title: "Models & Providers",
				eyebrow: "Agent Studio · Step 1",
				intro: "Register LLM providers once and define reusable model configurations. Agents pick a configuration instead of storing their own keys and settings.",
			});
			this.selected = null;
			this.reload();
		}

		fetch() {
			return studio.call("get_models");
		}

		render() {
			const { providers, modelConfigs } = this.data;
			if (!modelConfigs.some((c) => c.name === this.selected)) this.selected = modelConfigs[0]?.name;
			const config = modelConfigs.find((c) => c.name === this.selected);
			return `
				<div class="as-panel-head">
					<h2>${t("Providers")}</h2>
					${formLink("New provider", "LLM Provider")}
				</div>
				${providers.length ? `
					<section class="as-grid-cards">
						${providers.map((p) => `
							<article class="as-card">
								<div class="as-card-head">
									<h3>${escape(p.name)}</h3>
									${badge(p.enabled ? p.status : "Disabled")}
								</div>
								<dl>
									<dt>${t("Type")}</dt><dd>${escape(p.provider_type)}</dd>
									<dt>${t("Endpoint")}</dt><dd><code>${escape(p.endpoint)}</code></dd>
									${p.api_version ? `<dt>${t("API version")}</dt><dd><code>${escape(p.api_version)}</code></dd>` : ""}
									<dt>${t("API key")}</dt><dd>${p.key_set ? t("Stored (encrypted)") : `<span class="as-text-bad">${t("Not set")}</span>`}</dd>
									<dt>${t("Latency")}</dt><dd>${p.last_latency_ms ? `${p.last_latency_ms} ms` : "—"}</dd>
									<dt>${t("Models")}</dt><dd>${p.models}</dd>
								</dl>
								${p.last_error ? `<p class="as-muted">${escape(p.last_error)}</p>` : ""}
								<div class="as-actions">
									${formLink("Edit", "LLM Provider", p.name, "btn btn-default btn-xs")}
									<button type="button" class="btn btn-default btn-xs as-test" data-provider="${escape(p.name)}">${t("Test connection")}</button>
								</div>
							</article>`).join("")}
					</section>` : studio.empty("No providers yet.", "Add the LLM service your company uses, such as an Azure OpenAI resource.")}

				<div class="as-split">
					<section class="as-panel">
						<div class="as-panel-head">
							<h2>${t("Model configurations")}</h2>
							${formLink("New configuration", "LLM Model Config", "", "btn btn-primary btn-sm")}
						</div>
						${modelConfigs.length ? `
							<div class="as-table-scroll">
								<table class="as-table">
									<thead><tr>
										<th>${t("Name")}</th><th>${t("Provider")}</th><th>${t("Model ID")}</th><th>${t("Temp.")}</th><th>${t("Fallback")}</th><th>${t("Status")}</th>
									</tr></thead>
									<tbody>
										${modelConfigs.map((c) => `
											<tr class="is-selectable ${c.name === this.selected ? "is-selected" : ""}" data-name="${escape(c.name)}">
												<td><strong>${escape(c.name)}</strong><div class="as-muted">${t("Used by")} ${c.used_by} ${t("agent(s)")}</div></td>
												<td>${escape(c.provider)}</td>
												<td><code>${escape(c.model_id)}</code></td>
												<td>${c.temperature}</td>
												<td>${escape(c.fallback || "—")}</td>
												<td>${badge(c.status)}</td>
											</tr>`).join("")}
									</tbody>
								</table>
							</div>` : studio.empty("No model configurations yet.", "Create one after adding a provider.")}
					</section>

					<section class="as-panel">
						${config ? this.renderConfig(config) : studio.empty("Select a configuration.")}
					</section>
				</div>`;
		}

		renderConfig(config) {
			const rows = [
				["Provider", escape(config.provider)],
				["Model / deployment ID", `<code>${escape(config.model_id)}</code>`],
				["Temperature", `${config.temperature} <span class="as-help">${t("0 = most consistent, 1 = most creative")}</span>`],
				["Max output tokens", config.max_tokens],
				["Timeout", `${config.timeout_s}s`],
				["Retries", config.retries],
				["Fallback configuration", escape(config.fallback || t("None"))],
			];
			return `
				<div class="as-panel-head">
					<h2>${t("Configuration")}: ${escape(config.name)}</h2>
					${badge(config.status)}
				</div>
				${config.description ? `<p class="as-muted">${escape(config.description)}</p>` : ""}
				<div class="as-table-scroll"><table class="as-table"><tbody>
					${rows.map(([label, value]) => `<tr><td class="as-muted">${t(label)}</td><td>${value}</td></tr>`).join("")}
				</tbody></table></div>
				<div class="as-callout" style="margin-top:14px">
					<strong>${t("Security")}:</strong> ${t("API keys are stored encrypted on the provider record. They are never sent to the browser or written to logs and traces.")}
				</div>
				<div class="as-actions">
					${formLink("Edit configuration", "LLM Model Config", config.name, "btn btn-primary btn-sm")}
					<button type="button" class="btn btn-default btn-sm as-test" data-provider="${escape(config.provider)}">${t("Send test prompt")}</button>
				</div>`;
		}

		bind(body) {
			body.querySelectorAll("tr[data-name]").forEach((row) =>
				row.addEventListener("click", () => {
					this.selected = row.dataset.name;
					this.refresh();
				})
			);
			body.querySelectorAll(".as-test").forEach((button) =>
				button.addEventListener("click", () => this.notify("Connection testing arrives with the LLM gateway (next build step).", "orange"))
			);
		}
	}

	wrapper.agent_studio = new AgentModelsPage(wrapper);
};
