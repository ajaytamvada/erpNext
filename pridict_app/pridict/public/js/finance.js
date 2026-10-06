(() => {
	const namespace = (window.pridict = window.pridict || {});
	const routeContext = namespace.routeContext;
	const surface = namespace.surface;
	const components = namespace.components;
	if (!routeContext || !surface || !components) return;

	const documentConfig = {
		"Payment Entry": {
			description: "Record receipts, payments, transfers, references, deductions, and accounting dimensions.",
			presets: [
				["Receipts", { payment_type: "Receive" }],
				["Payments", { payment_type: "Pay" }],
				["Internal transfers", { payment_type: "Internal Transfer" }],
			],
			fields: [
				["payment_type", "Payment Type"],
				["posting_date", "Posting Date"],
				["party_type", "Party Type"],
				["party", "Party"],
				["mode_of_payment", "Mode of Payment"],
				["paid_amount", "Paid Amount", "Currency", "paid_from_account_currency"],
				["received_amount", "Received Amount", "Currency", "paid_to_account_currency"],
				["difference_amount", "Difference", "Currency", "paid_from_account_currency"],
			],
		},
		"Journal Entry": {
			description: "Review balanced debit and credit lines, references, dimensions, and posting details.",
			presets: [
				["Draft", { docstatus: 0 }],
				["Submitted", { docstatus: 1 }],
			],
			fields: [
				["voucher_type", "Entry Type"],
				["company", "Company"],
				["posting_date", "Posting Date"],
				["total_debit", "Total Debit", "Currency"],
				["total_credit", "Total Credit", "Currency"],
				["difference", "Difference", "Currency"],
			],
		},
	};
	const reportConfig = {
		"profit-and-loss-statement": ["Profit and Loss Statement", "Review income, expenses, and period profitability using the native financial statement engine."],
		"balance-sheet": ["Balance Sheet", "Review assets, liabilities, and equity while retaining native filters, charts, and drill-down behavior."],
		"cash-flow": ["Cash Flow", "Analyze operating, investing, and financing cash movements through the standard ERPNext report."],
		"general-ledger": ["General Ledger", "Trace posted accounting entries with the native filters, grouping, export, and voucher drill-down controls."],
		"accounts-receivable": ["Accounts Receivable", "Review customer balances, aging, due dates, and invoice-level drill-downs without changing report calculations."],
		"accounts-payable": ["Accounts Payable", "Review supplier balances, aging, due dates, and invoice-level drill-downs without changing report calculations."],
	};
	const treeConfig = {
		Account: ["Chart of Accounts", "Navigate the native account hierarchy, balances, groups, and ledger accounts for the selected company."],
		"Cost Center": ["Cost Center Tree", "Navigate the native cost-center hierarchy while preserving company filters and tree actions."],
	};
	const journey = [
		["Finance", "pridict-finance"],
		["Accounting", "accounting"],
		["Financial Reports", "financial-reports"],
		["Receivables", "receivables"],
		["Payables", "payables"],
		["Payment Entry", "payment-entry"],
		["Journal Entry", "journal-entry"],
		["Chart of Accounts", "Tree/Account", "account"],
	];

	function escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}

	function visiblePage() {
		return [...document.querySelectorAll(".page-container")].find((element) => element.offsetParent !== null) || null;
	}

	function formatValue(value, fieldtype, currency) {
		if (value === undefined || value === null || value === "") return __("Not set");
		if (fieldtype === "Currency") {
			const resolvedCurrency = currency || frappe.defaults.get_default("currency") || frappe.boot?.sysdefaults?.currency;
			return frappe.format(value, { fieldtype: "Currency", options: resolvedCurrency });
		}
		return escape(value);
	}

	function ensureJourney(page, context) {
		let nav = page.querySelector(".pridict-finance-journey");
		if (!nav) {
			nav = document.createElement("nav");
			nav.className = "pridict-finance-journey";
			nav.setAttribute("aria-label", __("Finance navigation"));
			nav.innerHTML = journey.map(([label, route]) => `<button type="button" data-route="${route}">${__(label)}</button>`).join("");
			nav.addEventListener("click", (event) => {
				const button = event.target.closest("[data-route]");
				if (button) frappe.set_route(button.dataset.route);
			});
			page.querySelector(".page-head")?.insertAdjacentElement("afterend", nav);
		}
		nav.querySelectorAll("button").forEach((button, index) => {
			const route = button.dataset.route;
			const activeSlug = journey[index][2] || route;
			const active = activeSlug === context.slug || (route === "financial-reports" && context.surface === "report");
			button.classList.toggle("is-active", active);
			if (active) button.setAttribute("aria-current", "page");
			else button.removeAttribute("aria-current");
		});
	}

	function ensureListIntro(page, context) {
		if (context.surface !== "list" || !documentConfig[context.doctype]) return;
		const config = documentConfig[context.doctype];
		let intro = page.querySelector(".pridict-finance-list-intro");
		if (!intro) {
			intro = document.createElement("section");
			intro.className = "pridict-finance-list-intro";
			page.querySelector(".page-body .container, .page-body")?.prepend(intro);
		}
		surface.render(intro, `
			<div><span>${__("Financial operations")}</span><strong>${__(context.doctype)}</strong><p>${__(config.description)}</p></div>
			<div class="pridict-finance-list-presets" aria-label="${__("Common filters")}">
				<button type="button" class="btn btn-default btn-sm" data-pridict-finance-list-all>${__("All")}</button>
				${(config.presets || []).map(([label, filters]) => `<button type="button" class="btn btn-default btn-sm" data-pridict-finance-list-filter="${escape(JSON.stringify(filters))}">${__(label)}</button>`).join("")}
			</div>
		`);
		intro.onclick = (event) => {
			const allButton = event.target.closest("[data-pridict-finance-list-all]");
			const filterButton = event.target.closest("[data-pridict-finance-list-filter]");
			if (!allButton && !filterButton) return;
			surface.applyListFilters(context.doctype, filterButton ? JSON.parse(filterButton.dataset.pridictFinanceListFilter) : {});
		};
	}

	function ensureReportIntro(page, context) {
		const config = reportConfig[context.slug];
		if (context.surface !== "report" || !config) return;
		surface.ensureIntro(page, "pridict-finance-report-intro", "Financial analysis", config[0], config[1]);
		page.querySelectorAll(".report-wrapper, .query-report, .report-view").forEach((element) => element.classList.add("pridict-finance-report-native"));
		page.querySelectorAll(".filter-section, .report-filter-area").forEach((element) => element.classList.add("pridict-finance-report-filters"));
		page.querySelectorAll(".report-summary").forEach((element) => element.classList.add("pridict-finance-report-summary"));
		page.querySelectorAll(".chart-container").forEach((element) => element.classList.add("pridict-finance-report-chart"));
		page.querySelectorAll(".datatable").forEach((element) => element.classList.add("pridict-finance-report-table"));
	}

	function ensureTreeIntro(page, context) {
		const config = treeConfig[context.doctype];
		if (context.surface !== "tree" || !config) return;
		surface.ensureIntro(page, "pridict-finance-tree-intro", "Financial structure", config[0], config[1]);
		page.querySelectorAll(".tree, .treeview, .tree-body").forEach((element) => element.classList.add("pridict-finance-tree-native"));
	}

	function getDocumentGuidance(doctype, doc) {
		if (doc.docstatus === 2) return ["muted", __("This document is cancelled. Use the native Amend action when available.")];
		if (doc.docstatus === 0) return ["draft", __("Complete the required fields and use the native Save or Submit action.")];
		if (doctype === "Payment Entry") return ["complete", __("Review allocated references, deductions, and the native accounting ledger links for this submitted payment.")];
		if (doctype === "Journal Entry") {
			if (Number(doc.difference || 0) !== 0) return ["attention", __("Debit and credit totals are not balanced. Correct the native account rows before submission.")];
			return ["complete", __("Debit and credit totals are balanced. Use native references and ledger links for audit review.")];
		}
		return ["muted", __("Use the native document actions for the next permitted step.")];
	}

	function tagFormSections(page, context) {
		page.querySelectorAll(".pridict-native-details, .pridict-native-items, .pridict-native-totals, .pridict-finance-section-details, .pridict-finance-section-lines, .pridict-finance-section-totals").forEach((section) => {
			section.classList.remove("pridict-native-details", "pridict-native-items", "pridict-native-totals", "pridict-finance-section-details", "pridict-finance-section-lines", "pridict-finance-section-totals");
		});
		let tableSection = null;
		if (context.doctype === "Payment Entry") {
			components.tagNativeFieldSections(page, ["payment_type"], "pridict-native-details", "pridict-finance-section-details");
			tableSection = components.tagNativeFieldSection(page, ["references"], "pridict-native-items", "pridict-finance-section-lines");
			components.tagNativeFieldSections(page, ["deductions", "difference_amount"], "pridict-native-totals", "pridict-finance-section-totals");
		} else if (context.doctype === "Journal Entry") {
			components.tagNativeFieldSections(page, ["voucher_type"], "pridict-native-details", "pridict-finance-section-details");
			tableSection = components.tagNativeFieldSection(page, ["accounts"], "pridict-native-items", "pridict-finance-section-lines");
			components.tagNativeFieldSections(page, ["total_debit"], "pridict-native-totals", "pridict-finance-section-totals");
		}
		components.tagNativeDocumentRegions(page, { grid: "pridict-finance-grid-native", timeline: "pridict-finance-timeline", linked: "pridict-finance-linked-documents" });
		page.querySelector(".form-sidebar")?.classList.add("pridict-finance-sidebar");
		components.ensureGridScrollNote(tableSection, "On smaller screens, swipe horizontally to review every accounting column.", "pridict-finance-grid-note");
		page.querySelectorAll(".page-actions button, .page-actions .btn").forEach((button) => {
			let kind = "utility";
			if (button.classList.contains("primary-action") || button.classList.contains("btn-primary")) kind = "primary";
			else if (button.classList.contains("btn-danger")) kind = "danger";
			button.dataset.pridictActionKind = kind;
		});
	}

	function ensureFormSummary(page, context) {
		const config = documentConfig[context.doctype];
		const form = window.cur_frm;
		if (context.surface !== "form" || !config || form?.doc?.doctype !== context.doctype) return;
		const [guidanceTone, guidance] = getDocumentGuidance(context.doctype, form.doc);
		components.ensureDocumentSummary({
			page,
			className: "pridict-finance-document-summary",
			eyebrow: "Financial document",
			name: form.doc.name,
			status: components.documentStatus(form.doc, [], { cancelledFirst: true, translateStatus: true }),
			fields: config.fields.map(([fieldname, label, fieldtype, currencyField]) => [label, formatValue(form.doc[fieldname], fieldtype, form.doc[currencyField] || frappe.defaults.get_user_default("Currency"))]),
			guidance,
			guidanceTone,
			guidanceClass: "pridict-finance-guidance",
		});
		page.querySelector(".page-actions")?.classList.add("pridict-finance-actions-native");
		tagFormSections(page, context);
	}

	function remove() {
		document.querySelectorAll(".pridict-finance-journey, .pridict-finance-list-intro, .pridict-finance-list-progress, .pridict-finance-report-intro, .pridict-finance-tree-intro, .pridict-finance-document-summary, .pridict-finance-grid-note").forEach((element) => element.remove());
		document.querySelectorAll(".pridict-finance-route").forEach((element) => element.classList.remove("pridict-finance-route"));
		document.querySelectorAll(".pridict-finance-report-native, .pridict-finance-report-filters, .pridict-finance-report-summary, .pridict-finance-report-chart, .pridict-finance-report-table, .pridict-finance-tree-native").forEach((element) => {
			element.classList.remove("pridict-finance-report-native", "pridict-finance-report-filters", "pridict-finance-report-summary", "pridict-finance-report-chart", "pridict-finance-report-table", "pridict-finance-tree-native");
		});
		document.querySelectorAll(".pridict-finance-section-details, .pridict-finance-section-lines, .pridict-finance-section-totals, .pridict-finance-linked-documents, .pridict-finance-sidebar, .pridict-finance-grid-native, .pridict-finance-timeline, .pridict-finance-actions-native").forEach((element) => {
			element.classList.remove("pridict-finance-section-details", "pridict-finance-section-lines", "pridict-finance-section-totals", "pridict-finance-linked-documents", "pridict-finance-sidebar", "pridict-finance-grid-native", "pridict-finance-timeline", "pridict-finance-actions-native");
		});
		document.documentElement.classList.remove("pridict-finance-surface");
	}

	function apply(context) {
		if (context.module !== "finance") {
			remove();
			return;
		}
		const page = visiblePage();
		if (!page) return;
		document.documentElement.classList.add("pridict-finance-surface");
		page.classList.add("pridict-finance-route");
		ensureJourney(page, context);
		ensureListIntro(page, context);
		ensureReportIntro(page, context);
		ensureTreeIntro(page, context);
		ensureFormSummary(page, context);
	}

	function refreshForm(frm) {
		if (!documentConfig[frm?.doctype]) return;
		const context = routeContext.classify();
		window.setTimeout(() => apply(context), 50);
		window.setTimeout(() => apply(context), 240);
	}

	const refresh = routeContext.onRouteChange((context) => {
		window.setTimeout(() => apply(context), 120);
		window.setTimeout(() => apply(context), 500);
	});
	const observer = new MutationObserver(() => refresh());
	observer.observe(document.documentElement, { childList: true, subtree: true });
	window.setTimeout(() => observer.disconnect(), 20000);

	namespace.finance = { apply, refreshForm };
})();
