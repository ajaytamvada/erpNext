frappe.pages["agent-models"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/sample_data.js",
		"/assets/pridict/js/agent_studio/common.js",
	]);
	const studio = window.pridict.agentStudio;
	const { t, escape, badge } = studio;

	class AgentModelsPage extends studio.StudioPage {
		constructor(wrapper) {
			super(wrapper, {
				route: "agent-models",
				title: "Models & Providers",
				eyebrow: "Agent Studio · Step 1",
				intro: "Register LLM providers once and define reusable model configurations. Agents pick a configuration instead of storing their own keys and settings.",
			});
			this.selected = this.data.modelConfigs[0].name;
			this.refresh();
		}

		render() {
			const config = this.data.modelConfigs.find((c) => c.name === this.selected);
			return `
				<section class="as-grid-cards">
					${this.data.providers.map((p) => `
						<article class="as-card">
							<div class="as-card-head">
								<h3>${escape(p.name)}</h3>
								${badge(p.status)}
							</div>
							<dl>
								<dt>${t("Endpoint")}</dt><dd><code>${escape(p.endpoint)}</code></dd>
								<dt>${t("API key")}</dt><dd><code>${escape(p.credential)}</code></dd>
								<dt>${t("Latency")}</dt><dd>${p.latency_ms ? `${p.latency_ms} ms` : "—"}</dd>
								<dt>${t("Models")}</dt><dd>${p.models}</dd>
							</dl>
							<button type="button" class="btn btn-default btn-xs as-test" data-provider="${escape(p.name)}">${t("Test connection")}</button>
						</article>`).join("")}
				</section>

				<div class="as-split">
					<section class="as-panel">
						<div class="as-panel-head">
							<h2>${t("Model configurations")}</h2>
							<button type="button" class="btn btn-primary btn-sm as-new">${t("New configuration")}</button>
						</div>
						<div class="as-table-scroll">
							<table class="as-table">
								<thead><tr>
									<th>${t("Name")}</th><th>${t("Provider")}</th><th>${t("Model ID")}</th><th>${t("Temp.")}</th><th>${t("Fallback")}</th><th>${t("Status")}</th>
								</tr></thead>
								<tbody>
									${this.data.modelConfigs.map((c) => `
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
						</div>
						<p class="as-muted" style="margin-top:10px">${t("Model IDs are examples. Use any model your provider account supports.")}</p>
					</section>

					<section class="as-panel">
						<h2>${t("Configuration")}: ${escape(config.name)}</h2>
						<div class="as-form">
							<label class="as-field">${t("Provider")}
								<select class="form-control">${this.data.providers.map((p) => `<option ${p.name === config.provider ? "selected" : ""}>${escape(p.name)}</option>`).join("")}</select>
							</label>
							<label class="as-field">${t("Model ID")}
								<input type="text" class="form-control" value="${escape(config.model_id)}">
							</label>
							<label class="as-field">${t("Temperature")} <span class="as-help">${t("0 = most consistent, 1 = most creative")}</span>
								<input type="number" class="form-control" step="0.1" min="0" max="1" value="${config.temperature}">
							</label>
							<label class="as-field">${t("Max output tokens")}
								<input type="number" class="form-control" value="${config.max_tokens}">
							</label>
							<label class="as-field">${t("Timeout (seconds)")}
								<input type="number" class="form-control" value="${config.timeout_s}">
							</label>
							<label class="as-field">${t("Retries")}
								<input type="number" class="form-control" value="${config.retries}">
							</label>
							<label class="as-field as-full">${t("Fallback configuration")} <span class="as-help">${t("Used automatically if this model fails or times out after all retries")}</span>
								<select class="form-control">
									<option value="">${t("None")}</option>
									${this.data.modelConfigs.filter((c) => c.name !== config.name).map((c) => `<option ${c.name === config.fallback ? "selected" : ""}>${escape(c.name)}</option>`).join("")}
								</select>
							</label>
						</div>
						<div class="as-callout" style="margin-top:14px">
							<strong>${t("Security")}:</strong> ${t("API keys are stored server-side in a secrets store and referenced by name (secret://...). They are never sent to the browser or written to logs and traces.")}
						</div>
						<div class="as-actions">
							<button type="button" class="btn btn-primary btn-sm as-save">${t("Save")}</button>
							<button type="button" class="btn btn-default btn-sm as-test" data-provider="${escape(config.provider)}">${t("Send test prompt")}</button>
						</div>
					</section>
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
				button.addEventListener("click", () => this.notify(`Sample mode: a real test would call ${button.dataset.provider} from the server.`))
			);
			body.querySelectorAll(".as-save, .as-new").forEach((button) =>
				button.addEventListener("click", () => this.notify("Sample mode: saving is enabled once the Model Configuration DocType exists.", "orange"))
			);
		}
	}

	wrapper.agent_studio = new AgentModelsPage(wrapper);
};
