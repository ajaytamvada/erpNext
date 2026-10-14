frappe.pages["agent-policies"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/common.js",
	]);
	const studio = window.pridict.agentStudio;
	const { t, escape, badge } = studio;

	class AgentPoliciesPage extends studio.StudioPage {
		constructor(wrapper) {
			super(wrapper, {
				route: "agent-policies",
				title: "Policies & Guardrails",
				eyebrow: "Agent Studio · Step 5",
				intro: "Business rules the agent cannot talk its way around. They run as server-side Python before and after every risky step, independent of the LLM and its prompt.",
			});
			this.reload();
		}

		fetch() {
			return studio.call("get_policies");
		}

		render() {
			const latest = this.data.latestCheck;
			return `
				<div class="as-callout">
					<strong>${t("Why not just put these rules in the prompt?")}</strong>
					${t("A prompt is a request, not a guarantee. An LLM can misread or ignore it. These policies are checked by code, so a ₹30 lakh order is blocked even if the LLM is convinced it is fine.")}
				</div>
				<div class="as-split">
					<div>
						${this.data.policies.map((group) => `
							<section class="as-panel as-policy-group">
								<h3>${t(group.group)} <span class="as-enforced"><i class="fa fa-lock" aria-hidden="true"></i> ${t("Enforced by server code")}</span></h3>
								<div class="as-table-scroll"><table class="as-table">
									<thead><tr><th>${t("Rule")}</th><th>${t("Setting")}</th><th>${t("If broken")}</th></tr></thead>
									<tbody>
										${group.rules.map((r) => `
											<tr class="is-selectable ${r.enabled ? "" : "as-muted"}" data-open-doctype="Agent Policy" data-open-name="${escape(r.name)}">
												<td><strong>${t(r.name)}</strong>${r.enabled ? "" : ` ${badge("Disabled")}`}${r.agent ? `<div class="as-muted">${t("Only")}: ${escape(r.agent)}</div>` : ""}</td>
												<td>${escape(r.description)}</td>
												<td>${badge(r.severity)}</td>
											</tr>`).join("")}
									</tbody>
								</table></div>
							</section>`).join("")}
						<p class="as-muted">${t("Click a rule to change its setting. Every change is kept in the document history.")}</p>
					</div>

					<aside class="as-panel as-preview">
						<h2>${t("Latest policy check")}</h2>
						${latest ? `
							<p class="as-muted">${escape(latest.name)} · ${escape(latest.action || "")} · ${studio.inr(latest.estimated_value)} · ${badge(latest.status)}</p>
							<div class="as-table-scroll"><table class="as-table"><tbody>
								${latest.results.map((c) => `<tr><td>${badge(c.result)}</td><td><strong>${t(c.rule)}</strong><div class="as-muted">${escape(c.detail)}</div></td></tr>`).join("")}
							</tbody></table></div>`
						: studio.empty("No checks yet.", "The result of checking each agent proposal against these rules will appear here.")}
						<h3>${t("Legend")}</h3>
						<ul class="as-muted" style="padding-left:18px;margin:0">
							<li>${badge("Block")} ${t("The action cannot happen.")}</li>
							<li>${badge("Approval")} ${t("Allowed only after the named approver(s) agree.")}</li>
							<li>${badge("Warn")} ${t("Allowed, but highlighted to the approver.")}</li>
							<li>${badge("Ask buyer")} ${t("The run pauses and asks the buyer for the missing detail.")}</li>
						</ul>
					</aside>
				</div>`;
		}
	}

	wrapper.agent_studio = new AgentPoliciesPage(wrapper);
};
