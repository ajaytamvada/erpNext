(() => {
	const namespace = (window.pridict = window.pridict || {});
	const routeContext = namespace.routeContext;
	const surface = namespace.surface;
	const components = namespace.components;
	if (!routeContext || !surface || !components) return;

	const documentConfig = {
		Lead: {
			description: "Qualify incoming prospects while preserving assignments, communications, and conversion actions.",
			presets: [["Open", { status: ["in", ["Lead", "Open", "Replied", "Interested"]] }], ["Converted", { status: "Converted" }]],
			fields: [["lead_name", "Lead"], ["company_name", "Organization"], ["status", "Status"], ["lead_owner", "Owner"]],
		},
		Opportunity: {
			description: "Track qualified demand, probability, expected close, customer requirements, and quotation progress.",
			presets: [["Open", { status: "Open" }], ["Replied", { status: "Replied" }], ["Converted", { status: "Converted" }]],
			fields: [["party_name", "Customer or Lead"], ["sales_stage", "Sales Stage"], ["probability", "Probability", "Percent"], ["expected_closing", "Expected Closing"], ["opportunity_amount", "Opportunity Amount", "Currency", "currency"], ["status", "Status"]],
		},
		Quotation: {
			description: "Prepare commercial offers with native pricing, taxes, validity, terms, and order conversion.",
			presets: [["Active", { docstatus: 1, status: ["in", ["Open", "Replied", "Partially Ordered"]] }], ["Expired", { status: "Expired" }]],
			fields: [["party_name", "Customer or Lead"], ["transaction_date", "Quotation Date"], ["valid_till", "Valid Till"], ["grand_total", "Grand Total", "Currency", "currency"], ["status", "Status"]],
		},
		"Sales Order": {
			description: "Control customer commitments, delivery progress, billing progress, and order value.",
			presets: [["To deliver", { docstatus: 1, per_delivered: ["<", 100], status: ["!=", "Closed"] }], ["To bill", { docstatus: 1, per_billed: ["<", 100], status: ["!=", "Closed"] }]],
			fields: [["customer_name", "Customer"], ["transaction_date", "Order Date"], ["delivery_date", "Delivery Date"], ["grand_total", "Grand Total", "Currency", "currency"], ["per_delivered", "Delivered", "Percent"], ["per_billed", "Billed", "Percent"]],
		},
		"Delivery Note": {
			description: "Record customer fulfillment while preserving stock posting, returns, installation, transport, and billing actions.",
			presets: [["To bill", { docstatus: 1, per_billed: ["<", 100] }], ["Returns", { is_return: 1 }]],
			fields: [["customer_name", "Customer"], ["posting_date", "Posting Date"], ["transporter_name", "Transporter"], ["grand_total", "Grand Total", "Currency", "currency"], ["per_billed", "Billed", "Percent"], ["status", "Status"]],
		},
		"Sales Invoice": {
			description: "Manage customer billing, delivery references, taxes, payment status, and accounting impact.",
			presets: [["Outstanding", { docstatus: 1, outstanding_amount: [">", 0] }], ["Overdue", { status: "Overdue" }]],
			fields: [["customer_name", "Customer"], ["posting_date", "Posting Date"], ["due_date", "Due Date"], ["grand_total", "Grand Total", "Currency", "currency"], ["outstanding_amount", "Outstanding", "Currency", "currency"], ["status", "Status"]],
		},
	};
	const journey = [
		["Sales & CRM", "pridict-sales"],
		["Lead", "lead"],
		["Opportunity", "opportunity"],
		["Quotation", "quotation"],
		["Sales Order", "sales-order"],
		["Delivery Note", "delivery-note"],
		["Sales Invoice", "sales-invoice"],
	];

	function escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}

	function visiblePage() {
		return [...document.querySelectorAll(".page-container")].find((element) => element.offsetParent !== null) || null;
	}

	function formatValue(value, fieldtype, currency) {
		if (value === undefined || value === null || value === "") return __("Not set");
		if (fieldtype === "Currency") return frappe.format(value, { fieldtype: "Currency", options: currency || frappe.boot?.sysdefaults?.currency });
		if (fieldtype === "Percent") return `${Number(value || 0).toFixed(0)}%`;
		return escape(value);
	}

	function ensureJourney(page, context) {
		let nav = page.querySelector(".pridict-sales-journey");
		if (!nav) {
			nav = document.createElement("nav");
			nav.className = "pridict-sales-journey";
			nav.setAttribute("aria-label", __("Sales journey"));
			nav.innerHTML = journey.map(([label, route]) => `<button type="button" data-route="${route}" data-doctype="${label === "Sales & CRM" ? "" : label}">${__(label)}</button>`).join("");
			nav.addEventListener("click", (event) => {
				const button = event.target.closest("[data-route]");
				if (button) frappe.set_route(button.dataset.route);
			});
			page.querySelector(".page-head")?.insertAdjacentElement("afterend", nav);
		}
		nav.querySelectorAll("button").forEach((button) => {
			const active = button.dataset.doctype ? button.dataset.doctype === context.doctype : context.slug === "pridict-sales";
			button.classList.toggle("is-active", active);
			if (active) button.setAttribute("aria-current", "page");
			else button.removeAttribute("aria-current");
		});
	}

	function ensureListIntro(page, context) {
		const config = documentConfig[context.doctype];
		if (context.surface !== "list" || !config) return;
		let intro = page.querySelector(".pridict-sales-list-intro");
		if (!intro) {
			intro = document.createElement("section");
			intro.className = "pridict-sales-list-intro";
			page.querySelector(".page-body .container, .page-body")?.prepend(intro);
		}
		surface.render(intro, `<div><span>${__("Customer operations")}</span><strong>${__(context.doctype)}</strong><p>${__(config.description)}</p></div><div class="pridict-sales-list-presets"><button type="button" class="btn btn-default btn-sm" data-sales-list-all>${__("All")}</button>${config.presets.map(([label, filters]) => `<button type="button" class="btn btn-default btn-sm" data-sales-list-filter="${escape(JSON.stringify(filters))}">${__(label)}</button>`).join("")}</div>`);
		intro.onclick = (event) => {
			const filter = event.target.closest("[data-sales-list-filter]");
			const all = event.target.closest("[data-sales-list-all]");
			if (!filter && !all) return;
			frappe.route_options = filter ? JSON.parse(filter.dataset.salesListFilter) : {};
			frappe.set_route("List", context.doctype, "List");
		};
	}

	function progressValues(doctype, doc) {
		if (doctype === "Opportunity") return [[__("Probability"), doc.probability]];
		if (doctype === "Sales Order") return [[__("Delivered"), doc.per_delivered], [__("Billed"), doc.per_billed]];
		if (doctype === "Delivery Note") return [[__("Billed"), doc.per_billed]];
		if (doctype === "Sales Invoice") {
			const total = Math.abs(Number(doc.base_grand_total || doc.grand_total || 0));
			return [[__("Outstanding"), total ? (Math.abs(Number(doc.outstanding_amount || 0)) / total) * 100 : 0]];
		}
		return [];
	}

	function enhanceListRows(page, context) {
		if (context.surface !== "list" || !window.cur_list?.data?.length) return;
		window.cur_list.data.forEach((doc) => {
			const values = progressValues(context.doctype, doc).filter(([, value]) => value !== undefined && value !== null);
			if (!values.length) return;
			const row = page.querySelector(`[data-name="${window.CSS?.escape ? CSS.escape(doc.name) : doc.name}"]`);
			if (!row) return;
			let progress = row.querySelector(".pridict-sales-list-progress");
			if (!progress) {
				progress = document.createElement("div");
				progress.className = "pridict-sales-list-progress";
				(row.querySelector(".level-right") || row).appendChild(progress);
			}
			const markup = values.map(([label, value]) => {
				const percentage = Math.max(0, Math.min(100, Number(value) || 0));
				return `<span><i><b style="width:${percentage}%"></b></i><em>${escape(label)} ${percentage.toFixed(0)}%</em></span>`;
			}).join("");
			surface.render(progress, markup);
		});
	}

	function documentGuidance(doctype, doc) {
		if (doc.docstatus === 2) return ["muted", __("This document is cancelled. Use the native Amend action when available.")];
		if (doc.docstatus === 0 && !["Lead", "Opportunity"].includes(doctype)) return ["draft", __("Complete required fields, review customer and item details, then use native Save or Submit.")];
		if (doctype === "Lead") return doc.status === "Converted" ? ["complete", __("This lead is converted. Continue through the linked customer or opportunity records.")] : ["attention", __("Review qualification, ownership, communications, and the native conversion actions.")];
		if (doctype === "Opportunity") return [doc.status === "Converted" ? "complete" : "attention", doc.status === "Converted" ? __("This opportunity is converted. Review linked quotations and customer documents.") : __("Review probability, expected closing, requirements, and the native quotation action.")];
		if (doctype === "Quotation") return doc.status === "Ordered" ? ["complete", __("This quotation is ordered. Review linked sales orders in the native dashboard.")] : ["attention", __("Review validity, pricing, taxes, terms, and the native order conversion action.")];
		if (doctype === "Sales Order") {
			const delivery = Number(doc.per_delivered || 0) < 100;
			const billing = Number(doc.per_billed || 0) < 100;
			if (delivery && billing) return ["attention", __("This order still requires delivery and billing.")];
			if (delivery) return ["attention", __("This order still has quantities to deliver.")];
			if (billing) return ["attention", __("Delivery is complete, but billing remains incomplete.")];
			return ["complete", __("Delivery and billing progress are complete.")];
		}
		if (doctype === "Delivery Note") return Number(doc.per_billed || 0) < 100 ? ["attention", __("This delivery still has value to bill using native document actions.")] : ["complete", __("This delivery is fully billed. Review stock and invoice links in the native dashboard.")];
		if (doctype === "Sales Invoice") return Number(doc.outstanding_amount || 0) > 0 ? ["attention", __("This invoice has an outstanding balance. Use native payment and reminder actions.")] : ["complete", __("This invoice has no outstanding balance.")];
		return ["muted", __("Use native document actions for the next permitted step.")];
	}

	function tagFormSections(page, context) {
		page.querySelectorAll(".pridict-native-details, .pridict-native-items, .pridict-native-totals, .pridict-sales-section-details, .pridict-sales-section-items, .pridict-sales-section-totals").forEach((section) => {
			section.classList.remove("pridict-native-details", "pridict-native-items", "pridict-native-totals", "pridict-sales-section-details", "pridict-sales-section-items", "pridict-sales-section-totals");
		});
		const detailField = ["lead_name", "opportunity_from", "quotation_to", "customer"].find((fieldname) => page.querySelector(`[data-fieldname="${fieldname}"]`));
		if (detailField) components.tagNativeFieldSection(page, [detailField], "pridict-native-details", "pridict-sales-section-details");
		const itemSection = components.tagNativeFieldSection(page, ["items"], "pridict-native-items", "pridict-sales-section-items");
		components.tagNativeFieldSections(page, ["taxes", "grand_total"], "pridict-native-totals", "pridict-sales-section-totals");
		components.tagNativeDocumentRegions(page, { grid: "pridict-sales-grid-native", timeline: "pridict-sales-timeline", linked: "pridict-sales-linked-documents" });
		page.querySelector(".page-actions")?.classList.add("pridict-sales-actions-native");
		page.querySelector(".form-sidebar")?.classList.add("pridict-sales-sidebar");
		components.ensureGridScrollNote(itemSection, "On smaller screens, swipe horizontally to review every item column.", "pridict-sales-grid-note");
	}

	function ensureFormSummary(page, context) {
		const config = documentConfig[context.doctype];
		const form = window.cur_frm;
		if (context.surface !== "form" || !config || form?.doc?.doctype !== context.doctype) return;
		const [tone, guidance] = documentGuidance(context.doctype, form.doc);
		components.ensureDocumentSummary({
			page,
			className: "pridict-sales-document-summary",
			eyebrow: "Customer document",
			name: form.doc.name,
			status: components.documentStatus(form.doc),
			fields: config.fields.map(([fieldname, label, fieldtype, currencyField]) => [label, formatValue(form.doc[fieldname], fieldtype, form.doc[currencyField])]),
			guidance,
			guidanceTone: tone,
			guidanceClass: "pridict-sales-guidance",
		});
		tagFormSections(page, context);
	}

	function remove() {
		document.querySelectorAll(".pridict-sales-journey, .pridict-sales-list-intro, .pridict-sales-list-progress, .pridict-sales-document-summary, .pridict-sales-grid-note").forEach((element) => element.remove());
		document.querySelectorAll(".pridict-sales-route").forEach((element) => element.classList.remove("pridict-sales-route"));
		document.querySelectorAll(".pridict-sales-section-details, .pridict-sales-section-items, .pridict-sales-section-totals, .pridict-sales-linked-documents, .pridict-sales-actions-native, .pridict-sales-sidebar, .pridict-sales-timeline, .pridict-sales-grid-native").forEach((element) => {
			element.classList.remove("pridict-sales-section-details", "pridict-sales-section-items", "pridict-sales-section-totals", "pridict-sales-linked-documents", "pridict-sales-actions-native", "pridict-sales-sidebar", "pridict-sales-timeline", "pridict-sales-grid-native");
		});
		document.documentElement.classList.remove("pridict-sales-surface");
	}

	function apply(context) {
		if (!context.isSales) {
			remove();
			return;
		}
		const page = visiblePage();
		if (!page) return;
		document.documentElement.classList.add("pridict-sales-surface");
		page.classList.add("pridict-sales-route");
		ensureJourney(page, context);
		ensureListIntro(page, context);
		enhanceListRows(page, context);
		ensureFormSummary(page, context);
	}

	function refreshForm(frm) {
		if (!documentConfig[frm?.doctype]) return;
		const context = routeContext.classify();
		window.setTimeout(() => apply(context), 40);
		window.setTimeout(() => apply(context), 240);
	}

	const refresh = routeContext.onRouteChange((context) => {
		window.setTimeout(() => apply(context), 120);
		window.setTimeout(() => apply(context), 500);
	});
	const observer = new MutationObserver(() => refresh());
	observer.observe(document.documentElement, { childList: true, subtree: true });
	window.setTimeout(() => observer.disconnect(), 20000);

	namespace.sales = { apply, refreshForm };
})();
