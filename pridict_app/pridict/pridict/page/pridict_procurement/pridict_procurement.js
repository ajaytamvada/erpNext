frappe.pages["pridict-procurement"].on_page_load = (wrapper) => {
	frappe.pridict_procurement = new PridictProcurement(wrapper);
};

frappe.pages["pridict-procurement"].on_page_show = () => {
	frappe.pridict_procurement?.refresh();
};

class PridictProcurement {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Procurement"), single_column: true });
		this.company = frappe.defaults.get_user_default("Company");
		$(wrapper).addClass("pridict-procurement-page");
		this.$root = $('<div class="pridict-procurement" aria-live="polite"></div>').appendTo(this.page.main.empty());
		this.renderLoading();
	}

	async refresh() {
		this.renderLoading();
		try {
			const data = await frappe.xcall(
				"pridict.pridict.page.pridict_procurement.pridict_procurement.get_overview",
				{ company: this.company }
			);
			this.data = data;
			this.company = data.filters?.company || this.company;
			this.render();
		} catch (_error) {
			this.renderError();
		}
	}

	renderLoading() {
		this.$root.html(`<div class="pridict-procurement-state" role="status"><span class="pridict-executive-spinner"></span><strong>${__("Loading Procurement")}</strong><p>${__("Retrieving permitted purchasing activity.")}</p></div>`);
	}

	renderError() {
		this.$root.html(`<div class="pridict-procurement-state" role="alert"><strong>${__("Procurement could not be loaded")}</strong><p>${__("No data was changed. Try again or open the standard Buying workspace.")}</p><div><button class="btn btn-primary" data-action="retry">${__("Try again")}</button><button class="btn btn-default" data-route="buying">${__("Open Buying workspace")}</button></div></div>`);
		this.bind();
	}

	render() {
		if (!this.data.companies?.length) {
			this.$root.html(`<div class="pridict-procurement-state"><strong>${__("No company access")}</strong><p>${frappe.utils.escape_html(this.data.message || "")}</p></div>`);
			return;
		}
		this.$root.html(`
			<header class="pridict-procurement-hero">
				<div><span>${__("Purchasing operations")}</span><h1>${__("Procurement")}</h1><p>${__("Move approved demand through ordering, receipt, and supplier billing without leaving the Pridict operating view.")}</p></div>
				<label><span>${__("Company")}</span><select data-filter="company">${this.data.companies.map((company) => `<option value="${frappe.utils.escape_html(company.name)}" ${company.name === this.company ? "selected" : ""}>${frappe.utils.escape_html(company.name)}</option>`).join("")}</select></label>
			</header>
			<section class="pridict-procurement-metrics">${this.renderMetrics()}</section>
			<div class="pridict-procurement-grid">
				<section class="pridict-procurement-panel pridict-procurement-attention"><header><div><span>${__("Action required")}</span><h2>${__("Documents needing follow-up")}</h2></div><b>${this.data.attention.length}</b></header>${this.renderAttention()}</section>
				<div class="pridict-procurement-stack">
					<section class="pridict-procurement-panel"><header><div><span>${__("Purchasing pipeline")}</span><h2>${__("Document flow")}</h2></div></header><div class="pridict-procurement-pipeline">${this.renderPipeline()}</div></section>
					<section class="pridict-procurement-panel"><header><div><span>${__("Quick actions")}</span><h2>${__("Create purchasing document")}</h2></div></header><div class="pridict-procurement-actions">${this.renderActions()}</div></section>
			</div>
			</div>
			<section class="pridict-procurement-panel"><header><div><span>${__("Recent activity")}</span><h2>${__("Latest permitted documents")}</h2></div></header><div class="pridict-procurement-activity">${this.renderActivity()}</div></section>
			<footer class="pridict-procurement-footer"><span>${__("Counts and activity respect your document and company permissions.")}</span><button class="btn btn-link" data-route="buying">${__("Open standard Buying workspace")}</button></footer>
		`);
		this.bind();
	}

	renderMetrics() {
		const metrics = [
			["material_requests", "Submitted requests", "material-request"],
			["purchase_orders_to_receive", "Orders to receive", "purchase-order"],
			["purchase_orders_to_bill", "Orders to bill", "purchase-order"],
			["unpaid_purchase_invoices", "Unpaid invoices", "purchase-invoice"],
		];
		return metrics.map(([key, label, route]) => `<button type="button" data-route="${route}" class="pridict-procurement-metric"><span>${__(label)}</span><strong>${this.data.metrics[key] ?? "—"}</strong><small>${frappe.utils.escape_html(this.data.definitions[key] || "")}</small></button>`).join("");
	}

	renderAttention() {
		if (!this.data.attention.length) return `<div class="pridict-procurement-empty">${__("No purchasing documents currently need follow-up for this company.")}</div>`;
		return this.data.attention.map((row) => `<button type="button" class="pridict-procurement-row" data-doctype="${row.doctype}" data-name="${row.name}"><span class="pridict-procurement-row-icon">${frappe.utils.icon("right", "sm")}</span><span><strong>${frappe.utils.escape_html(row.title)}</strong><small>${frappe.utils.escape_html([row.party, row.name, row.status, row.date].filter(Boolean).join(" · "))}</small></span><b>${row.amount ? format_currency(row.amount, row.currency) : ""}</b></button>`).join("");
	}

	renderPipeline() {
		return this.data.pipeline.map((stage, index) => `<button type="button" data-route="${stage.doctype.toLowerCase().replaceAll(" ", "-")}"><span>${index + 1}</span><strong>${__(stage.doctype)}</strong><b>${stage.count ?? "—"}</b></button>`).join("");
	}

	renderActions() {
		return Object.entries(this.data.create_permissions).filter(([, allowed]) => allowed).map(([doctype]) => `<button type="button" class="btn btn-default" data-new-doctype="${doctype}">${frappe.utils.icon("add", "sm")}<span>${__(doctype)}</span></button>`).join("") || `<div class="pridict-procurement-empty">${__("You do not have permission to create purchasing documents.")}</div>`;
	}

	renderActivity() {
		if (!this.data.activity.length) return `<div class="pridict-procurement-empty">${__("No permitted purchasing activity is available.")}</div>`;
		return this.data.activity.map((row) => `<button type="button" data-doctype="${row.doctype}" data-name="${row.name}"><span><strong>${__(row.doctype)}</strong><small>${frappe.utils.escape_html([row.party, row.name, row.status].filter(Boolean).join(" · "))}</small></span><time>${frappe.datetime.prettyDate(row.modified)}</time></button>`).join("");
	}

	bind() {
		this.$root.find('[data-action="retry"]').on("click", () => this.refresh());
		this.$root.find("[data-route]").on("click", (event) => frappe.set_route(event.currentTarget.dataset.route));
		this.$root.find("[data-doctype][data-name]").on("click", (event) => frappe.set_route("Form", event.currentTarget.dataset.doctype, event.currentTarget.dataset.name));
		this.$root.find("[data-new-doctype]").on("click", (event) => frappe.new_doc(event.currentTarget.dataset.newDoctype));
		this.$root.find('[data-filter="company"]').on("change", (event) => { this.company = event.currentTarget.value; this.refresh(); });
	}
}
