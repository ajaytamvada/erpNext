frappe.pages["agent-registry"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/sample_data.js",
		"/assets/pridict/js/agent_studio/common.js",
	]);
	const studio = window.pridict.agentStudio;
	const { t, escape, badge } = studio;

	const modes = [
		["readonly", "Read-only analysis", "Reads ERPNext data and explains. Cannot create anything."],
		["recommend", "Recommend and prepare drafts", "Prepares a proposal; a human must approve before a draft document is created."],
		["execute", "Execute authorized actions after approval", "After approval, may create permitted draft documents automatically."],
	];

	class AgentRegistryPage extends studio.StudioPage {
		constructor(wrapper) {
			super(wrapper, {
				route: "agent-registry",
				title: "Agent Registry",
				eyebrow: "Agent Studio · Step 2",
				intro: "Each agent is a managed record: what it is for, which model it uses, which tools it may call, how far it may go on its own, and who owns it.",
			});
			// Working copy of the selected agent so the preview reacts to form edits.
			this.form = structuredClone(this.data.agents[0]);
			this.refresh();
		}

		render() {
			const agent = this.form;
			return `
				<section class="as-panel">
					<div class="as-panel-head">
						<h2>${t("Agents")}</h2>
						<button type="button" class="btn btn-primary btn-sm as-new">${t("New agent")}</button>
					</div>
					<div class="as-table-scroll">
						<table class="as-table">
							<thead><tr><th>${t("Agent")}</th><th>${t("Module")}</th><th>${t("Type")}</th><th>${t("Model")}</th><th>${t("Mode")}</th><th>${t("Version")}</th><th>${t("Status")}</th></tr></thead>
							<tbody>
								${this.data.agents.map((a) => `
									<tr class="${a.name === agent.name ? "is-selected" : ""}">
										<td><strong>${escape(a.name)}</strong><div class="as-muted">${escape(a.owner)}</div></td>
										<td>${escape(a.module)}</td>
										<td>${escape(a.type)}</td>
										<td><code>${escape(a.model_config)}</code></td>
										<td>${t(modes.find((m) => m[0] === a.mode)?.[1] || a.mode)}</td>
										<td>${escape(a.version)}</td>
										<td>${badge(a.status)}</td>
									</tr>`).join("")}
							</tbody>
						</table>
					</div>
				</section>

				<div class="as-split">
					<section class="as-panel">
						<h2>${escape(agent.name)} <span class="as-muted">${escape(agent.version)}</span></h2>
						<form class="as-form" onsubmit="return false">
							<label class="as-field">${t("Agent name")}
								<input type="text" class="form-control" name="name" value="${escape(agent.name)}">
							</label>
							<label class="as-field">${t("Model configuration")}
								<select class="form-control" name="model_config">
									${this.data.modelConfigs.map((c) => `<option ${c.name === agent.model_config ? "selected" : ""} value="${escape(c.name)}">${escape(c.name)} (${escape(c.model_id)})</option>`).join("")}
								</select>
							</label>

							<fieldset class="as-field as-full">
								<span>${t("Execution mode")}</span>
								<div class="as-radio-group">
									${modes.map(([value, label, help]) => `
										<label><input type="radio" name="mode" value="${value}" ${agent.mode === value ? "checked" : ""}>
											<span><strong>${t(label)}</strong><br><span class="as-help">${t(help)}</span></span>
										</label>`).join("")}
								</div>
							</fieldset>

							<label class="as-field">${t("Temperature")}
								<span class="as-range-row"><input type="range" name="temperature" min="0" max="1" step="0.1" value="${agent.temperature}"><output>${agent.temperature}</output></span>
								<span class="as-help">${t("Low values suit extraction and consistent recommendations. It does not make answers factually correct.")}</span>
							</label>
							<label class="as-field">${t("Maximum reasoning steps")}
								<span class="as-range-row"><input type="range" name="max_steps" min="2" max="20" step="1" value="${agent.max_steps}"><output>${agent.max_steps}</output></span>
								<span class="as-help">${t("Hard stop so the agent cannot loop forever.")}</span>
							</label>
							<label class="as-field">${t("Max runtime (seconds)")}
								<input type="number" class="form-control" name="max_runtime_s" value="${agent.max_runtime_s}">
							</label>
							<label class="as-field">${t("Token budget per run")}
								<input type="number" class="form-control" name="token_budget" value="${agent.token_budget}">
							</label>

							<label class="as-check as-full">
								<input type="checkbox" name="approval_required" ${agent.approval_required ? "checked" : ""}>
								<span><strong>${t("Require human approval before creating or submitting purchasing documents")}</strong></span>
							</label>

							<fieldset class="as-field as-full">
								<span>${t("Allowed tools")} <span class="as-help">${t("Configured on the Tools & Connectors page")}</span></span>
								<div class="as-tool-checks">
									${this.data.tools.map((tool) => {
										const blocked = tool.status === "Blocked for agents" || tool.status === "Disabled";
										return `<label class="as-check"><input type="checkbox" name="tools" value="${escape(tool.name)}" ${agent.tools.includes(tool.name) ? "checked" : ""} ${blocked ? "disabled" : ""}>
											<span><code>${escape(tool.name)}</code> <span class="as-help">${escape(tool.access)}${blocked ? ` · ${t(tool.status)}` : ""}</span></span></label>`;
									}).join("")}
								</div>
							</fieldset>

							<label class="as-field as-full">${t("System instructions")}
								<textarea class="form-control" name="instructions">${escape(agent.instructions)}</textarea>
							</label>
						</form>
					</section>

					<aside class="as-panel as-preview">
						<h2>${t("Configuration preview")}</h2>
						<div class="as-config-preview">${this.renderPreview()}</div>
						<h3 style="margin-top:14px">${t("Output schema")}</h3>
						${studio.json(agent.output_schema)}
						<h3 style="margin-top:14px">${t("Version history")}</h3>
						<ul class="as-muted" style="padding-left:18px;margin:0">
							${agent.history.map((h) => `<li><strong>${escape(h.version)}</strong> · ${escape(h.date)} · ${escape(h.note)}</li>`).join("")}
						</ul>
						<div class="as-actions" style="margin-top:14px">
							<button type="button" class="btn btn-default btn-sm as-save">${t("Save draft")}</button>
							<button type="button" class="btn btn-primary btn-sm as-publish">${t("Publish v1.3")}</button>
						</div>
					</aside>
				</div>`;
		}

		renderPreview() {
			const a = this.form;
			const config = this.data.modelConfigs.find((c) => c.name === a.model_config);
			const rows = [
				["Provider", config?.provider],
				["Model", config?.model_id],
				["Mode", modes.find((m) => m[0] === a.mode)?.[1]],
				["Temperature", a.temperature],
				["Step limit", a.max_steps],
				["Tools", `${a.tools.length} enabled`],
				["Approval gate", a.approval_required ? "Required" : "Not required"],
			];
			const warning = !a.approval_required && a.mode !== "readonly"
				? `<div class="as-callout" style="border-left-color:#dc2626">${t("Policy will block publishing: agents that can write documents must keep the approval gate on.")}</div>`
				: "";
			return `
				<div class="as-table-scroll"><table class="as-table"><tbody>
					${rows.map(([k, v]) => `<tr><td class="as-muted">${t(k)}</td><td><strong>${escape(v)}</strong></td></tr>`).join("")}
				</tbody></table></div>${warning}`;
		}

		bind(body) {
			const form = body.querySelector("form");
			form.addEventListener("input", (event) => {
				const el = event.target;
				if (el.name === "tools") {
					this.form.tools = [...form.querySelectorAll('input[name="tools"]:checked')].map((i) => i.value);
				} else if (el.type === "checkbox") {
					this.form[el.name] = el.checked;
				} else if (el.type === "range" || el.type === "number") {
					this.form[el.name] = Number(el.value);
					if (el.nextElementSibling?.tagName === "OUTPUT") el.nextElementSibling.textContent = el.value;
				} else {
					this.form[el.name] = el.value;
				}
				body.querySelector(".as-config-preview").innerHTML = this.renderPreview();
			});
			body.querySelectorAll(".as-save, .as-publish, .as-new").forEach((button) =>
				button.addEventListener("click", () => this.notify("Sample mode: saving and publishing are enabled once the Agent Definition DocType exists.", "orange"))
			);
		}
	}

	wrapper.agent_studio = new AgentRegistryPage(wrapper);
};
