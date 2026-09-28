(() => {
	const namespace = window.pridict || {};
	const routes = namespace.routeContext;
	const surface = namespace.surface;
	const components = namespace.components;
	if (!routes || !surface || !components) return;

	const quality = {
		"Quality Inspection": ["Inspection", "Review reference, item, template, readings, acceptance status, and native submission.", ["inspection_type", "reference_type", "reference_name", "item_code", "report_date", "status"]],
		"Quality Goal": ["Goal", "Track measurable quality objectives linked to procedures.", ["goal", "procedure", "date"]],
		"Quality Review": ["Review", "Review objectives, findings, procedure links, and follow-up status.", ["goal", "procedure", "date", "status"]],
		"Quality Action": ["Action", "Track corrective resolutions arising from goals and reviews.", ["goal", "review", "procedure", "date", "status"]],
		"Non Conformance": ["Non-conformance", "Record findings, procedure context, corrective action, preventive action, and closure.", ["subject", "procedure", "status"]],
	};
	const support = {
		Issue: ["Issue", "Manage customer communication, ownership, priority, SLA timing, response, and resolution.", ["subject", "customer_name", "status", "priority", "issue_type", "opening_date", "agreement_status", "sla_resolution_by"]],
		"Service Level Agreement": ["Service level", "Maintain priority response and resolution commitments, calendars, and pause rules.", ["service_level", "enabled", "default_priority", "start_date", "end_date"]],
		"Warranty Claim": ["Warranty claim", "Track customer, item, warranty status, issue details, service work, and resolution.", ["customer_name", "item_code", "status", "warranty_amc_status", "complaint_date", "resolution_date"]],
	};
	const reports = new Map([
		["review", "Quality Review"],
		["issue-analytics", "Issue Analytics"],
		["issue-summary", "Issue Summary"],
		["first-response-time-for-issues", "First Response Time for Issues"],
		["support-hour-distribution", "Support Hour Distribution"],
	]);
	const journeys = {
		quality: [["Quality", "pridict-quality"], ["Inspection", "quality-inspection", "Quality Inspection"], ["Goals", "quality-goal", "Quality Goal"], ["Reviews", "quality-review", "Quality Review"], ["Actions", "quality-action", "Quality Action"], ["Non-conformance", "non-conformance", "Non Conformance"]],
		support: [["Support", "pridict-support"], ["Issues", "issue", "Issue"], ["SLA", "service-level-agreement", "Service Level Agreement"], ["Warranty", "warranty-claim", "Warranty Claim"]],
	};

	function fieldLabel(doctype, fieldname) {
		return frappe.meta.get_docfield(doctype, fieldname)?.label || fieldname.replaceAll("_", " ");
	}

	function apply(context) {
		const module = context.isQuality ? "quality" : context.isSupport ? "support" : null;
		if (!module) {
			surface.remove(".pridict-domain-journey,.pridict-domain-intro,.pridict-domain-summary");
			return;
		}
		const page = surface.visiblePage();
		if (!page) return;
		const journey = journeys[module];
		const nav = surface.ensureJourney(page, { className: "pridict-domain-journey", label: `${module} navigation`, items: journey });
		nav.querySelectorAll("button").forEach((button, index) => {
			const active = (journey[index][2] || journey[index][0]) === context.doctype || button.dataset.route === context.slug;
			button.classList.toggle("is-active", active);
		});
		if (context.surface === "report" && reports.has(context.slug)) {
			surface.ensureIntro(page, "pridict-domain-intro", module === "quality" ? "Quality analysis" : "Support analysis", reports.get(context.slug), "Use native filters, calculations, exports, and drill-down links within the Pridict frame.");
			return;
		}
		const config = (module === "quality" ? quality : support)[context.doctype];
		if (!config) return;
		if (context.surface === "list") {
			surface.ensureIntro(page, "pridict-domain-intro", module === "quality" ? "Quality operations" : "Customer service", context.doctype, config[1]);
		}
		if (context.surface === "form" && window.cur_frm?.doc?.doctype === context.doctype) {
			const doc = window.cur_frm.doc;
			components.ensureDocumentSummary({
				page,
				className: "pridict-domain-summary",
				eyebrow: config[0],
				name: doc.name,
				status: components.documentStatus(doc, ["repair_status"]),
				fields: components.safeDocumentFields(doc, config[2], (field) => fieldLabel(context.doctype, field)),
			});
			components.tagNativeDocumentRegions(page, {
				grid: "pridict-domain-grid",
				timeline: "pridict-domain-timeline",
				linked: "pridict-domain-linked",
				linkedSelectors: [".communication-timeline"],
			});
		}
	}

	function refreshForm() {
		const context = routes.classify();
		setTimeout(() => apply(context), 60);
		setTimeout(() => apply(context), 260);
	}

	const refresh = routes.onRouteChange((context) => {
		setTimeout(() => apply(context), 120);
		setTimeout(() => apply(context), 500);
	});
	const observer = new MutationObserver(() => refresh());
	observer.observe(document.documentElement, { childList: true, subtree: true });
	window.setTimeout(() => observer.disconnect(), 20000);
	namespace.qualitySupport = { apply, refreshForm };
})();
