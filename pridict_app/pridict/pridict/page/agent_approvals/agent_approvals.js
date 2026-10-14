frappe.pages["agent-approvals"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/sample_data.js",
		"/assets/pridict/js/agent_studio/common.js",
	]);
	const studio = window.pridict.agentStudio;
	const { t, escape, badge, inr } = studio;

	class AgentApprovalsPage extends studio.StudioPage {
		constructor(wrapper) {
			super(wrapper, {
				route: "agent-approvals",
				title: "Approval Inbox",
				eyebrow: "Agent Studio · Step 7",
				intro: "Proposals that need a person's decision. The agent has stopped and is waiting. Nothing has been created in ERPNext yet.",
			});
			this.selected = this.data.approvals[0].name;
			this.decisions = {};
			this.refresh();
		}

		status(approval) {
			return this.decisions[approval.name] || approval.status;
		}

		render() {
			const approval = this.data.approvals.find((a) => a.name === this.selected);
			return `
				<div class="as-split-wide">
					<section class="as-panel">
						<h2>${t("Requests")}</h2>
						<div class="as-table-scroll"><table class="as-table">
							<tbody>
								${this.data.approvals.map((a) => `
									<tr class="is-selectable ${a.name === this.selected ? "is-selected" : ""}" data-name="${escape(a.name)}">
										<td><strong>${escape(a.name)}</strong><div class="as-muted">${escape(a.action)} · ${inr(a.value)}</div><div class="as-muted">${escape(a.requested_by)} · ${escape(a.created)}</div></td>
										<td>${badge(this.status(a))}</td>
									</tr>`).join("")}
							</tbody>
						</table></div>
					</section>
					${approval.name === this.data.approvals[0].name ? this.renderDetail(approval) : this.renderSummary(approval)}
				</div>`;
		}

		renderSummary(approval) {
			return `
				<section class="as-panel">
					<h2>${escape(approval.name)} ${badge(this.status(approval))}</h2>
					<p>${escape(approval.action)} · ${inr(approval.value)} · ${t("Risk")}: ${badge(approval.risk)}</p>
					<p class="as-muted">${t("Full evidence is shown in the sample for")} ${escape(this.data.approvals[0].name)}.</p>
				</section>`;
		}

		renderDetail(approval) {
			const s = this.data.scenario;
			const status = this.status(approval);
			const estimate = s.net_shortage * 258;
			return `
				<section class="as-panel">
					<div class="as-panel-head">
						<div>
							<h2>${t("Create Draft RFQ")}: ${escape(s.net_shortage)} ${escape(s.uom)} ${escape(s.item_name)}</h2>
							<p class="as-muted" style="margin:0">${escape(approval.name)} · ${t("from")} <a href="#" class="as-open-run">${escape(approval.run)}</a> · ${t("requested by")} ${escape(approval.requested_by)}</p>
						</div>
						${badge(status)}
					</div>

					<h3>${t("Evidence from ERPNext")}</h3>
					<div class="as-evidence">
						<div><span>${t("Required")}</span><strong>${s.required_qty} ${escape(s.uom)}</strong></div>
						<div><span>${t("In stock")} (${escape(s.warehouse)})</span><strong>${s.stock_qty} ${escape(s.uom)}</strong></div>
						<div><span>${t("Open PO")} ${escape(s.open_po.name)}</span><strong>${s.open_po.qty} ${escape(s.uom)}</strong></div>
						<div><span>${t("Net shortage")}</span><strong>${s.net_shortage} ${escape(s.uom)}</strong></div>
					</div>
					<div class="as-callout">
						<strong>${t("Calculation (done by code, not the LLM)")}:</strong>
						${s.required_qty} ${t("required")} − ${s.stock_qty} ${t("in stock")} − ${s.open_po.qty} ${t("arriving on")} ${escape(s.open_po.schedule_date)} (${t("before need-by")} ${escape(s.need_by)}) = <strong>${s.net_shortage} ${escape(s.uom)}</strong>
					</div>

					<h3>${t("Agent recommendation")}</h3>
					<p>${t("Send an RFQ to all three approved suppliers. Preferred: Bharat Metals & Alloys. It has the best balance of price (₹258/kg, 1.5% below the 90-day average) and reliability (score 78), and its 10-day lead time meets the 30 October date. Hindalco is the safer but more expensive alternative.")}</p>
					<div class="as-table-scroll"><table class="as-table">
						<thead><tr><th>${t("Supplier")}</th><th>${t("Score")}</th><th>${t("Last price")}</th><th>${t("Lead time")}</th><th>${t("Open quotation")}</th><th>${t("Note")}</th></tr></thead>
						<tbody>
							${this.data.suppliers.map((x, i) => `<tr>
								<td><strong>${escape(x.supplier)}</strong> ${i === 0 ? badge("Recommended") : ""}</td>
								<td>${x.score} ${badge(x.tier)}</td>
								<td>₹${x.last_price}/kg</td>
								<td>${x.lead_time_days} ${t("days")}</td>
								<td>${escape(x.quote)}</td>
								<td>${escape(x.note)}</td>
							</tr>`).join("")}
						</tbody>
					</table></div>
					<p class="as-muted" style="margin-top:8px">${t("Excluded")}: Coastal Alloys (${t("not an approved supplier for this item")}).</p>

					<h3 style="margin-top:14px">${t("Policy checks")}</h3>
					<div class="as-table-scroll"><table class="as-table"><tbody>
						${this.data.policyCheck.map((c) => `<tr><td style="width:80px">${badge(c.result)}</td><td>${t(c.rule)}<div class="as-muted">${escape(c.detail)}</div></td></tr>`).join("")}
					</tbody></table></div>

					<h3 style="margin-top:14px">${t("Your decision")}</h3>
					<div class="as-decision">
						<p class="as-muted" style="margin:0">${t("Estimated value")} ${inr(estimate)} · ${t("Required approver")}: Purchase Manager</p>
						<textarea class="form-control as-comment" placeholder="${t("Comment (required for reject or request changes)")}"></textarea>
						<div class="as-actions">
							<button type="button" class="btn btn-primary btn-sm as-decide" data-decision="Approved" ${status !== "Pending" ? "disabled" : ""}>${t("Approve")}</button>
							<button type="button" class="btn btn-default btn-sm as-decide" data-decision="Changes requested" ${status !== "Pending" ? "disabled" : ""}>${t("Request changes")}</button>
							<button type="button" class="btn btn-danger btn-sm as-decide" data-decision="Rejected" ${status !== "Pending" ? "disabled" : ""}>${t("Reject")}</button>
						</div>
						<p class="as-muted" style="margin:0">${t("On approval, the server re-checks your permission, current stock and all policies, then resumes the run. The agent creates the RFQ as a Draft. Submitting it stays a separate, manual step.")}</p>
					</div>
				</section>`;
		}

		bind(body) {
			body.querySelectorAll("tr[data-name]").forEach((row) =>
				row.addEventListener("click", () => {
					this.selected = row.dataset.name;
					this.refresh();
				})
			);
			body.querySelector(".as-open-run")?.addEventListener("click", (event) => {
				event.preventDefault();
				frappe.set_route("agent-runs");
			});
			body.querySelectorAll(".as-decide").forEach((button) =>
				button.addEventListener("click", () => {
					const decision = button.dataset.decision;
					const comment = body.querySelector(".as-comment").value.trim();
					if (decision !== "Approved" && !comment) {
						this.notify("Please add a comment explaining your decision.", "red");
						return;
					}
					this.decisions[this.selected] = decision;
					this.refresh();
					this.notify(`Sample mode: recorded "${decision}". A real decision would resume the paused run.`, "green");
				})
			);
		}
	}

	wrapper.agent_studio = new AgentApprovalsPage(wrapper);
};
