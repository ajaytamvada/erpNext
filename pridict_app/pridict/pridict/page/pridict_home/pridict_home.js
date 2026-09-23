frappe.pages["pridict-home"].on_page_load = (wrapper) => {
	frappe.pridict_home = new PridictExecutiveHome(wrapper);
};

frappe.pages["pridict-home"].on_page_show = () => {
	frappe.pridict_home?.refresh();
};

class PridictExecutiveHome {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Executive Overview"),
			single_column: true,
		});
		this.filters = {
			company: frappe.defaults.get_user_default("Company"),
			from_date: frappe.datetime.add_months(frappe.datetime.get_today(), -5),
			to_date: frappe.datetime.get_today(),
		};
		this.active_task_filter = "all";
		this.build();
	}

	build() {
		$(this.wrapper).addClass("pridict-executive-page");
		$(this.wrapper).find(".page-head").addClass("pridict-executive-page-head");
		this.$root = $('<div class="pridict-executive-home" aria-live="polite"></div>').appendTo(
			this.page.main.empty()
		);
		this.renderLoading();
	}

	async refresh() {
		this.renderLoading();
		try {
			const response = await frappe.xcall(
				"pridict.pridict.page.pridict_home.pridict_home.get_dashboard",
				this.filters
			);
			this.data = response;
			if (response.filters) {
				this.filters = { ...this.filters, ...response.filters };
			}
			this.render();
		} catch (error) {
			this.renderError(error);
		}
	}

	renderLoading() {
		this.$root.html(`
			<div class="pridict-executive-state" role="status">
				<div class="pridict-executive-spinner"></div>
				<strong>${__("Loading executive overview")}</strong>
				<span>${__("Retrieving permitted company data.")}</span>
			</div>
		`);
	}

	renderError() {
		this.$root.html(`
			<div class="pridict-executive-state pridict-executive-state-error" role="alert">
				<strong>${__("Executive overview could not be loaded")}</strong>
				<span>${__("No data was changed. Try again or open the standard workspace.")}</span>
				<div class="pridict-state-actions">
					<button class="btn btn-primary" data-action="retry">${__("Try again")}</button>
					<button class="btn btn-default" data-route="home">${__("Open workspace")}</button>
				</div>
			</div>
		`);
		this.bindNavigation();
	}

	render() {
		if (!this.data.companies?.length) {
			this.$root.html(`
				<div class="pridict-executive-state">
					<strong>${__("No company access")}</strong>
					<span>${frappe.utils.escape_html(this.data.message || __("Ask an administrator for company access."))}</span>
				</div>
			`);
			return;
		}

		this.$root.html(`
			<div class="pridict-executive-layout">
				${this.renderSidebar()}
				<main class="pridict-executive-main">
					${this.renderToolbar()}
					${this.renderHero()}
					${this.renderMetrics()}
					<div class="pridict-dashboard-grid">
						<div class="pridict-dashboard-primary">
							${this.renderTasks()}
							${this.renderTrend()}
						</div>
						<div class="pridict-dashboard-secondary">
							${this.renderBusinessAreas()}
							${this.renderActivity()}
						</div>
					</div>
					<footer class="pridict-executive-footer">
						<span>${__("Values reflect your permitted company and document access.")}</span>
						<button class="btn btn-link" data-route="home">${__("Open standard workspace")}</button>
					</footer>
				</main>
			</div>
		`);
		this.bindControls();
		this.applyTaskFilter();
	}

	renderSidebar() {
		const routes = [
			["home", __("Overview"), "home"],
			...this.data.business_areas.map((area) => [area.route, area.label, area.icon]),
			["query-report/Profit and Loss Statement", __("Reports"), "chart"],
			["workflow-action", __("Approvals"), "check-circle"],
			...(frappe.user_roles.some((role) => ["System Manager", "Schema Reviewer"].includes(role))
				? [["schema-intelligence", __("Schema Intelligence"), "branch"]]
				: []),
		];
		return `
			<aside class="pridict-executive-sidebar" aria-label="${__("Executive navigation")}">
				<div class="pridict-sidebar-brand">
					<img src="/assets/pridict/images/pridict-wordmark.svg" alt="${__("Pridict")}">
				</div>
				<div class="pridict-company-summary">
					<strong>${frappe.utils.escape_html(this.filters.company)}</strong>
					<span>${__("Executive overview")}</span>
				</div>
				<nav>
					${routes
						.map(
							([route, label, icon], index) => `
								<button class="pridict-sidebar-link ${index === 0 ? "is-active" : ""}" data-route="${frappe.utils.escape_html(route)}">
									<span aria-hidden="true">${frappe.utils.icon(icon, "sm")}</span>
									<span>${frappe.utils.escape_html(label)}</span>
								</button>
							`
						)
						.join("")}
				</nav>
			</aside>
		`;
	}

	renderToolbar() {
		return `
			<div class="pridict-executive-toolbar">
				<span>${__("Workspace")} / ${__("Overview")}</span>
				<div class="pridict-toolbar-actions">
					<label>
						<span>${__("Company")}</span>
						<select data-filter="company">
							${this.data.companies
								.map(
									(company) => `<option value="${frappe.utils.escape_html(company.name)}" ${
										company.name === this.filters.company ? "selected" : ""
									}>${frappe.utils.escape_html(company.name)}</option>`
								)
								.join("")}
						</select>
					</label>
					<button class="btn btn-default" data-action="refresh" aria-label="${__("Refresh dashboard")}">${frappe.utils.icon("refresh", "sm")}</button>
				</div>
			</div>
		`;
	}

	renderHero() {
		return `
			<header class="pridict-executive-hero">
				<div>
					<span class="pridict-eyebrow">${__("Your business at a glance")}</span>
					<h1>${__("Executive overview")}</h1>
					<p>${__("Performance, priorities and decisions that need you.")}</p>
				</div>
				<div class="pridict-period-controls">
					<label><span>${__("From")}</span><input type="date" data-filter="from_date" value="${this.filters.from_date}"></label>
					<label><span>${__("To")}</span><input type="date" data-filter="to_date" value="${this.filters.to_date}"></label>
				</div>
			</header>
		`;
	}

	renderMetrics() {
		const metrics = [
			[__("Revenue"), this.data.metrics.revenue, this.data.filters.currency, this.data.definitions.revenue, "trend-up"],
			[__("Total expenses"), this.data.metrics.expenses, this.data.filters.currency, this.data.definitions.expenses, "accounting"],
			[
				__("Sales pipeline"),
				this.data.metrics.pipeline?.value,
				this.data.filters.currency,
				this.data.definitions.pipeline,
				"chart",
				this.data.metrics.pipeline ? __("{0} open opportunities", [this.data.metrics.pipeline.count]) : null,
			],
			[
				__("Overdue receivables"),
				this.data.metrics.overdue_receivables?.value,
				this.data.filters.currency,
				this.data.definitions.overdue_receivables,
				"time",
				this.data.metrics.overdue_receivables
					? __("{0} invoices to follow up", [this.data.metrics.overdue_receivables.count])
					: null,
			],
		];
		return `<section class="pridict-kpi-grid" aria-label="${__("Key performance indicators")}">
			${metrics
				.map(
					([label, value, currency, definition, icon, detail]) => `
						<article class="pridict-kpi-card" title="${frappe.utils.escape_html(definition)}">
							<div class="pridict-kpi-heading"><span>${frappe.utils.escape_html(label)}</span>${frappe.utils.icon(icon, "sm")}</div>
							<strong>${value === null || value === undefined ? __("Restricted") : format_currency(value, currency)}</strong>
							<small>${frappe.utils.escape_html(detail || definition)}</small>
						</article>
					`
				)
				.join("")}
		</section>`;
	}

	renderTasks() {
		return `
			<section class="pridict-dashboard-panel pridict-task-panel">
				<div class="pridict-panel-heading"><h2>${__("Needs your attention")}</h2><span data-task-count></span></div>
				<div class="pridict-task-filters" role="group" aria-label="${__("Filter tasks")}">
					<button data-task-filter="all" aria-pressed="true">${__("All items")}</button>
					<button data-task-filter="approval" aria-pressed="false">${__("Approvals")}</button>
					<button data-task-filter="alert" aria-pressed="false">${__("Alerts")}</button>
				</div>
				<div class="pridict-task-list">
					${
						this.data.tasks.length
							? this.data.tasks.map((task) => this.renderTask(task)).join("")
							: `<div class="pridict-empty-state">${__("Nothing needs your attention for this selection.")}</div>`
					}
				</div>
			</section>
		`;
	}

	renderTask(task) {
		const amount = task.amount ? ` · ${format_currency(task.amount, task.currency)}` : "";
		return `
			<div class="pridict-task-row" data-task-category="${task.category}">
				<span class="pridict-task-icon" aria-hidden="true">${frappe.utils.icon(task.category === "approval" ? "check-circle" : "alert-circle", "sm")}</span>
				<div><strong>${frappe.utils.escape_html(task.title)}</strong><span>${frappe.utils.escape_html(task.meta)}${amount}</span></div>
				<button class="btn btn-default btn-sm" data-doctype="${frappe.utils.escape_html(task.doctype)}" data-name="${frappe.utils.escape_html(task.name)}">${frappe.utils.escape_html(task.action)}</button>
			</div>
		`;
	}

	renderTrend() {
		return `
			<section class="pridict-dashboard-panel">
				<div class="pridict-panel-heading"><h2>${__("Revenue & expenses")}</h2><span>${frappe.utils.escape_html(this.data.filters.currency)}</span></div>
				${this.renderTrendChart()}
			</section>
		`;
	}

	renderTrendChart() {
		if (!this.data.trend?.length) {
			return `<div class="pridict-empty-state">${__("Financial trend data is unavailable for this role or period.")}</div>`;
		}
		const width = 720;
		const height = 220;
		const padding = 28;
		const values = this.data.trend.flatMap((row) => [row.income, row.expense]);
		const maxValue = Math.max(...values, 1);
		const x = (index) => padding + (index * (width - padding * 2)) / Math.max(this.data.trend.length - 1, 1);
		const y = (value) => height - padding - (value / maxValue) * (height - padding * 2);
		const points = (field) => this.data.trend.map((row, index) => `${x(index)},${y(row[field])}`).join(" ");
		return `
			<div class="pridict-chart-legend"><span class="is-income">${__("Revenue")}</span><span class="is-expense">${__("Expenses")}</span></div>
			<div class="pridict-trend-chart">
				<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${__("Revenue and expense trend for the selected period")}">
					<g class="pridict-chart-grid"><line x1="${padding}" y1="${padding}" x2="${width - padding}" y2="${padding}"/><line x1="${padding}" y1="${height / 2}" x2="${width - padding}" y2="${height / 2}"/><line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}"/></g>
					<polyline class="pridict-income-line" points="${points("income")}"/>
					<polyline class="pridict-expense-line" points="${points("expense")}"/>
					${this.data.trend.map((row, index) => `<text x="${x(index)}" y="${height - 6}" text-anchor="middle">${frappe.utils.escape_html(row.label)}</text>`).join("")}
				</svg>
			</div>
		`;
	}

	renderBusinessAreas() {
		return `
			<section class="pridict-dashboard-panel">
				<div class="pridict-panel-heading"><h2>${__("Business areas")}</h2></div>
				<div class="pridict-business-areas">
					${
						this.data.business_areas.length
							? this.data.business_areas
								.map(
									(area) => `<button data-route="${frappe.utils.escape_html(area.route)}"><span aria-hidden="true">${frappe.utils.icon(area.icon, "sm")}</span>${frappe.utils.escape_html(area.label)}</button>`
								)
								.join("")
							: `<div class="pridict-empty-state">${__("No business areas are available for this role.")}</div>`
					}
				</div>
			</section>
		`;
	}

	renderActivity() {
		return `
			<section class="pridict-dashboard-panel">
				<div class="pridict-panel-heading"><h2>${__("Recent activity")}</h2><span>${__("Latest")}</span></div>
				<div class="pridict-activity-list">
					${
						this.data.activity.length
							? this.data.activity
								.map(
									(row) => `<button data-doctype="${frappe.utils.escape_html(row.doctype)}" data-name="${frappe.utils.escape_html(row.name)}"><span class="pridict-activity-dot"></span><span><strong>${frappe.utils.escape_html(row.title)}</strong><small>${frappe.utils.escape_html(row.meta)}</small><small>${frappe.datetime.prettyDate(row.modified)}</small></span></button>`
								)
								.join("")
							: `<div class="pridict-empty-state">${__("No permitted recent activity is available.")}</div>`
					}
				</div>
				<div class="pridict-panel-note">${__("Activity is limited to documents you can read.")}</div>
			</section>
		`;
	}

	bindControls() {
		this.$root.find('[data-filter="company"], [data-filter="from_date"], [data-filter="to_date"]').on("change", (event) => {
			this.filters[event.currentTarget.dataset.filter] = event.currentTarget.value;
			this.refresh();
		});
		this.$root.find("[data-task-filter]").on("click", (event) => {
			this.active_task_filter = event.currentTarget.dataset.taskFilter;
			this.applyTaskFilter();
		});
		this.bindNavigation();
	}

	bindNavigation() {
		this.$root.find('[data-action="retry"], [data-action="refresh"]').on("click", () => this.refresh());
		this.$root.find("[data-route]").on("click", (event) => frappe.set_route(event.currentTarget.dataset.route));
		this.$root.find("[data-doctype][data-name]").on("click", (event) => {
			frappe.set_route("Form", event.currentTarget.dataset.doctype, event.currentTarget.dataset.name);
		});
	}

	applyTaskFilter() {
		const $rows = this.$root.find("[data-task-category]");
		let visible = 0;
		$rows.each((_index, row) => {
			const show = this.active_task_filter === "all" || row.dataset.taskCategory === this.active_task_filter;
			row.hidden = !show;
			if (show) visible += 1;
		});
		this.$root.find("[data-task-filter]").each((_index, button) => {
			button.setAttribute("aria-pressed", button.dataset.taskFilter === this.active_task_filter ? "true" : "false");
		});
		this.$root.find("[data-task-count]").text(__("{0} items", [visible]));
	}
}
