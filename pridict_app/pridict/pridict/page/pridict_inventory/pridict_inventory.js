frappe.pages["pridict-inventory"].on_page_load = (wrapper) => { frappe.pridict_inventory = new PridictInventory(wrapper); };
frappe.pages["pridict-inventory"].on_page_show = () => { frappe.pridict_inventory?.refresh(); };

class PridictInventory {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Inventory"), single_column: true });
		this.company = frappe.defaults.get_user_default("Company");
		$(wrapper).addClass("pridict-inventory-page");
		this.$root = $('<div class="pridict-inventory" aria-live="polite"></div>').appendTo(this.page.main.empty());
		this.renderLoading();
	}

	async refresh() {
		this.renderLoading();
		try {
			this.data = await frappe.xcall("pridict.pridict.page.pridict_inventory.pridict_inventory.get_overview", { company: this.company });
			this.company = this.data.filters?.company || this.company;
			this.render();
		} catch (_error) { this.renderError(); }
	}

	renderLoading() { this.$root.html(`<div class="pridict-inventory-state"><span class="pridict-executive-spinner"></span><strong>${__("Loading Inventory")}</strong><p>${__("Retrieving permitted stock activity.")}</p></div>`); }
	renderError() { this.$root.html(`<div class="pridict-inventory-state"><strong>${__("Inventory could not be loaded")}</strong><p>${__("No data was changed. Try again or open the standard Stock workspace.")}</p><div><button class="btn btn-primary" data-action="retry">${__("Try again")}</button><button class="btn btn-default" data-route="stock">${__("Open Stock workspace")}</button></div></div>`); this.bind(); }

	render() {
		if (!this.data.companies?.length) { this.$root.html(`<div class="pridict-inventory-state"><strong>${__("No company access")}</strong><p>${frappe.utils.escape_html(this.data.message || "")}</p></div>`); return; }
		this.$root.html(`
			<header class="pridict-inventory-hero"><div><span>${__("Stock operations")}</span><h1>${__("Inventory")}</h1><p>${__("Manage stock masters, movements, picking, reconciliation, traceability, and operational reports.")}</p></div><label><span>${__("Company")}</span><select data-filter="company">${this.data.companies.map((company) => `<option value="${frappe.utils.escape_html(company.name)}" ${company.name === this.company ? "selected" : ""}>${frappe.utils.escape_html(company.name)}</option>`).join("")}</select></label></header>
			<section class="pridict-inventory-metrics">${this.renderMetrics()}</section>
			<div class="pridict-inventory-grid"><section class="pridict-inventory-panel"><header><div><span>${__("Action required")}</span><h2>${__("Stock work needing follow-up")}</h2></div><b>${this.data.attention.length}</b></header><div>${this.renderAttention()}</div></section><div class="pridict-inventory-stack"><section class="pridict-inventory-panel"><header><div><span>${__("Inventory flow")}</span><h2>${__("Operational records")}</h2></div></header><div class="pridict-inventory-pipeline">${this.renderPipeline()}</div></section><section class="pridict-inventory-panel"><header><div><span>${__("Reports")}</span><h2>${__("Stock analysis")}</h2></div></header><div class="pridict-inventory-links">${this.renderReports()}</div></section></div></div>
			<section class="pridict-inventory-panel"><header><div><span>${__("Quick actions")}</span><h2>${__("Create inventory record")}</h2></div></header><div class="pridict-inventory-actions">${this.renderActions()}</div></section>
			<section class="pridict-inventory-panel"><header><div><span>${__("Recent activity")}</span><h2>${__("Latest stock transactions")}</h2></div></header><div class="pridict-inventory-activity">${this.renderActivity()}</div></section>
			<footer class="pridict-inventory-footer"><span>${__("Items and batches are shared masters; company filters apply only where supported by the native document.")}</span><div><button class="btn btn-link" data-route="purchase-receipt">${__("Purchase receipts")}</button><button class="btn btn-link" data-route="delivery-note">${__("Delivery notes")}</button><button class="btn btn-link" data-route="stock">${__("Stock workspace")}</button></div></footer>`);
		this.bind();
	}

	renderMetrics() { const rows=[["stock_items","Stock items","item"],["warehouses","Warehouses","Tree/Warehouse"],["draft_stock_entries","Draft stock entries","stock-entry"],["pending_pick_lists","Pending pick lists","pick-list"]]; return rows.map(([key,label,route])=>`<button data-route="${route}"><span>${__(label)}</span><strong>${this.data.metrics[key] ?? "—"}</strong><small>${frappe.utils.escape_html(this.data.definitions[key] || "")}</small></button>`).join(""); }
	renderAttention() { if(!this.data.attention.length) return `<div class="pridict-inventory-empty">${__("No current stock records require follow-up for this company.")}</div>`; return this.data.attention.map((row)=>`<button class="pridict-inventory-row" data-doctype="${row.doctype}" data-name="${row.name}"><span><strong>${frappe.utils.escape_html(row.title)}</strong><small>${frappe.utils.escape_html([row.detail || row.name,row.status,row.date].filter(Boolean).join(" · "))}</small></span><b>${row.amount !== null && row.amount !== undefined ? format_currency(row.amount,this.data.filters.currency) : ""}</b></button>`).join(""); }
	renderPipeline() { return this.data.pipeline.map((row,index)=>`<button data-route="${row.doctype === "Warehouse" ? "Tree/Warehouse" : row.doctype.toLowerCase().replaceAll(" ","-")}"><span>${index+1}</span><strong>${__(row.doctype)}</strong><b>${row.count ?? "—"}</b></button>`).join(""); }
	renderReports() { return this.data.reports.map((report)=>`<button data-route="${report.route}">${frappe.utils.icon("chart","sm")}<span>${frappe.utils.escape_html(report.label)}</span></button>`).join(""); }
	renderActions() { return Object.entries(this.data.create_permissions).filter(([,allowed])=>allowed).map(([doctype])=>`<button class="btn btn-default" data-new-doctype="${doctype}">${frappe.utils.icon("add","sm")}<span>${__(doctype)}</span></button>`).join("") || `<div class="pridict-inventory-empty">${__("You do not have permission to create inventory records.")}</div>`; }
	renderActivity() { if(!this.data.activity.length) return `<div class="pridict-inventory-empty">${__("No permitted stock activity is available.")}</div>`; return this.data.activity.map((row)=>`<button data-doctype="${row.doctype}" data-name="${row.name}"><span><strong>${__(row.doctype)}</strong><small>${frappe.utils.escape_html([row.detail || row.name,row.status].filter(Boolean).join(" · "))}</small></span><b>${row.amount !== null && row.amount !== undefined ? format_currency(row.amount,this.data.filters.currency) : ""}</b><time>${frappe.datetime.prettyDate(row.modified)}</time></button>`).join(""); }

	bind() {
		this.$root.find('[data-action="retry"]').on("click",()=>this.refresh());
		this.$root.find("[data-route]").on("click",(event)=>frappe.set_route(event.currentTarget.dataset.route));
		this.$root.find("[data-doctype][data-name]").on("click",(event)=>frappe.set_route("Form",event.currentTarget.dataset.doctype,event.currentTarget.dataset.name));
		this.$root.find("[data-new-doctype]").on("click",(event)=>frappe.new_doc(event.currentTarget.dataset.newDoctype));
		this.$root.find('[data-filter="company"]').on("change",(event)=>{ this.company=event.currentTarget.value; this.refresh(); });
	}
}
