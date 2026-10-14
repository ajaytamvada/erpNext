frappe.pages["agent-approvals"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/common.js",
	]);
	const studio = window.pridict.agentStudio;
	const { t, escape, badge, inr } = studio;

	// Agent Approval.proposal_json, as written by the procurement workflow:
	// { item_code, item_name, uom, warehouse, need_by, required_qty, stock_qty,
	//   open_orders: [{ name, supplier, pending_qty, schedule_date }], usable_open_qty, shortage_qty,
	//   recommendation, recommended_supplier,
	//   suppliers: [{ supplier, score, tier, last_price, lead_time_days, quotation, note }],
	//   excluded: [{ supplier, reason }] }

	// Zero means the agent found no price at all; never show that as a free order.
	const value = (amount) => (Number(amount) ? inr(amount) : __("value unknown"));

	class AgentApprovalsPage extends studio.StudioPage {
		constructor(wrapper) {
			super(wrapper, {
				route: "agent-approvals",
				title: "Approval Inbox",
				eyebrow: "Agent Studio · Step 7",
				intro: "Proposals that need a person's decision. The agent has stopped and is waiting. Nothing has been created in ERPNext yet.",
			});
			this.selected = null;
			this.details = {};
			frappe.realtime.on("agent_run_update", () => {
				clearTimeout(this.pending);
				this.pending = setTimeout(() => document.body.contains(this.root) && this.reload(), 400);
			});
			this.reload();
		}

		async fetch() {
			this.details = {};
			return studio.call("get_approvals");
		}

		render() {
			const { approvals } = this.data;
			if (!approvals.some((a) => a.name === this.selected)) this.selected = approvals[0]?.name;
			if (!approvals.length) {
				return studio.empty("Nothing waiting for a decision.", "When an agent prepares a proposal that needs approval, it appears here.");
			}
			const detail = this.details[this.selected];
			return `
				<div class="as-split-wide">
					<section class="as-panel">
						<h2>${t("Requests")}</h2>
						<div class="as-table-scroll"><table class="as-table">
							<tbody>
								${approvals.map((a) => `
									<tr class="is-selectable ${a.name === this.selected ? "is-selected" : ""}" data-name="${escape(a.name)}">
										<td><strong>${escape(a.name)}</strong><div class="as-muted">${escape(a.action || "")} · ${value(a.estimated_value)}</div><div class="as-muted">${escape(a.requested_by || "")} · ${studio.datetime(a.creation)}</div></td>
										<td>${badge(a.status)}</td>
									</tr>`).join("")}
							</tbody>
						</table></div>
					</section>
					${detail ? this.renderDetail(detail) : `<section class="as-panel">${studio.empty("Loading…")}</section>`}
				</div>`;
		}

		renderDetail(a) {
			const p = a.proposal || {};
			const uom = escape(p.uom || "");
			const openOrders = p.open_orders || [];
			return `
				<section class="as-panel">
					<div class="as-panel-head">
						<div>
							<h2>${escape(a.action || t("Proposal"))}${p.item_name ? `: ${escape(p.shortage_qty)} ${uom} ${escape(p.item_name)}` : ""}</h2>
							<p class="as-muted" style="margin:0">${escape(a.name)} · ${t("from")} <a href="#" class="as-open-run">${escape(a.run)}</a> · ${t("requested by")} ${escape(a.requested_by || "")}</p>
						</div>
						${badge(a.status)}
					</div>

					${p.item_code ? `
						<h3>${t("Evidence from ERPNext")}</h3>
						<div class="as-evidence">
							<div><span>${t("Required")}</span><strong>${escape(p.required_qty)} ${uom}</strong></div>
							<div><span>${t("In stock")} (${escape(p.warehouse)})</span><strong>${escape(p.stock_qty)} ${uom}</strong></div>
							<div><span>${t("Usable open orders")}</span><strong>${escape(p.usable_open_qty)} ${uom}</strong></div>
							<div><span>${t("Net shortage")}</span><strong>${escape(p.shortage_qty)} ${uom}</strong></div>
						</div>
						<div class="as-callout">
							<strong>${t("Calculation (done by code, not the LLM)")}:</strong>
							${escape(p.required_qty)} ${t("required")} − ${escape(p.stock_qty)} ${t("in stock")} − ${escape(p.usable_open_qty)} ${t("arriving before")} ${escape(p.need_by)}
							${openOrders.length ? `(${openOrders.map((o) => `${escape(o.name)}: ${escape(o.pending_qty)} ${t("on")} ${escape(o.schedule_date)}`).join(", ")})` : ""}
							= <strong>${escape(p.shortage_qty)} ${uom}</strong>
						</div>` : ""}

					${p.recommendation || a.summary ? `<h3>${t("Agent recommendation")}</h3><p>${escape(p.recommendation || a.summary)}</p>` : ""}
					${(p.suppliers || []).length ? `
						<div class="as-table-scroll"><table class="as-table">
							<thead><tr><th>${t("Supplier")}</th><th>${t("Score")}</th><th>${t("Last price")}</th><th>${t("Lead time")}</th><th>${t("Open quotation")}</th><th>${t("Note")}</th></tr></thead>
							<tbody>
								${p.suppliers.map((x) => `<tr>
									<td><strong>${escape(x.supplier)}</strong> ${x.supplier === p.recommended_supplier ? badge("Recommended") : ""}</td>
									<td>${escape(x.score ?? "—")} ${x.tier ? badge(x.tier) : ""}</td>
									<td>${x.last_price ? inr(x.last_price) : "—"}</td>
									<td>${x.lead_time_days ? `${escape(x.lead_time_days)} ${t("days")}` : "—"}</td>
									<td>${escape(x.quotation || "—")}</td>
									<td>${escape(x.note || "")}</td>
								</tr>`).join("")}
							</tbody>
						</table></div>` : ""}
					${(p.excluded || []).length ? `<p class="as-muted" style="margin-top:8px">${t("Excluded")}: ${p.excluded.map((x) => `${escape(x.supplier)} (${escape(x.reason)})`).join("; ")}</p>` : ""}

					${a.policy_results.length ? `
						<h3 style="margin-top:14px">${t("Policy checks")}</h3>
						<div class="as-table-scroll"><table class="as-table"><tbody>
							${a.policy_results.map((c) => `<tr><td style="width:80px">${badge(c.result)}</td><td>${t(c.rule)}<div class="as-muted">${escape(c.detail)}</div></td></tr>`).join("")}
						</tbody></table></div>` : ""}

					<h3 style="margin-top:14px">${t("Decision")}</h3>
					<div class="as-decision">
						<p class="as-muted" style="margin:0">${Number(a.estimated_value) ? `${t("Estimated value")} ${inr(a.estimated_value)}` : t("Value unknown")} · ${t("Risk")}: ${a.risk ? badge(a.risk) : "—"}</p>
						<div class="as-table-scroll"><table class="as-table"><tbody>
							${a.required_roles.map((role) => {
								const by = a.covered[role];
								return `<tr><td style="width:40%">${escape(role)}</td><td>${by ? `${badge("Approved")} ${escape(by)}` : a.status === "Pending" ? badge("Pending") : "—"}</td></tr>`;
							}).join("")}
						</tbody></table></div>
						${a.decisions.length ? `<ul class="as-muted" style="padding-left:18px;margin:0">${a.decisions.map((d) => `<li>${escape(d.decision)} · ${escape(d.approver)}${d.role ? ` (${escape(d.role)})` : ""} · ${studio.datetime(d.at)}${d.note ? ` · ${escape(d.note)}` : ""}</li>`).join("")}</ul>` : ""}
						${a.status === "Pending" ? (a.blockers.length
							? `<p class="as-muted" style="margin:0"><i class="fa fa-lock" aria-hidden="true"></i> ${escape(a.blockers.join(" "))}</p>`
							: `<textarea class="form-control as-comment" placeholder="${t("Comment (required to reject)")}"></textarea>
								<div class="as-actions">
									<button type="button" class="btn btn-primary btn-sm as-decide" data-decision="approve">${t("Approve")}</button>
									<button type="button" class="btn btn-danger btn-sm as-decide" data-decision="reject">${t("Reject")}</button>
								</div>
								<p class="as-muted" style="margin:0">${t("On approval, the server re-checks the approvers, current stock and open orders, then the agent creates the RFQ as a Draft. Sending it to suppliers stays a separate, manual step.")}</p>`)
						: `<p style="margin:0">${badge(a.status)} ${a.decided_by ? `${t("by")} ${escape(a.decided_by)} · ${studio.datetime(a.decided_at)}` : ""}${a.decision_note ? `<br><span class="as-muted">${escape(a.decision_note)}</span>` : ""}</p>
							${a.created_docname ? `<p style="margin:0">${t("Created")}: <a href="/app/${frappe.router.slug(a.created_doctype)}/${encodeURIComponent(a.created_docname)}">${escape(a.created_docname)}</a> (${t("Draft")})</p>` : ""}`}
					</div>
				</section>`;
		}

		async loadDetail(name) {
			if (!name || this.details[name]) return;
			this.details[name] = await studio.call("get_approval", { name });
			if (this.selected === name) this.refresh();
		}

		bind(body) {
			this.loadDetail(this.selected);
			body.querySelectorAll("tr[data-name]").forEach((row) =>
				row.addEventListener("click", () => {
					this.selected = row.dataset.name;
					this.refresh();
				})
			);
			body.querySelectorAll(".as-decide").forEach((button) =>
				button.addEventListener("click", async () => {
					const decision = button.dataset.decision;
					const note = body.querySelector(".as-comment").value.trim();
					if (decision === "reject" && !note) {
						this.notify("Please add a comment explaining why you are rejecting.", "red");
						return;
					}
					body.querySelectorAll(".as-decide").forEach((b) => (b.disabled = true));
					try {
						const r = await frappe.xcall("pridict.agent_studio.approvals.decide", { approval: this.selected, decision, note });
						this.notify(
							r.status === "Pending" ? `Recorded. Still waiting for: ${r.remaining.join(", ")}` : `${r.status}. The agent is resuming the run.`,
							r.status === "Rejected" ? "orange" : "green"
						);
					} finally {
						this.reload();
					}
				})
			);
			body.querySelector(".as-open-run")?.addEventListener("click", (event) => {
				event.preventDefault();
				frappe.set_route("agent-runs");
			});
		}
	}

	wrapper.agent_studio = new AgentApprovalsPage(wrapper);
};
