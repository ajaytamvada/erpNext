frappe.pages["agent-policies"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/sample_data.js",
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
			this.refresh();
		}

		render() {
			const s = this.data.scenario;
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
										${group.rules.map((r) => `<tr><td><strong>${t(r.name)}</strong></td><td>${escape(r.value)}</td><td>${badge(r.severity)}</td></tr>`).join("")}
									</tbody>
								</table></div>
							</section>`).join("")}
					</div>

					<aside class="as-panel as-preview">
						<h2>${t("Policy check simulator")}</h2>
						<p class="as-muted">${t("Result of checking the current proposal:")} ${escape(s.net_shortage)} ${escape(s.uom)} ${escape(s.item_name)}, ${t("RFQ to 3 suppliers, estimated")} ${studio.inr(s.net_shortage * 258)}</p>
						<div class="as-table-scroll"><table class="as-table">
							<tbody>
								${this.data.policyCheck.map((c) => `<tr><td>${badge(c.result)}</td><td><strong>${t(c.rule)}</strong><div class="as-muted">${escape(c.detail)}</div></td></tr>`).join("")}
							</tbody>
						</table></div>
						<div class="as-callout" style="margin-top:14px">
							<strong>${t("Outcome")}:</strong> ${t("Allowed with one Purchase Manager approval. The watchlist warning is shown to the approver.")}
						</div>
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
