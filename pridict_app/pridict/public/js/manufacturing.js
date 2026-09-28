(() => {
	const namespace = window.pridict || {};
	const routeContext = namespace.routeContext;
	const surface = namespace.surface;
	const components = namespace.components;
	if (!routeContext || !surface || !components) return;

	const config = {
		BOM: {
			description: "Define materials, operations, scrap, process loss, and cost through the native BOM engine.",
			presets: [["Active", { is_active: 1 }], ["Default", { is_default: 1 }]],
			fields: [["item", "Item"], ["quantity", "Quantity"], ["company", "Company"], ["with_operations", "Operations", "Check"], ["total_cost", "Total Cost", "Currency"], ["process_loss_qty", "Process Loss Qty"]],
		},
		"Production Plan": {
			description: "Plan finished goods, subassemblies, work orders, and material requests without replacing native planning logic.",
			presets: [["Not started", { status: ["in", ["Submitted", "Not Started"]] }], ["In process", { status: "In Process" }]],
			fields: [["company", "Company"], ["posting_date", "Posting Date"], ["from_date", "From Date"], ["to_date", "To Date"], ["total_planned_qty", "Planned Qty"], ["total_produced_qty", "Produced Qty"]],
		},
		"Work Order": {
			description: "Control material transfer, operations, manufactured quantity, process loss, and stock-entry actions.",
			presets: [["Not started", { status: ["in", ["Submitted", "Not Started"]] }], ["In process", { status: "In Process" }]],
			fields: [["production_item", "Production Item"], ["qty", "To Manufacture"], ["material_transferred_for_manufacturing", "Material Transferred"], ["produced_qty", "Manufactured"], ["wip_warehouse", "WIP Warehouse"], ["fg_warehouse", "Target Warehouse"]],
		},
		"Job Card": {
			description: "Record operation execution, workstation time, completed quantity, employees, and process loss.",
			presets: [["Open", { status: "Open" }], ["In progress", { status: "Work In Progress" }], ["Completed", { status: "Completed" }]],
			fields: [["work_order", "Work Order"], ["operation", "Operation"], ["workstation", "Workstation"], ["for_quantity", "Target Qty"], ["total_completed_qty", "Completed Qty"], ["process_loss_qty", "Process Loss Qty"]],
		},
		Operation: { description: "Maintain reusable operation definitions and default workstation settings.", presets: [], fields: [["name", "Operation"], ["workstation", "Default Workstation"]] },
		Workstation: { description: "Maintain production capacity, working hours, holidays, rates, and workstation status.", presets: [["Production", { status: "Production" }], ["Off", { status: "Off" }]], fields: [["name", "Workstation"], ["status", "Status"], ["warehouse", "Warehouse"], ["hour_rate", "Hourly Rate", "Currency"]] },
	};
	const reports = new Map([["production-analytics", "Production Analytics"], ["production-planning-report", "Production Planning Report"], ["work-order-summary", "Work Order Summary"], ["job-card-summary", "Job Card Summary"], ["bom-stock-report", "BOM Stock Report"], ["process-loss-report", "Process Loss Report"]]);
	const journey = [["Manufacturing", "pridict-manufacturing"], ["BOM", "bom"], ["Production Plan", "production-plan"], ["Work Order", "work-order"], ["Job Card", "job-card"], ["Operation", "operation"], ["Workstation", "workstation"]];

	function format(value, type, doc) {
		if (value === undefined || value === null || value === "") return __("Not set");
		if (type === "Currency") return frappe.format(value, { fieldtype: "Currency", options: doc.currency || doc.company_currency || frappe.boot?.sysdefaults?.currency });
		if (type === "Check") return value ? __("Yes") : __("No");
		return surface.escape(value);
	}

	function ensureJourney(page, context) {
		const nav = surface.ensureJourney(page, { className: "pridict-manufacturing-journey", label: "Manufacturing journey", items: journey });
		nav.querySelectorAll("button").forEach((button, index) => {
			const active = journey[index][0] === context.doctype || button.dataset.route === context.slug;
			button.classList.toggle("is-active", active);
			if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
		});
	}

	function ensureIntro(page, context) {
		if (context.surface === "report" && reports.has(context.slug)) {
			surface.ensureIntro(page, "pridict-manufacturing-report-intro", "Production analysis", reports.get(context.slug), "Use native filters, calculations, exports, charts, and drill-down links within the Pridict production frame.");
			page.querySelectorAll(".report-wrapper,.query-report,.report-view").forEach((element) => element.classList.add("pridict-manufacturing-report-native"));
			return;
		}
		const current = config[context.doctype];
		if (context.surface !== "list" || !current) return;
		let intro = page.querySelector(".pridict-manufacturing-intro");
		if (!intro) { intro = document.createElement("section"); intro.className = "pridict-manufacturing-intro"; page.querySelector(".page-body .container,.page-body")?.prepend(intro); }
		surface.render(intro, `<div><span>${__("Production operations")}</span><strong>${__(context.doctype)}</strong><p>${__(current.description)}</p></div><div>${current.presets.map(([label, filters]) => `<button class="btn btn-default btn-sm" data-filter="${surface.escape(JSON.stringify(filters))}">${__(label)}</button>`).join("")}</div>`);
		intro.onclick = (event) => { const button = event.target.closest("[data-filter]"); if (!button) return; frappe.route_options = JSON.parse(button.dataset.filter); frappe.set_route("List", context.doctype, "List"); };
	}

	function progress(doctype, doc) {
		const ratio = (label, numerator, denominator) => numerator === undefined || denominator === undefined || !Number(denominator) ? null : [label, Number(numerator || 0) / Number(denominator) * 100];
		if (doctype === "Production Plan") return [ratio(__("Produced"), doc.total_produced_qty, doc.total_planned_qty)].filter(Boolean);
		if (doctype === "Work Order") return [ratio(__("Transferred"), doc.material_transferred_for_manufacturing, doc.qty), ratio(__("Produced"), doc.produced_qty, doc.qty)].filter(Boolean);
		if (doctype === "Job Card") return [ratio(__("Completed"), doc.total_completed_qty, doc.for_quantity)].filter(Boolean);
		return [];
	}

	function enhanceRows(page, context) {
		if (context.surface !== "list" || !window.cur_list?.data?.length) return;
		window.cur_list.data.forEach((doc) => {
			const values = progress(context.doctype, doc); if (!values.length) return;
			const row = page.querySelector(`[data-name="${window.CSS?.escape ? CSS.escape(doc.name) : doc.name}"]`); if (!row) return;
			let block = row.querySelector(".pridict-manufacturing-progress"); if (!block) { block = document.createElement("div"); block.className = "pridict-manufacturing-progress"; (row.querySelector(".level-right") || row).appendChild(block); }
			surface.render(block, values.map(([label, value]) => { const percent = Math.max(0, Math.min(100, Number(value) || 0)); return `<span><i><b style="width:${percent}%"></b></i><em>${surface.escape(label)} ${percent.toFixed(0)}%</em></span>`; }).join(""));
		});
	}

	function guidance(doctype, doc) {
		if (doc.docstatus === 2) return __("This record is cancelled. Use native amendment actions when available.");
		if (doc.docstatus === 0 && !["Operation", "Workstation"].includes(doctype)) return __("Review required fields, materials, quantities, operations, warehouses, and costs before submission.");
		if (doctype === "BOM") return doc.is_active ? __("This BOM is active. Review materials, operations, scrap, process loss, and calculated cost.") : __("This BOM is inactive and will not be selected by native manufacturing flows.");
		if (doctype === "Production Plan") return __("Review planned and produced quantities, subassemblies, work orders, and material requests.");
		if (doctype === "Work Order") return __("Review material transfer and manufactured quantity progress with native stock-entry and job-card actions.");
		if (doctype === "Job Card") return __("Review completed quantity, time logs, employees, workstation, and process loss before completion.");
		return __("Use native manufacturing controls and linked records for the next permitted action.");
	}

	function ensureSummary(page, context) {
		const current = config[context.doctype], frm = window.cur_frm;
		if (context.surface !== "form" || !current || frm?.doc?.doctype !== context.doctype) return;
		components.ensureDocumentSummary({
			page,
			className: "pridict-manufacturing-summary",
			eyebrow: "Manufacturing record",
			name: frm.doc.name,
			status: components.documentStatus(frm.doc),
			fields: current.fields.map(([field, label, type]) => [label, format(frm.doc[field], type, frm.doc)]),
			guidance: guidance(context.doctype, frm.doc),
		});
		components.tagNativeDocumentRegions(page, { grid: "pridict-manufacturing-grid", timeline: "pridict-manufacturing-timeline", linked: "pridict-manufacturing-links" });
	}

	function remove() { surface.remove(".pridict-manufacturing-journey,.pridict-manufacturing-intro,.pridict-manufacturing-report-intro,.pridict-manufacturing-summary,.pridict-manufacturing-progress"); document.querySelectorAll(".pridict-manufacturing-route").forEach((element) => element.classList.remove("pridict-manufacturing-route")); document.documentElement.classList.remove("pridict-manufacturing-surface"); }
	function apply(context) { if (!context.isManufacturing) { remove(); return; } const page = surface.visiblePage(); if (!page) return; document.documentElement.classList.add("pridict-manufacturing-surface"); page.classList.add("pridict-manufacturing-route"); ensureJourney(page, context); ensureIntro(page, context); enhanceRows(page, context); ensureSummary(page, context); }
	function refreshForm() { const context = routeContext.classify(); setTimeout(() => apply(context), 50); setTimeout(() => apply(context), 250); }
	const refresh = routeContext.onRouteChange((context) => { setTimeout(() => apply(context), 120); setTimeout(() => apply(context), 500); });
	const observer = new MutationObserver(() => refresh()); observer.observe(document.documentElement, { childList: true, subtree: true }); setTimeout(() => observer.disconnect(), 20000);
	namespace.manufacturing = { apply, refreshForm };
})();
