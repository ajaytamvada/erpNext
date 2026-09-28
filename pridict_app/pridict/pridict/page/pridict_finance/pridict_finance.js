frappe.pages["pridict-finance"].on_page_load = (wrapper) => {
	frappe.pridict_finance = new PridictFinance(wrapper);
};

frappe.pages["pridict-finance"].on_page_show = () => {
	frappe.pridict_finance?.refresh();
};

class PridictFinance {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Finance"), single_column: true });
		this.filters = {
			company: frappe.defaults.get_user_default("Company"),
			from_date: frappe.datetime.add_months(frappe.datetime.get_today(), -5),
			to_date: frappe.datetime.get_today(),
		};
		$(wrapper).addClass("pridict-finance-page");
		this.$root = $('<div class="pridict-finance" aria-live="polite"></div>').appendTo(this.page.main.empty());
		this.renderLoading();
	}

	async refresh() {
		this.renderLoading();
		try {
			this.data = await frappe.xcall(
				"pridict.pridict.page.pridict_finance.pridict_finance.get_overview",
				this.filters
			);
			this.filters = { ...this.filters, ...(this.data.filters || {}) };
			this.render();
		} catch (_error) {
			this.renderError();
		}
	}

	renderLoading() {
		this.$root.html(`<div class="pridict-finance-state" role="status"><span class="pridict-executive-spinner"></span><strong>${__("Loading Finance")}</strong><p>${__("Retrieving permitted financial information.")}</p></div>`);
	}

	renderError() {
		this.$root.html(`<div class="pridict-finance-state" role="alert"><strong>${__("Finance could not be loaded")}</strong><p>${__("No data was changed. Try again or open the standard Accounting workspace.")}</p><div><button class="btn btn-primary" data-action="retry">${__("Try again")}</button><button class="btn btn-default" data-route="accounting">${__("Open Accounting workspace")}</button></div></div>`);
		this.bind();
	}

	render() {
		if (!this.data.companies?.length) {
			this.$root.html(`<div class="pridict-finance-state"><strong>${__("No company access")}</strong><p>${frappe.utils.escape_html(this.data.message || "")}</p></div>`);
			return;
		}
		this.$root.html(`
			<header class="pridict-finance-hero">
				<div><span>${__("Financial operations")}</span><h1>${__("Finance")}</h1><p>${__("Monitor performance, receivables, payables, and accounting activity from one permission-aware workspace.")}</p></div>
				<div class="pridict-finance-filters">
					<label><span>${__("Company")}</span><select data-filter="company">${this.data.companies.map((company) => `<option value="${frappe.utils.escape_html(company.name)}" ${company.name === this.filters.company ? "selected" : ""}>${frappe.utils.escape_html(company.name)}</option>`).join("")}</select></label>
					<label><span>${__("From")}</span><input type="date" data-filter="from_date" value="${this.filters.from_date}"></label>
					<label><span>${__("To")}</span><input type="date" data-filter="to_date" value="${this.filters.to_date}"></label>
				</div>
			</header>
			<section class="pridict-finance-metrics">${this.renderMetrics()}</section>
			<div class="pridict-finance-grid">
				<section class="pridict-finance-panel"><header><div><span>${__("Action required")}</span><h2>${__("Overdue receivables and payables")}</h2></div><b>${this.data.attention.length}</b></header><div>${this.renderAttention()}</div></section>
				<div class="pridict-finance-stack">
					<section class="pridict-finance-panel"><header><div><span>${__("Reports")}</span><h2>${__("Financial statements and ledgers")}</h2></div></header><div class="pridict-finance-links">${this.renderReports()}</div></section>
					<section class="pridict-finance-panel"><header><div><span>${__("Quick actions")}</span><h2>${__("Create financial document")}</h2></div></header><div class="pridict-finance-actions">${this.renderActions()}</div></section>
				</div>
			</div>
			<section class="pridict-finance-panel"><header><div><span>${__("Recent activity")}</span><h2>${__("Latest permitted financial documents")}</h2></div></header><div class="pridict-finance-activity">${this.renderActivity()}</div></section>
			<footer class="pridict-finance-footer"><span>${__("Financial values use the selected company's default currency and the Profit and Loss report calculation.")}</span><button class="btn btn-link" data-route="accounting">${__("Open standard Accounting workspace")}</button></footer>
		`);
		this.bind();
	}

	renderMetrics() {
		const metrics = [
			["revenue", "Revenue", "Currency"],
			["expenses", "Expenses", "Currency"],
			["overdue_receivables", "Overdue receivables", "Count"],
			["overdue_payables", "Overdue payables", "Count"],
		];
		return metrics.map(([key, label, type]) => `<article><span>${__(label)}</span><strong>${this.formatMetric(this.data.metrics[key], type)}</strong><small>${frappe.utils.escape_html(this.data.definitions[key] || "")}</small></article>`).join("");
	}

	formatMetric(value, type) {
		if (value === null || value === undefined) return "—";
		if (type === "Currency") return format_currency(value, this.filters.currency);
		return Number(value).toLocaleString();
	}

	renderAttention() {
		if (!this.data.attention.length) return `<div class="pridict-finance-empty">${__("No overdue invoices require attention for this company.")}</div>`;
		return this.data.attention.map((row) => `<button type="button" class="pridict-finance-row" data-doctype="${row.doctype}" data-name="${row.name}"><span><strong>${frappe.utils.escape_html(row.party || row.name)}</strong><small>${frappe.utils.escape_html([row.doctype, row.name, row.status, row.due_date].filter(Boolean).join(" · "))}</small></span><b>${format_currency(row.amount, row.currency)}</b></button>`).join("");
	}

	renderReports() {
		return this.data.reports.map((report) => `<button type="button" data-route="${report.route}">${frappe.utils.icon("chart", "sm")}<span>${frappe.utils.escape_html(report.label)}</span></button>`).join("");
	}

	renderActions() {
		return Object.entries(this.data.create_permissions).filter(([, allowed]) => allowed).map(([doctype]) => `<button type="button" class="btn btn-default" data-new-doctype="${doctype}">${frappe.utils.icon("add", "sm")}<span>${__(doctype)}</span></button>`).join("") || `<div class="pridict-finance-empty">${__("You do not have permission to create financial documents.")}</div>`;
	}

	renderActivity() {
		if (!this.data.activity.length) return `<div class="pridict-finance-empty">${__("No permitted financial activity is available.")}</div>`;
		return this.data.activity.map((row) => `<button type="button" data-doctype="${row.doctype}" data-name="${row.name}"><span><strong>${__(row.doctype)}</strong><small>${frappe.utils.escape_html([row.name, row.status].filter(Boolean).join(" · "))}</small></span><b>${row.amount ? format_currency(row.amount, row.currency || this.filters.currency) : ""}</b><time>${frappe.datetime.prettyDate(row.modified)}</time></button>`).join("");
	}

	bind() {
		this.$root.find('[data-action="retry"]').on("click", () => this.refresh());
		this.$root.find("[data-route]").on("click", (event) => frappe.set_route(event.currentTarget.dataset.route));
		this.$root.find("[data-doctype][data-name]").on("click", (event) => frappe.set_route("Form", event.currentTarget.dataset.doctype, event.currentTarget.dataset.name));
		this.$root.find("[data-new-doctype]").on("click", (event) => frappe.new_doc(event.currentTarget.dataset.newDoctype));
		this.$root.find("[data-filter]").on("change", (event) => { this.filters[event.currentTarget.dataset.filter] = event.currentTarget.value; this.refresh(); });
	}
}
