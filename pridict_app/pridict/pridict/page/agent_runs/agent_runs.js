frappe.pages["agent-runs"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/common.js",
	]);
	const studio = window.pridict.agentStudio;
	const { t, escape, badge, kindBadge } = studio;

	const waiting = (status) => ["Awaiting approval", "Waiting for buyer"].includes(status);
	const finishedStatuses = ["Completed", "Failed", "Rejected", "Cancelled"];
	const runtime = (method, args) => frappe.xcall(`pridict.agent_studio.runtime.${method}`, args);

	class AgentRunsPage extends studio.StudioPage {
		constructor(wrapper) {
			super(wrapper, {
				route: "agent-runs",
				title: "Runs & Traces",
				eyebrow: "Agent Studio · Step 6",
				intro: "Every time an agent works, it creates a run. The trace records each step, what went in, what came out, how long it took and what it cost, so anyone can see why the agent did what it did.",
			});
			this.selected = null;
			this.details = {};
			this.tab = "trace";
			this.draft = "";
			this.answer = "";
			// Runs progress in a background job; the server announces each step.
			frappe.realtime.on("agent_eval_update", () => {
				clearTimeout(this.pending);
				this.pending = setTimeout(() => document.body.contains(this.root) && this.reload(), 400);
			});
			frappe.realtime.on("agent_run_update", () => {
				clearTimeout(this.pending);
				this.pending = setTimeout(() => document.body.contains(this.root) && this.reload(), 400);
			});
			this.reload();
		}

		async fetch() {
			this.details = {};
			return studio.call("get_runs");
		}

		render() {
			const { runs } = this.data;
			if (!runs.some((r) => r.name === this.selected)) this.selected = runs[0]?.name;
			const finished = runs.filter((r) => ["Completed", "Rejected"].includes(r.status)).length;
			const tokens = runs.reduce((s, r) => s + (r.total_tokens || 0), 0);
			return `
				${this.renderStart()}
				<div class="as-metrics">
					${studio.metric("Runs", runs.length, t("Most recent 50"))}
					${studio.metric("Finished cleanly", runs.length ? `${Math.round((finished / runs.length) * 100)}%` : "—", t("Completed or rejected by a human"))}
					${studio.metric("Waiting on people", runs.filter((r) => waiting(r.status)).length)}
					${studio.metric("Avg tokens / run", runs.length ? Math.round(tokens / runs.length).toLocaleString() : "—")}
					${this.evalMetric()}
				</div>

				<section class="as-panel">
					<div class="as-panel-head"><h2>${t("Recent runs")}</h2></div>
					${runs.length ? `
						<div class="as-table-scroll">
							<table class="as-table">
								<thead><tr><th>${t("Run")}</th><th>${t("Started")}</th><th>${t("User")}</th><th>${t("Duration")}</th><th>${t("Tokens")}</th><th>${t("Status")}</th><th>${t("Outcome")}</th></tr></thead>
								<tbody>
									${runs.map((r) => `
										<tr class="is-selectable ${r.name === this.selected ? "is-selected" : ""}" data-name="${escape(r.name)}">
											<td><strong>${escape(r.name)}</strong><div class="as-muted">${escape(r.agent)} ${escape(r.agent_version || "")}</div></td>
											<td>${studio.datetime(r.started_at || r.creation)}</td>
											<td>${escape(r.requested_by || "")}</td>
											<td>${r.duration_s ? `${r.duration_s}s` : "—"}</td>
											<td>${(r.total_tokens || 0).toLocaleString()}</td>
											<td>${badge(r.status)}</td>
											<td>${escape(r.outcome || r.request_summary || "")}</td>
										</tr>`).join("")}
								</tbody>
							</table>
						</div>` : studio.empty("No runs yet.", "A run is recorded each time a buyer asks an agent for help.")}
				</section>

				<nav class="as-subnav" aria-label="${t("Run details")}">
					<button type="button" class="as-subnav-link as-tab ${this.tab === "trace" ? "is-active" : ""}" data-tab="trace">${t("Trace")}${this.selected ? `: ${escape(this.selected)}` : ""}</button>
					<button type="button" class="as-subnav-link as-tab ${this.tab === "evals" ? "is-active" : ""}" data-tab="evals">${t("Evaluation suite")}</button>
				</nav>
				${this.tab === "trace" ? this.renderTrace() : this.renderEvals()}`;
		}

		renderStart() {
			const agents = this.data.agents || [];
			if (!agents.length) return "";
			return `
				<section class="as-panel">
					<div class="as-panel-head">
						<h2>${t("Ask an agent")}</h2>
						<select class="form-control as-agent" style="max-width:320px">
							${agents.map((a) => `<option value="${escape(a.name)}" ${a.name === this.agent ? "selected" : ""}>${escape(a.name)} ${escape(a.version || "")}${a.status !== "Active" ? ` (${__(a.status)})` : ""}</option>`).join("")}
						</select>
					</div>
					<textarea class="form-control as-request" rows="2" placeholder="${t("For example: Source 500 kg of aluminium sheet for Stores - PRD by 30 October.")}">${escape(this.draft)}</textarea>
					<div class="as-actions" style="margin-top:10px">
						<button type="button" class="btn btn-primary btn-sm as-start">${t("Start run")}</button>
						<span class="as-muted">${t("The agent works in the background; this page updates as each step finishes.")}</span>
					</div>
				</section>`;
		}

		renderTrace() {
			if (!this.selected) return `<section class="as-panel">${studio.empty("Select a run to see its trace.")}</section>`;
			const run = this.details[this.selected];
			if (!run) return `<section class="as-panel">${studio.empty("Loading trace…")}</section>`;
			const pending = run.approvals.find((a) => a.status === "Pending");
			return `
				<section class="as-panel">
					<div class="as-panel-head">
						<div><h2>${escape(run.name)} ${badge(run.status)}</h2><p class="as-muted" style="margin:0">${escape(run.request)}</p></div>
						<div class="as-actions">
							${run.can_act && !finishedStatuses.includes(run.status) && run.status !== "Running" ? `<button type="button" class="btn btn-default btn-sm as-cancel">${t("Cancel run")}</button>` : ""}
							${studio.formLink("Open record", "Agent Run", run.name)}
						</div>
					</div>
					${["Queued", "Running"].includes(run.status) ? `<div class="as-callout"><i class="fa fa-spinner fa-spin" aria-hidden="true"></i> ${t(run.status === "Queued" ? "Waiting for a worker to pick up the run…" : "The agent is working…")}</div>` : ""}
					${run.status === "Waiting for buyer" ? `
						<div class="as-decision" style="margin-bottom:14px">
							<strong>${t("The agent needs more information")}</strong>
							<p style="white-space:pre-wrap;margin:0">${escape(run.pending_question || "")}</p>
							${run.can_act ? `
								<textarea class="form-control as-answer" rows="2" placeholder="${t("Your answer")}">${escape(this.answer)}</textarea>
								<div class="as-actions"><button type="button" class="btn btn-primary btn-sm as-send-answer">${t("Send answer")}</button></div>`
							: `<p class="as-muted" style="margin:0">${t("Only the person who started the run can answer.")}</p>`}
						</div>` : ""}
					${run.outcome && finishedStatuses.includes(run.status) ? `<div class="as-callout"><strong>${t("Outcome")}:</strong> ${escape(run.outcome)}</div>` : ""}
					${run.result?.explanation ? `<p>${escape(run.result.explanation)}</p>` : ""}
					${run.error ? `<div class="as-callout" style="border-left-color:#dc2626">${escape(run.error)}</div>` : ""}
					${run.steps.length ? `
						<ol class="as-timeline">
							${run.steps.map((s) => `
								<li>
									<span class="as-dot as-dot-${escape(s.kind)}"></span>
									<div class="as-trace-row">
										<div class="as-trace-meta"><strong>${escape(s.node)}</strong> ${kindBadge(s.kind)} ${s.status !== "Completed" ? badge(s.status) : ""} <span>${s.ms || 0} ms</span>${s.tokens ? `<span>${s.tokens.toLocaleString()} ${t("tokens")}</span>` : ""}</div>
										<div class="as-trace-summary">${escape(s.summary || "")}</div>
									</div>
								</li>`).join("")}
						</ol>` : `<p class="as-muted">${t("No steps recorded yet.")}</p>`}
					${pending ? `<div class="as-callout" style="margin-top:14px">${t("Paused at human review. The full state is saved in a checkpoint, so the run resumes correctly after approval even if the server restarts.")} <a href="#" class="as-open-approval">${t("Open in Approval Inbox")}</a></div>` : ""}
				</section>`;
		}

		evalMetric() {
			const e = this.data.evaluation;
			if (!e) return studio.metric("Evaluation", "—", t("Suite not run yet"));
			if (["Queued", "Running"].includes(e.status)) return studio.metric("Evaluation", `${e.results.length}/${this.data.scenarios.length}`, t("Running…"));
			return studio.metric("Evaluation", e.total ? `${e.passed}/${e.total}` : "—", `${t(e.mode)} · ${escape(e.agent_version)}`);
		}

		renderEvals() {
			const e = this.data.evaluation;
			const byCase = Object.fromEntries((e?.results || []).map((r) => [r.case, r]));
			const running = e && ["Queued", "Running"].includes(e.status);
			return `
				<section class="as-panel">
					<div class="as-panel-head">
						<h2>${t("Evaluation suite: Procurement Sourcing")}</h2>
						${this.data.can_evaluate ? `<div class="as-actions">
							<button type="button" class="btn btn-default btn-sm as-eval" data-mode="Offline" ${running ? "disabled" : ""}>${t("Run offline check")}</button>
							<button type="button" class="btn btn-primary btn-sm as-eval" data-mode="Live" ${running ? "disabled" : ""}>${t("Run with live model")}</button>
						</div>` : ""}
					</div>
					<p class="as-muted">${t("Each scenario builds its own temporary items, suppliers, stock and purchase orders, runs the agent end to end, checks the result, and then rolls everything back. Live mode uses the agent's model and is required before an agent version can be activated; offline mode uses a scripted model to check the code paths.")}</p>
					${e ? `<p class="as-muted">${escape(e.name)} · ${t(e.mode)} · ${t("version")} ${escape(e.agent_version)} · ${badge(e.status)}${e.ended_at ? ` · ${studio.datetime(e.ended_at)}` : ""}${e.total_tokens ? ` · ${Number(e.total_tokens).toLocaleString()} ${t("tokens")}` : ""}</p>` : ""}
					${e?.error ? `<div class="as-callout" style="border-left-color:#dc2626">${escape(e.error)}</div>` : ""}
					<div class="as-table-scroll"><table class="as-table">
						<thead><tr><th>${t("Scenario")}</th><th>${t("Expected behaviour")}</th><th>${t("What happened")}</th><th>${t("Result")}</th></tr></thead>
						<tbody>
							${this.data.scenarios.map((sc) => {
								const r = byCase[sc.case];
								return `<tr>
									<td><strong>${t(sc.case)}</strong></td>
									<td>${t(sc.expected)}</td>
									<td>${r ? `${escape(r.outcome || r.run_status || "")}${r.note ? `<div class="as-text-bad">${escape(r.note)}</div>` : ""}<div class="as-muted">${r.llm_calls ?? 0} ${t("LLM calls")} · ${r.seconds}s</div>` : `<span class="as-muted">${running ? t("Waiting…") : "—"}</span>`}</td>
									<td>${badge(r ? r.result : "Not run")}</td>
								</tr>`;
							}).join("")}
						</tbody>
					</table></div>
				</section>`;
		}

		async loadDetail(name) {
			if (!name || this.details[name]) return;
			this.details[name] = await studio.call("get_run", { name });
			if (this.selected === name) this.refresh();
		}

		bind(body) {
			if (this.tab === "trace") this.loadDetail(this.selected);
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
			body.querySelector(".as-request")?.addEventListener("input", (e) => (this.draft = e.target.value));
			body.querySelector(".as-answer")?.addEventListener("input", (e) => (this.answer = e.target.value));
			body.querySelector(".as-agent")?.addEventListener("change", (e) => (this.agent = e.target.value));
			body.querySelector(".as-start")?.addEventListener("click", async (event) => {
				event.currentTarget.disabled = true;
				try {
					const { run } = await runtime("start_run", { agent: body.querySelector(".as-agent").value, request: this.draft });
					this.draft = "";
					this.selected = run;
					this.tab = "trace";
					this.notify(`Started ${run}`, "green");
				} finally {
					this.reload();
				}
			});
			body.querySelector(".as-send-answer")?.addEventListener("click", async (event) => {
				event.currentTarget.disabled = true;
				try {
					await runtime("answer_run", { run: this.selected, answer: this.answer });
					this.answer = "";
				} finally {
					this.reload();
				}
			});
			body.querySelector(".as-cancel")?.addEventListener("click", () =>
				frappe.confirm(__("Cancel this run? Any pending approval will expire."), async () => {
					await runtime("cancel_run", { run: this.selected });
					this.reload();
				})
			);
			body.querySelectorAll(".as-eval").forEach((button) =>
				button.addEventListener("click", async () => {
					button.disabled = true;
					try {
						await frappe.xcall("pridict.agent_studio.evals.start_evaluation", { mode: button.dataset.mode });
						this.notify(`Evaluation started (${button.dataset.mode}). Results appear here as each scenario finishes.`, "blue");
					} finally {
						this.reload();
					}
				})
			);
			body.querySelector(".as-open-approval")?.addEventListener("click", (event) => {
				event.preventDefault();
				frappe.set_route("agent-approvals");
			});
		}
	}

	wrapper.agent_studio = new AgentRunsPage(wrapper);
};
