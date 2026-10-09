frappe.pages["decision-intelligence"].on_page_load = async (wrapper) => {
	await frappe.require("/assets/pridict/css/decision_intelligence.css");
	wrapper.decision_intelligence = new ProcurementDecisionIntelligence(wrapper);
};

class ProcurementDecisionIntelligence {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Decision Intelligence"),
			single_column: true,
		});
		this.$root = $('<div class="di-screen"></div>').appendTo(this.page.main.empty());
		this.activeTab = "audit";
		this.data = null;
		this.loadOptions();
	}

	escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}

	text(value) {
		return this.escape(__(value));
	}

	formatCurrency(value, currency = "INR") {
		const num = Number(value || 0);
		const curr = (typeof currency === "string" && currency.length === 3) ? currency.toUpperCase() : "INR";
		try {
			return new Intl.NumberFormat(frappe.boot?.sysdefaults?.number_format || "en-IN", {
				style: "currency",
				currency: curr,
				maximumFractionDigits: 0,
			}).format(num);
		} catch (_) {
			return `${curr} ${num.toLocaleString()}`;
		}
	}

	async loadOptions() {
		this.$root.html(`<p role="status">${this.text("Loading decision intelligence options…")}</p>`);
		try {
			this.options = await frappe.xcall("pridict.decision_intelligence.screen.get_options");
			if (!this.options.companies || !this.options.companies.length) {
				this.$root.html(`
					<section class="di-panel" role="status">
						<h2>${this.text("No company access")}</h2>
						<p>${this.text("Ask your administrator for company and purchase order read permissions.")}</p>
					</section>
				`);
				return;
			}
			this.build();
		} catch (err) {
			this.$root.html(`
				<section class="di-panel" role="alert">
					<h2>${this.text("Decision Intelligence is unavailable")}</h2>
					<p>${this.text("Sign in with Purchase Manager, Process Analyst, or System Manager role.")}</p>
					<button class="btn btn-default di-retry">${this.text("Retry")}</button>
				</section>
			`);
			this.$root.find(".di-retry").on("click", () => this.loadOptions());
		}
	}

	build() {
		const company = this.options.companies.includes(this.options.default_company)
			? this.options.default_company
			: this.options.companies[0];

		this.$root.html(`
			<header class="di-intro">
				<div>
					<span class="di-eyebrow">${this.text("Procurement Governance & Analytics")}</span>
					<h1>${this.text("Decision Intelligence")}</h1>
					<p>${this.text("Audit approval compliance, identify spend & price anomalies, and act on prescriptive recommendations.")}</p>
				</div>
				<div class="di-header-actions">
					<a href="/app/process-intelligence" class="btn btn-default btn-sm di-cross-nav">
						<i class="fa fa-sitemap mr-1"></i> ${this.text("Process Intelligence")}
					</a>
					<span class="di-badge di-badge-standard">${this.text("Real-Time Audit")}</span>
				</div>
			</header>

			<form class="di-panel di-filters" aria-label="${this.text("Evaluation scope")}">
				<label>${this.text("Company")}
					<select name="company" required class="form-control">
						${this.options.companies.map((name) => `<option ${name === company ? "selected" : ""} value="${this.escape(name)}">${this.escape(name)}</option>`).join("")}
					</select>
				</label>
				<label>${this.text("Start Date")}
					<input name="start_date" type="date" required class="form-control" value="${this.escape(this.options.start_date || "")}">
				</label>
				<label>${this.text("End Date")}
					<input name="end_date" type="date" required class="form-control" value="${this.escape(this.options.today || "")}">
				</label>
				<button class="btn btn-primary" type="submit">${this.text("Evaluate Decisions")}</button>
				<p class="di-filter-note">
					${this.text("Evaluates purchase orders, approval tiers, cost center accountability, price variances, and vendor performance.")}
				</p>
			</form>

			<div class="di-results" aria-live="polite"></div>
		`);

		this.$results = this.$root.find(".di-results");
		this.$root.find("form").on("submit", (event) => {
			event.preventDefault();
			this.evaluate();
		});

		// Auto run on initial load
		this.evaluate();
	}

	async evaluate() {
		const form = this.$root.find("form")[0];
		if (!form || !form.reportValidity()) return;

		const args = Object.fromEntries(new FormData(form));
		if (args.start_date > args.end_date) {
			this.$results.html(`<div class="di-panel text-danger">${this.text("Start Date must be before or equal to End Date.")}</div>`);
			return;
		}

		this.$root.find("form :input").prop("disabled", true);
		this.$results.html(`
			<section class="di-panel di-empty" role="status">
				<h2>${this.text("Evaluating procurement decisions & risk patterns…")}</h2>
				<p>${this.text("Analyzing approval tiers, unit price benchmarks, split order patterns, and vendor scores.")}</p>
			</section>
		`);

		try {
			const data = await frappe.xcall("pridict.decision_intelligence.screen.get_decision_analysis", args);
			this.data = data;
			this.render();
		} catch (err) {
			this.$results.html(`
				<section class="di-panel" role="alert">
					<h2>${this.text("Evaluation could not be completed")}</h2>
					<p>${this.escape(err?.message || this.text("An error occurred during decision analysis."))}</p>
				</section>
			`);
		} finally {
			this.$root.find("form :input").prop("disabled", false);
		}
	}

	render() {
		if (!this.data) return;
		const s = this.data.summary;
		const currency = this.data.evaluated_decisions[0]?.currency || "INR";

		const complianceBadgeClass = s.compliance_rate_pct >= 90 ? "di-badge-compliant" : s.compliance_rate_pct >= 75 ? "di-badge-warning" : "di-badge-breach";

		this.$results.html(`
			<!-- Executive Scorecard -->
			<div class="di-metrics">
				<div class="di-metric-card">
					<span class="di-metric-title">${this.text("Compliance Rate")}</span>
					<div class="d-flex align-items-baseline gap-2">
						<span class="di-metric-value">${s.compliance_rate_pct}%</span>
						<span class="di-badge ${complianceBadgeClass}">${s.breach_count > 0 ? this.text("Breaches Found") : this.text("Optimal")}</span>
					</div>
					<span class="di-metric-sub">${s.compliant_count} ${this.text("compliant out of")} ${s.total_decisions_evaluated} ${this.text("orders")}</span>
				</div>

				<div class="di-metric-card">
					<span class="di-metric-title">${this.text("Active Risk Signals")}</span>
					<div class="d-flex align-items-baseline gap-2">
						<span class="di-metric-value">${s.total_anomalies_count}</span>
						<span class="di-badge di-badge-warning">${this.text("Anomalies")}</span>
					</div>
					<span class="di-metric-sub">${this.text("Price spikes, split POs, & maverick spend")}</span>
				</div>

				<div class="di-metric-card">
					<span class="di-metric-title">${this.text("Spend at Risk")}</span>
					<span class="di-metric-value">${this.formatCurrency(s.total_spend_at_risk, currency)}</span>
					<span class="di-metric-sub">${this.text("Total evaluated:")} ${this.formatCurrency(s.total_spend_evaluated, currency)}</span>
				</div>

				<div class="di-metric-card">
					<span class="di-metric-title">${this.text("Identified Savings")}</span>
					<span class="di-metric-value text-success">${this.formatCurrency(s.potential_savings_total, currency)}</span>
					<span class="di-metric-sub">${s.active_recommendations_count} ${this.text("actionable recommendations")}</span>
				</div>
			</div>

			<!-- Tab Navigation -->
			<nav class="di-tabs-nav" role="tablist">
				<button class="di-tab-btn ${this.activeTab === "audit" ? "is-active" : ""}" data-tab="audit">
					<i class="fa fa-gavel mr-1"></i> ${this.text("Decision Audit")} (${this.data.evaluated_decisions.length})
				</button>
				<button class="di-tab-btn ${this.activeTab === "anomalies" ? "is-active" : ""}" data-tab="anomalies">
					<i class="fa fa-exclamation-triangle mr-1"></i> ${this.text("Spend Anomalies")} (${this.data.anomalies.length})
				</button>
				<button class="di-tab-btn ${this.activeTab === "vendors" ? "is-active" : ""}" data-tab="vendors">
					<i class="fa fa-building mr-1"></i> ${this.text("Vendor Scorecard")} (${this.data.vendor_scores.length})
				</button>
				<button class="di-tab-btn ${this.activeTab === "recommendations" ? "is-active" : ""}" data-tab="recommendations">
					<i class="fa fa-lightbulb-o mr-1"></i> ${this.text("Recommendations")} (${this.data.recommendations.length})
				</button>
				<button class="di-tab-btn ${this.activeTab === "rules" ? "is-active" : ""}" data-tab="rules">
					<i class="fa fa-sliders mr-1"></i> ${this.text("Configured Rules")} (${this.options.rules?.length || 6})
				</button>
			</nav>

			<!-- Tab Content -->
			<div class="di-tab-content">
				${this.renderActiveTabContent(currency)}
			</div>
		`);

		this.$results.find(".di-tab-btn").on("click", (e) => {
			const target = $(e.currentTarget).data("tab");
			if (target) {
				this.activeTab = target;
				this.render();
			}
		});
	}

	renderActiveTabContent(currency) {
		switch (this.activeTab) {
			case "audit":
				return this.renderAuditTab(currency);
			case "anomalies":
				return this.renderAnomaliesTab(currency);
			case "vendors":
				return this.renderVendorsTab(currency);
			case "recommendations":
				return this.renderRecommendationsTab(currency);
			case "rules":
				return this.renderRulesTab();
			default:
				return "";
		}
	}

	renderAuditTab(currency) {
		const decisions = this.data.evaluated_decisions;
		if (!decisions.length) {
			return `<div class="di-panel di-empty"><p>${this.text("No purchase orders found within the selected dates.")}</p></div>`;
		}

		return `
			<div class="di-panel di-table-scroll">
				<table class="di-table">
					<thead>
						<tr>
							<th>${this.text("Document")}</th>
							<th>${this.text("Date")}</th>
							<th>${this.text("Order Value")}</th>
							<th>${this.text("Decision Status")}</th>
							<th>${this.text("Approver / Owner")}</th>
							<th>${this.text("Rule Evaluations & Rationale")}</th>
						</tr>
					</thead>
					<tbody>
						${decisions.map((d) => {
							const badgeClass = d.status === "COMPLIANT" ? "di-badge-compliant" : d.status === "WARNING" ? "di-badge-warning" : "di-badge-breach";
							return `
								<tr>
									<td><a href="${this.escape(d.doc_url)}" target="_blank">${this.escape(d.doc_name)}</a></td>
									<td>${this.escape(d.creation)}</td>
									<td><strong>${this.formatCurrency(d.total_amount, currency)}</strong></td>
									<td><span class="di-badge ${badgeClass}">${this.escape(d.status)}</span></td>
									<td>${this.escape(d.approver || d.owner)}</td>
									<td>
										<ul class="list-unstyled mb-0" style="font-size: 11px;">
											${d.evaluations.map((ev) => `
												<li class="mb-1">
													<strong class="${ev.status === "BREACH" ? "text-danger" : ev.status === "WARNING" ? "text-warning" : "text-success"}">• ${this.escape(ev.rule_name)}:</strong>
													${this.escape(ev.message)}
												</li>
											`).join("")}
										</ul>
									</td>
								</tr>
							`;
						}).join("")}
					</tbody>
				</table>
			</div>
		`;
	}

	renderAnomaliesTab(currency) {
		const anomalies = this.data.anomalies;
		if (!anomalies.length) {
			return `
				<div class="di-panel di-empty text-success">
					<i class="fa fa-check-circle fa-2x mb-2"></i>
					<h3>${this.text("Zero Critical Anomalies Detected")}</h3>
					<p>${this.text("No price outliers, split circumventions, or maverick spend found within the evaluated scope.")}</p>
				</div>
			`;
		}

		return `
			<div class="di-anomaly-grid">
				${anomalies.map((a) => {
					const badgeClass = a.severity === "HIGH" ? "di-badge-high" : a.severity === "MEDIUM" ? "di-badge-warning" : "di-badge-standard";
					return `
						<div class="di-anomaly-card">
							<div class="di-anomaly-header">
								<div>
									<span class="di-badge ${badgeClass} mb-1">${this.escape(a.severity)} SEVERITY</span>
									<h4 class="di-anomaly-title">${this.escape(a.title)}</h4>
								</div>
								${a.potential_impact > 0 ? `<strong class="text-danger">${this.formatCurrency(a.potential_impact, currency)}</strong>` : ""}
							</div>
							<p class="di-anomaly-body">${this.escape(a.description)}</p>
							<div class="di-anomaly-footer">
								<span class="text-muted"><i class="fa fa-user-circle mr-1"></i> ${this.escape(a.party_name || "Internal")}</span>
								<a href="${this.escape(a.doc_url)}" target="_blank" class="btn btn-xs btn-default">
									${this.text("View Document")} <i class="fa fa-arrow-right ml-1"></i>
								</a>
							</div>
						</div>
					`;
				}).join("")}
			</div>
		`;
	}

	renderVendorsTab(currency) {
		const scores = this.data.vendor_scores;
		if (!scores.length) {
			return `<div class="di-panel di-empty"><p>${this.text("No vendor transactions to score in this period.")}</p></div>`;
		}

		return `
			<div class="di-panel di-table-scroll">
				<table class="di-table">
					<thead>
						<tr>
							<th>${this.text("Vendor Name")}</th>
							<th>${this.text("Total Spend")}</th>
							<th>${this.text("Orders")}</th>
							<th>${this.text("On-Time %")}</th>
							<th>${this.text("Quality %")}</th>
							<th>${this.text("Score")}</th>
							<th>${this.text("Decision Tier")}</th>
							<th>${this.text("Observations")}</th>
						</tr>
					</thead>
					<tbody>
						${scores.map((v) => {
							const tierBadge = v.tier === "PREFERRED" ? "di-badge-preferred" : v.tier === "STANDARD" ? "di-badge-standard" : v.tier === "WATCHLIST" ? "di-badge-watchlist" : "di-badge-breach";
							return `
								<tr>
									<td><strong><a href="/app/supplier/${encodeURIComponent(v.vendor_name)}" target="_blank">${this.escape(v.vendor_name)}</a></strong></td>
									<td>${this.formatCurrency(v.total_spend, currency)}</td>
									<td>${v.order_count}</td>
									<td>${v.on_time_delivery_rate}%</td>
									<td>${v.quality_acceptance_rate}%</td>
									<td><strong>${v.overall_score}</strong> / 100</td>
									<td><span class="di-badge ${tierBadge}">${this.escape(v.tier)}</span></td>
									<td>
										${v.key_strengths.map((s) => `<span class="badge badge-success mr-1">${this.escape(s)}</span>`).join("")}
										${v.risk_flags.map((f) => `<span class="badge badge-warning mr-1">${this.escape(f)}</span>`).join("")}
									</td>
								</tr>
							`;
						}).join("")}
					</tbody>
				</table>
			</div>
		`;
	}

	renderRecommendationsTab(currency) {
		const recs = this.data.recommendations;
		if (!recs.length) {
			return `
				<div class="di-panel di-empty text-success">
					<i class="fa fa-thumbs-up fa-2x mb-2"></i>
					<h3>${this.text("Procurement Operations are Fully Optimized")}</h3>
					<p>${this.text("All evaluated purchasing practices meet policy standards.")}</p>
				</div>
			`;
		}

		return `
			<div class="di-rec-grid">
				${recs.map((r) => {
					return `
						<div class="di-rec-card priority-${this.escape(r.priority)}">
							<div class="di-rec-header">
								<div>
									<div class="d-flex align-items-center gap-2 mb-1">
										<span class="badge badge-dark">${this.escape(r.priority)} PRIORITY</span>
										<span class="text-muted" style="font-size: 11px;">${this.escape(r.category)}</span>
									</div>
									<h3 class="di-rec-title">${this.escape(r.title)}</h3>
								</div>
								${r.estimated_saving > 0 ? `
									<div class="text-right">
										<div class="text-success" style="font-size: 18px; font-weight: 750;">+${this.formatCurrency(r.estimated_saving, currency)}</div>
										<span class="text-muted" style="font-size: 11px;">${this.text("Est. Opportunity")}</span>
									</div>
								` : ""}
							</div>
							<p style="font-size: 13px; margin: 0;">${this.escape(r.description)}</p>
							<div class="di-rec-action-box">
								<strong><i class="fa fa-lightbulb-o mr-1"></i> ${this.text("Prescriptive Action")}:</strong> ${this.escape(r.suggested_action)}
							</div>
							<div class="di-rec-footer">
								<span class="text-muted">${this.escape(r.target_doctype)}: <strong>${this.escape(r.target_docname)}</strong></span>
								${r.doc_url ? `
									<a href="${this.escape(r.doc_url)}" target="_blank" class="btn btn-xs btn-primary">
										${this.text("Act on Recommendation")} <i class="fa fa-external-link ml-1"></i>
									</a>
								` : ""}
							</div>
						</div>
					`;
				}).join("")}
			</div>
		`;
	}

	renderRulesTab() {
		const rules = this.options.rules || [];
		return `
			<div class="di-panel di-table-scroll">
				<table class="di-table">
					<thead>
						<tr>
							<th>${this.text("Rule ID")}</th>
							<th>${this.text("Rule Name")}</th>
							<th>${this.text("Category")}</th>
							<th>${this.text("Severity")}</th>
							<th>${this.text("Threshold")}</th>
							<th>${this.text("Description")}</th>
						</tr>
					</thead>
					<tbody>
						${rules.map((r) => `
							<tr>
								<td><code>${this.escape(r.rule_id)}</code></td>
								<td><strong>${this.escape(r.name)}</strong></td>
								<td><span class="badge badge-light">${this.escape(r.category)}</span></td>
								<td><span class="di-badge ${r.severity === "HIGH" ? "di-badge-high" : "di-badge-warning"}">${this.escape(r.severity)}</span></td>
								<td>${r.default_threshold > 0 ? this.escape(r.default_threshold.toLocaleString()) : "Strict Check"}</td>
								<td>${this.escape(r.description)}</td>
							</tr>
						`).join("")}
					</tbody>
				</table>
			</div>
		`;
	}
}
