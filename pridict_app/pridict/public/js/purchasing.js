(() => {
	const namespace = (window.pridict = window.pridict || {});
	const routeContext = namespace.routeContext;
	const surface = namespace.surface;
	const components = namespace.components;
	if (!routeContext || !surface || !components) return;

	const documentConfig = {
		"Material Request": {
			description: "Plan internal demand and convert approved requirements into purchasing documents.",
			presets: [
				["Purchase requests", { material_request_type: "Purchase" }],
				["Pending ordering", { docstatus: 1, per_ordered: ["<", 100] }],
			],
			fields: [
				["material_request_type", "Purpose"],
				["company", "Company"],
				["schedule_date", "Required By"],
				["set_warehouse", "Target Warehouse"],
				["per_ordered", "Ordered", "Percent"],
				["per_received", "Received", "Percent"],
			],
		},
		"Purchase Order": {
			description: "Control supplier commitments, receipt progress, billing progress, and order value.",
			presets: [
				["To receive", { docstatus: 1, per_received: ["<", 100] }],
				["To bill", { docstatus: 1, per_billed: ["<", 100] }],
			],
			fields: [
				["supplier_name", "Supplier"],
				["company", "Company"],
				["transaction_date", "Order Date"],
				["schedule_date", "Required By"],
				["currency", "Currency"],
				["grand_total", "Grand Total", "Currency"],
				["per_received", "Received", "Percent"],
				["per_billed", "Billed", "Percent"],
			],
		},
		"Purchase Receipt": {
			description: "Record accepted and rejected goods while preserving stock, quality, and billing controls.",
			presets: [
				["To bill", { docstatus: 1, per_billed: ["<", 100] }],
				["Returns", { is_return: 1 }],
			],
			fields: [
				["supplier_name", "Supplier"],
				["company", "Company"],
				["posting_date", "Posting Date"],
				["set_warehouse", "Accepted Warehouse"],
				["is_return", "Return", "Check"],
				["grand_total", "Grand Total", "Currency"],
				["per_billed", "Billed", "Percent"],
			],
		},
		"Purchase Invoice": {
			description: "Review supplier billing, due dates, taxes, outstanding value, and linked receipts or orders.",
			presets: [
				["Outstanding", { docstatus: 1, outstanding_amount: [">", 0] }],
				["Overdue", { status: "Overdue" }],
			],
			fields: [
				["supplier_name", "Supplier"],
				["bill_no", "Supplier Invoice"],
				["posting_date", "Posting Date"],
				["due_date", "Due Date"],
				["grand_total", "Grand Total", "Currency"],
				["outstanding_amount", "Outstanding", "Currency"],
			],
		},
	};
	const journey = [
		["Material Request", "material-request"],
		["Purchase Order", "purchase-order"],
		["Purchase Receipt", "purchase-receipt"],
		["Purchase Invoice", "purchase-invoice"],
	];

	function escape(value) {
		return window.frappe?.utils?.escape_html?.(String(value ?? "")) || String(value ?? "");
	}

	function formatValue(value, fieldtype, doc) {
		if (value === undefined || value === null || value === "") return __("Not set");
		if (fieldtype === "Currency" && window.frappe?.format) {
			return frappe.format(value, { fieldtype: "Currency", options: doc?.currency });
		}
		if (fieldtype === "Percent") return `${Number(value || 0).toFixed(0)}%`;
		if (fieldtype === "Check") return value ? __("Yes") : __("No");
		return escape(value);
	}

	function nextStepFor(doctype, doc) {
		if (doc.docstatus === 2) return { label: __("This document is cancelled. Use the native Amend action when available."), tone: "muted" };
		if (doc.docstatus === 0) return { label: __("Complete the required fields, review the item table, then use the native Save or Submit action."), tone: "draft" };
		if (doctype === "Material Request") {
			if (doc.material_request_type === "Purchase" && Number(doc.per_ordered || 0) < 100) return { label: __("Approved demand remains to be ordered. Use the native Create menu to make the next purchasing document."), tone: "attention" };
			return { label: __("Review ordered and received progress together with the native linked documents."), tone: "complete" };
		}
		if (doctype === "Purchase Order") {
			const receive = Number(doc.per_received || 0) < 100;
			const bill = Number(doc.per_billed || 0) < 100;
			if (receive && bill) return { label: __("This order is awaiting both receipt and supplier billing."), tone: "attention" };
			if (receive) return { label: __("This order still has quantities to receive."), tone: "attention" };
			if (bill) return { label: __("Receipt is complete and supplier billing remains."), tone: "attention" };
			return { label: __("Receipt and billing progress are complete."), tone: "complete" };
		}
		if (doctype === "Purchase Receipt") {
			if (doc.is_return) return { label: __("This is a return document. Review the linked original receipt and stock impact."), tone: "attention" };
			if (Number(doc.per_billed || 0) < 100) return { label: __("Received goods remain available for supplier billing through the native Create action."), tone: "attention" };
			return { label: __("Supplier billing progress for this receipt is complete."), tone: "complete" };
		}
		if (doctype === "Purchase Invoice") {
			if (doc.is_return) return { label: __("This is a return or debit-note document. Review the original invoice and ledger links."), tone: "attention" };
			if (Number(doc.outstanding_amount || 0) > 0) return { label: __("An outstanding supplier balance remains. Use native payment actions according to your permissions."), tone: "attention" };
			return { label: __("This supplier invoice has no outstanding balance."), tone: "complete" };
		}
		return { label: __("Use the native document actions for the next permitted step."), tone: "muted" };
	}

	function visiblePage() {
		return [...document.querySelectorAll(".page-container")].find((element) => element.offsetParent !== null) || null;
	}

	function ensureJourney(page, context) {
		let nav = page.querySelector(".pridict-purchasing-journey");
		if (!nav) {
			nav = document.createElement("nav");
			nav.className = "pridict-purchasing-journey";
			nav.setAttribute("aria-label", __("Purchasing journey"));
			const procurement = `<button type="button" data-route="pridict-procurement">${__("Procurement")}</button>`;
			nav.innerHTML = procurement.concat(
				journey
					.map(
						([label, route]) => `<button type="button" data-route="${route}" data-doctype="${label}">${__(label)}</button>`
					)
					.join("")
			);
			nav.addEventListener("click", (event) => {
				const button = event.target.closest("[data-route]");
				if (button) frappe.set_route(button.dataset.route);
			});
			const head = page.querySelector(".page-head");
			(head || page).insertAdjacentElement("afterend", nav);
		}
		nav.querySelectorAll("button").forEach((button) => {
			const isProcurement = context.slug === "pridict-procurement" || context.slug === "buying";
			button.classList.toggle(
				"is-active",
				button.dataset.doctype ? button.dataset.doctype === context.doctype : isProcurement
			);
			if (button.classList.contains("is-active")) button.setAttribute("aria-current", "page");
			else button.removeAttribute("aria-current");
		});
	}

	function ensureListIntro(page, context) {
		if (context.surface !== "list" || !context.doctype || page.querySelector(".pridict-list-intro")) return;
		const config = documentConfig[context.doctype];
		if (!config) return;
		const intro = surface.ensureListContext(page, {
			className: "pridict-list-intro",
			label: "Quick filters",
			actionsClass: "pridict-list-presets",
			actions: `<button type="button" class="btn btn-default btn-sm" data-pridict-list-all>${__("All")}</button>${(config.presets || []).map(([label, filters]) => `<button type="button" class="btn btn-default btn-sm" data-pridict-list-filter="${escape(JSON.stringify(filters))}">${__(label)}</button>`).join("")}`,
		});
		intro.addEventListener("click", (event) => {
			const allButton = event.target.closest("[data-pridict-list-all]");
			const filterButton = event.target.closest("[data-pridict-list-filter]");
			if (!allButton && !filterButton) return;
			surface.applyListFilters(context.doctype, filterButton ? JSON.parse(filterButton.dataset.pridictListFilter) : {});
		});
	}

	function progressValues(context, doc) {
		if (context.doctype === "Material Request") {
			return [[__("Ordered"), doc.per_ordered], [__("Received"), doc.per_received]];
		}
		if (context.doctype === "Purchase Order") {
			return [[__("Received"), doc.per_received], [__("Billed"), doc.per_billed]];
		}
		if (context.doctype === "Purchase Receipt") {
			return [[__("Billed"), doc.per_billed]];
		}
		if (context.doctype === "Purchase Invoice") {
			const total = Math.abs(Number(doc.base_grand_total || 0));
			const outstanding = Math.abs(Number(doc.outstanding_amount || 0));
			return [[__("Outstanding"), total ? (outstanding / total) * 100 : 0]];
		}
		return [];
	}

	function enhanceListRows(page, context) {
		if (context.surface !== "list" || !window.cur_list?.data?.length) return;
		window.cur_list.data.forEach((doc) => {
			const selector = `[data-name="${window.CSS?.escape ? CSS.escape(doc.name) : doc.name}"]`;
			const row = page.querySelector(selector);
			if (!row) return;
			const values = progressValues(context, doc).filter(([, value]) => value !== undefined && value !== null);
			if (!values.length) return;
			const signature = JSON.stringify(values.map(([label, value]) => [label, Math.max(0, Math.min(100, Number(value) || 0))]));
			let progress = row.querySelector(".pridict-list-row-progress");
			if (!progress) {
				progress = document.createElement("div");
				progress.className = "pridict-list-row-progress";
				(row.querySelector(".level-right") || row).appendChild(progress);
			}
			if (progress.dataset.signature === signature) return;
			progress.dataset.signature = signature;
			progress.innerHTML = values
				.map(([label, value]) => {
					const percentage = Math.max(0, Math.min(100, Number(value) || 0));
					return `<span title="${escape(label)}: ${percentage.toFixed(0)}%"><i><b style="width:${percentage}%"></b></i><em>${escape(label)} ${percentage.toFixed(0)}%</em></span>`;
				})
				.join("");
		});
	}

	function tagFormSections(page) {
		page.querySelectorAll(".pridict-native-details, .pridict-native-items, .pridict-native-totals, .pridict-form-section-details, .pridict-form-section-items, .pridict-form-section-totals").forEach((section) => {
			section.classList.remove("pridict-native-details", "pridict-native-items", "pridict-native-totals", "pridict-form-section-details", "pridict-form-section-items", "pridict-form-section-totals");
		});
		components.tagNativeFieldSections(page, ["supplier", "material_request_type"], "pridict-native-details", "pridict-form-section-details");
		const itemSection = components.tagNativeFieldSection(page, ["items"], "pridict-native-items", "pridict-form-section-items");
		components.tagNativeFieldSections(page, ["taxes", "grand_total"], "pridict-native-totals", "pridict-form-section-totals");
		components.tagNativeDocumentRegions(page, { grid: "pridict-transaction-grid", timeline: "pridict-document-timeline", linked: "pridict-linked-documents" });
		page.querySelector(".page-actions")?.classList.add("pridict-document-actions");
		page.querySelector(".form-sidebar")?.classList.add("pridict-document-sidebar");
		components.ensureGridScrollNote(itemSection, "On smaller screens, swipe horizontally to review every item column.");
		page.querySelectorAll(".page-actions button, .page-actions .btn").forEach((button) => {
			const label = button.textContent.trim().toLowerCase();
			let kind = "utility";
			if (button.classList.contains("primary-action") || button.classList.contains("btn-primary")) kind = "primary";
			else if (button.classList.contains("btn-danger")) kind = "danger";
			else if (["save", "submit", "update"].some((value) => label.startsWith(value))) kind = "primary";
			else if (["cancel", "delete"].some((value) => label.startsWith(value))) kind = "danger";
			else if (["create", "make"].some((value) => label.startsWith(value))) kind = "transition";
			button.dataset.pridictActionKind = kind;
		});
	}

	function currentForm(context) {
		const form = window.cur_frm;
		return form?.doc?.doctype === context.doctype ? form : null;
	}

	function ensureDocumentSummary(page, context) {
		if (context.surface !== "form" || !context.doctype) return;
		const config = documentConfig[context.doctype];
		const form = currentForm(context);
		if (!config || !form) return;
		const nextStep = nextStepFor(context.doctype, form.doc);
		components.ensureDocumentSummary({
			page,
			className: "pridict-document-summary",
			headerClass: "pridict-document-summary-heading",
			fieldsClass: "pridict-document-summary-grid",
			eyebrow: "Procurement document",
			name: form.doc.name,
			status: components.documentStatus(form.doc),
			fields: config.fields.map(([fieldname, label, fieldtype]) => [label, formatValue(form.doc[fieldname], fieldtype, form.doc)]),
			guidance: nextStep.label,
			guidanceTone: nextStep.tone,
		});
		tagFormSections(page);
	}

	function removePurchasingDecorations() {
		document.querySelectorAll(".pridict-purchasing-journey, .pridict-list-intro, .pridict-document-summary, .pridict-grid-scroll-note").forEach((element) => element.remove());
		document.querySelectorAll(".pridict-purchasing-page").forEach((element) => element.classList.remove("pridict-purchasing-page"));
		document.documentElement.classList.remove("pridict-purchasing-surface");
	}

	function apply(context) {
		if (!context.isPurchasing) {
			removePurchasingDecorations();
			return;
		}
		const page = visiblePage();
		if (!page) return;
		document.documentElement.classList.add("pridict-purchasing-surface");
		page.classList.add("pridict-purchasing-page");
		ensureJourney(page, context);
		ensureListIntro(page, context);
		enhanceListRows(page, context);
		ensureDocumentSummary(page, context);
	}

	const refresh = routeContext.onRouteChange((context) => {
		window.setTimeout(() => apply(context), 120);
		window.setTimeout(() => apply(context), 500);
	});
	const observer = new MutationObserver(() => refresh());
	observer.observe(document.documentElement, { childList: true, subtree: true });
	window.setTimeout(() => observer.disconnect(), 20000);

	function refreshForm(frm) {
		if (!documentConfig[frm?.doctype]) return;
		const context = routeContext.classify();
		window.setTimeout(() => apply(context), 40);
		window.setTimeout(() => apply(context), 220);
	}

	function refreshList() {
		const context = routeContext.classify();
		window.setTimeout(() => apply(context), 40);
		window.setTimeout(() => apply(context), 220);
	}

	namespace.purchasing = { apply, documentConfig, journey, refreshForm, refreshList };
})();
