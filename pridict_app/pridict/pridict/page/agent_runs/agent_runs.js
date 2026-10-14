frappe.pages["agent-runs"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/sample_data.js",
		"/assets/pridict/js/agent_studio/common.js",
	]);
	const studio = window.pridict.agentStudio;
	const { t, escape, badge, kindBadge } = studio;

	class AgentRunsPage extends studio.StudioPage {
		constructor(wrapper) {
			super(wrapper, {
				route: "agent-runs",
				title: "Runs & Traces",
				eyebrow: "Agent Studio · Step 6",
				intro: "Every time an agent works, it creates a run. The trace records each step, what went in, what came out, how long it took and what it cost, so anyone can see why the agent did what it did.",
			});
			this.selected = this.data.runs[0].name;
			this.tab = "trace";
			this.refresh();
		}

		render() {
			const runs = this.data.runs;
			const run = runs.find((r) => r.name === this.selected);
			const done = runs.filter((r) => ["Completed", "Rejected"].includes(r.status)).length;
			const evals = this.data.evaluations;
			return `
				<div class="as-metrics">
					${studio.metric("Runs (7 days)", runs.length)}
					${studio.metric("Finished cleanly", `${Math.round((done / runs.length) * 100)}%`, t("Completed or rejected by a human"))}
					${studio.metric("Waiting on people", runs.filter((r) => r.status.startsWith("Awaiting") || r.status.startsWith("Waiting")).length)}
					${studio.metric("Avg cost / run", `$${(runs.reduce((s, r) => s + r.cost_usd, 0) / runs.length).toFixed(3)}`)}
					${studio.metric("Evaluation", `${evals.filter((e) => e.result === "PASS").length}/${evals.length}`, t("Test scenarios passing"))}
				</div>

				<section class="as-panel">
					<div class="as-panel-head"><h2>${t("Recent runs")}</h2></div>
					<div class="as-table-scroll">
						<table class="as-table">
							<thead><tr><th>${t("Run")}</th><th>${t("Started")}</th><th>${t("User")}</th><th>${t("Duration")}</th><th>${t("Tokens")}</th><th>${t("Cost")}</th><th>${t("Status")}</th><th>${t("Outcome")}</th></tr></thead>
							<tbody>
								${runs.map((r) => `
									<tr class="is-selectable ${r.name === this.selected ? "is-selected" : ""}" data-name="${escape(r.name)}">
										<td><strong>${escape(r.name)}</strong><div class="as-muted">${escape(r.workflow)}</div></td>
										<td>${escape(r.started)}</td>
										<td>${escape(r.user)}</td>
										<td>${r.duration_s}s</td>
										<td>${r.tokens.toLocaleString()}</td>
										<td>$${r.cost_usd.toFixed(3)}</td>
										<td>${badge(r.status)}</td>
										<td>${escape(r.outcome)}</td>
									</tr>`).join("")}
							</tbody>
						</table>
					</div>
				</section>

				<nav class="as-subnav" aria-label="${t("Run details")}">
					<button type="button" class="as-subnav-link as-tab ${this.tab === "trace" ? "is-active" : ""}" data-tab="trace">${t("Trace")}: ${escape(run.name)}</button>
					<button type="button" class="as-subnav-link as-tab ${this.tab === "evals" ? "is-active" : ""}" data-tab="evals">${t("Evaluation suite")}</button>
				</nav>
				${this.tab === "trace" ? this.renderTrace(run) : this.renderEvals()}`;
		}

		renderTrace(run) {
			// Only the headline run has a recorded sample trace.
			const steps = run.name === this.data.runs[0].name ? this.data.trace : [];
			return `
				<section class="as-panel">
					<div class="as-panel-head">
						<div><h2>${escape(run.name)} ${badge(run.status)}</h2><p class="as-muted" style="margin:0">${escape(this.data.scenario.request)}</p></div>
						<div class="as-actions">
							<button type="button" class="btn btn-default btn-sm as-control" data-action="Pause">${t("Pause")}</button>
							<button type="button" class="btn btn-default btn-sm as-control" data-action="Resume">${t("Resume")}</button>
							<button type="button" class="btn btn-danger btn-sm as-control" data-action="Terminate">${t("Terminate")}</button>
						</div>
					</div>
					${steps.length ? `
						<ol class="as-timeline">
							${steps.map((s) => `
								<li>
									<span class="as-dot as-dot-${s.kind}"></span>
									<div class="as-trace-row">
										<div class="as-trace-meta"><strong>${escape(s.node)}</strong> ${kindBadge(s.kind)} <span>${s.ms} ms</span>${s.tokens ? `<span>${s.tokens.toLocaleString()} ${t("tokens")}</span>` : ""}</div>
										<div class="as-trace-summary">${escape(s.summary)}</div>
									</div>
								</li>`).join("")}
						</ol>
						${run.status === "Awaiting approval" ? `<div class="as-callout" style="margin-top:14px">${t("Paused at human_review. The full state is saved in a checkpoint, so the server can restart and the run will still resume correctly after approval.")} <a href="#" class="as-open-approval">${t("Open in Approval Inbox")}</a></div>` : ""}
					` : `<p class="as-muted">${t("Sample trace is only recorded for")} ${escape(this.data.runs[0].name)}.</p>`}
				</section>`;
		}

		renderEvals() {
			return `
				<section class="as-panel">
					<div class="as-panel-head">
						<h2>${t("Evaluation suite: Procurement Sourcing v1.2")}</h2>
						<button type="button" class="btn btn-default btn-sm as-control" data-action="Re-run suite">${t("Re-run suite")}</button>
					</div>
					<p class="as-muted">${t("Fixed test scenarios run against seeded test data before each new version is published. A failing case blocks publishing.")}</p>
					<div class="as-table-scroll"><table class="as-table">
						<thead><tr><th>${t("Scenario")}</th><th>${t("Expected behaviour")}</th><th>${t("Result")}</th></tr></thead>
						<tbody>
							${this.data.evaluations.map((e) => `<tr><td><strong>${escape(e.case)}</strong></td><td>${escape(e.expected)}${e.note ? `<div class="as-muted">${escape(e.note)}</div>` : ""}</td><td>${badge(e.result)}</td></tr>`).join("")}
						</tbody>
					</table></div>
				</section>`;
		}

		bind(body) {
			body.querySelectorAll("tr[data-name]").forEach((row) =>
				row.addEventListener("click", () => {
					this.selected = row.dataset.name;
					this.tab = "trace";
					this.refresh();
				})
			);
			body.querySelectorAll(".as-tab").forEach((button) =>
				button.addEventListener("click", () => {
					this.tab = button.dataset.tab;
					this.refresh();
				})
			);
			body.querySelectorAll(".as-control").forEach((button) =>
				button.addEventListener("click", () => this.notify(`Sample mode: "${button.dataset.action}" will call the LangGraph runtime once it exists.`, "orange"))
			);
			body.querySelector(".as-open-approval")?.addEventListener("click", (event) => {
				event.preventDefault();
				frappe.set_route("agent-approvals");
			});
		}
	}

	wrapper.agent_studio = new AgentRunsPage(wrapper);
};
