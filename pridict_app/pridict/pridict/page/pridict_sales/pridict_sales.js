frappe.pages["pridict-sales"].on_page_load = (wrapper) => {
	frappe.pridict_sales = new PridictSales(wrapper);
};

frappe.pages["pridict-sales"].on_page_show = () => {
	frappe.pridict_sales?.refresh();
};

class PridictSales {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Sales & CRM"), single_column: true });
		this.company = frappe.defaults.get_user_default("Company");
		$(wrapper).addClass("pridict-sales-page");
		this.$root = $('<div class="pridict-sales" aria-live="polite"></div>').appendTo(this.page.main.empty());
		this.renderLoading();
	}

	async refresh() {
		this.renderLoading();
		try {
			this.data = await frappe.xcall("pridict.pridict.page.pridict_sales.pridict_sales.get_overview", { company: this.company });
			this.company = this.data.filters?.company || this.company;
			this.render();
		} catch (_error) {
			this.renderError();
		}
	}

	renderLoading() {
		this.$root.html(`<div class="pridict-sales-state" role="status"><span class="pridict-executive-spinner"></span><strong>${__("Loading Sales and CRM")}</strong><p>${__("Retrieving permitted customer activity.")}</p></div>`);
	}

	renderError() {
		this.$root.html(`<div class="pridict-sales-state" role="alert"><strong>${__("Sales and CRM could not be loaded")}</strong><p>${__("No data was changed. Try again or open a standard workspace.")}</p><div><button class="btn btn-primary" data-action="retry">${__("Try again")}</button><button class="btn btn-default" data-route="selling">${__("Open Selling workspace")}</button></div></div>`);
		this.bind();
	}

	render() {
		if (!this.data.companies?.length) {
			this.$root.html(`<div class="pridict-sales-state"><strong>${__("No company access")}</strong><p>${frappe.utils.escape_html(this.data.message || "")}</p></div>`);
			return;
		}
		this.$root.html(`
			<header class="pridict-sales-hero">
				<div><span>${__("Customer operations")}</span><h1>${__("Sales & CRM")}</h1><p>${__("Move prospects through qualification, quotation, fulfillment, and billing while retaining native ERPNext controls.")}</p></div>
				<label><span>${__("Company")}</span><select data-filter="company">${this.data.companies.map((company) => `<option value="${frappe.utils.escape_html(company.name)}" ${company.name === this.company ? "selected" : ""}>${frappe.utils.escape_html(company.name)}</option>`).join("")}</select></label>
			</header>
			<section class="pridict-sales-metrics">${this.renderMetrics()}</section>
			<div class="pridict-sales-grid">
				<section class="pridict-sales-panel"><header><div><span>${__("Action required")}</span><h2>${__("Customer work needing follow-up")}</h2></div><b>${this.data.attention.length}</b></header><div>${this.renderAttention()}</div></section>
				<div class="pridict-sales-stack">
					<section class="pridict-sales-panel"><header><div><span>${__("Sales pipeline")}</span><h2>${__("Customer document flow")}</h2></div></header><div class="pridict-sales-pipeline">${this.renderPipeline()}</div></section>
					<section class="pridict-sales-panel"><header><div><span>${__("Quick actions")}</span><h2>${__("Create customer document")}</h2></div></header><div class="pridict-sales-actions">${this.renderActions()}</div></section>
				</div>
			</div>
			<section class="pridict-sales-panel"><header><div><span>${__("Recent activity")}</span><h2>${__("Latest permitted customer documents")}</h2></div></header><div class="pridict-sales-activity">${this.renderActivity()}</div></section>
			<footer class="pridict-sales-footer"><span>${__("Counts and activity respect your document and company permissions.")}</span><div><button class="btn btn-link" data-route="crm">${__("Open CRM workspace")}</button><button class="btn btn-link" data-route="selling">${__("Open Selling workspace")}</button></div></footer>
		`);
		this.bind();
	}

	renderMetrics() {
		const metrics = [
			["open_opportunities", "Open opportunities", "opportunity"],
			["active_quotations", "Active quotations", "quotation"],
			["orders_to_deliver", "Orders to deliver", "sales-order"],
			["orders_to_bill", "Orders to bill", "sales-order"],
		];
		return metrics.map(([key, label, route]) => `<button type="button" data-route="${route}"><span>${__(label)}</span><strong>${this.data.metrics[key] ?? "—"}</strong><small>${frappe.utils.escape_html(this.data.definitions[key] || "")}</small></button>`).join("");
	}

	renderAttention() {
		if (!this.data.attention.length) return `<div class="pridict-sales-empty">${__("No customer documents currently need dated follow-up for this company.")}</div>`;
		return this.data.attention.map((row) => `<button type="button" class="pridict-sales-row" data-doctype="${row.doctype}" data-name="${row.name}"><span><strong>${frappe.utils.escape_html(row.title)}</strong><small>${frappe.utils.escape_html([row.party || row.name, row.status, row.date].filter(Boolean).join(" · "))}</small></span><b>${row.amount ? format_currency(row.amount, row.currency || this.data.filters.currency) : ""}</b></button>`).join("");
	}

	renderPipeline() {
		return this.data.pipeline.map((row, index) => `<button type="button" data-route="${row.doctype.toLowerCase().replaceAll(" ", "-")}"><span>${index + 1}</span><strong>${__(row.doctype)}</strong><b>${row.count ?? "—"}</b></button>`).join("");
	}

	renderActions() {
		return Object.entries(this.data.create_permissions).filter(([, allowed]) => allowed).map(([doctype]) => `<button type="button" class="btn btn-default" data-new-doctype="${doctype}">${frappe.utils.icon("add", "sm")}<span>${__(doctype)}</span></button>`).join("") || `<div class="pridict-sales-empty">${__("You do not have permission to create customer documents.")}</div>`;
	}

	renderActivity() {
		if (!this.data.activity.length) return `<div class="pridict-sales-empty">${__("No permitted customer activity is available.")}</div>`;
		return this.data.activity.map((row) => `<button type="button" data-doctype="${row.doctype}" data-name="${row.name}"><span><strong>${__(row.doctype)}</strong><small>${frappe.utils.escape_html([row.party || row.name, row.status].filter(Boolean).join(" · "))}</small></span><b>${row.amount ? format_currency(row.amount, row.currency || this.data.filters.currency) : ""}</b><time>${frappe.datetime.prettyDate(row.modified)}</time></button>`).join("");
	}

	bind() {
		this.$root.find('[data-action="retry"]').on("click", () => this.refresh());
		this.$root.find("[data-route]").on("click", (event) => frappe.set_route(event.currentTarget.dataset.route));
		this.$root.find("[data-doctype][data-name]").on("click", (event) => frappe.set_route("Form", event.currentTarget.dataset.doctype, event.currentTarget.dataset.name));
		this.$root.find("[data-new-doctype]").on("click", (event) => frappe.new_doc(event.currentTarget.dataset.newDoctype));
		this.$root.find('[data-filter="company"]').on("change", (event) => { this.company = event.currentTarget.value; this.refresh(); });
	}
}
