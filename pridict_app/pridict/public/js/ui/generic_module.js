(() => {
	const namespace = (window.pridict = window.pridict || {});
	const routes = namespace.routeContext;
	const surface = namespace.surface;
	const components = namespace.components;
	if (!routes || !surface || !components) return;

	const modules = {
		procurement: ["Procurement", "pridict-procurement", "Purchasing operations"],
		finance: ["Finance", "pridict-finance", "Financial operations"],
		sales: ["Sales & CRM", "pridict-sales", "Customer and revenue operations"],
		inventory: ["Inventory", "pridict-inventory", "Stock and fulfilment operations"],
		assets: ["Assets", "pridict-assets", "Asset lifecycle operations"],
		manufacturing: ["Manufacturing", "pridict-manufacturing", "Production operations"],
		projects: ["Projects", "pridict-projects", "Delivery operations"],
		quality: ["Quality", "pridict-quality", "Quality management"],
		support: ["Support", "pridict-support", "Customer service"],
		administration: ["Administration", "pridict-administration", "System operations"],
		integrations: ["Integrations", "pridict-integrations", "Connected services"],
	};
	const specificSurfaceSelector = [
		".pridict-purchasing-journey", ".pridict-list-intro", ".pridict-document-summary",
		".pridict-finance-journey", ".pridict-finance-list-intro", ".pridict-finance-report-intro", ".pridict-finance-tree-intro", ".pridict-finance-document-summary",
		".pridict-sales-journey", ".pridict-sales-list-intro", ".pridict-sales-document-summary",
		".pridict-inventory-journey", ".pridict-inventory-list-intro", ".pridict-inventory-report-intro", ".pridict-inventory-tree-intro", ".pridict-inventory-document-summary",
		".pridict-assets-journey", ".pridict-assets-list-intro", ".pridict-assets-report-intro", ".pridict-assets-document-summary",
		".pridict-manufacturing-journey", ".pridict-manufacturing-intro", ".pridict-manufacturing-report-intro", ".pridict-manufacturing-summary",
		".pridict-projects-journey", ".pridict-projects-list-intro", ".pridict-projects-report-intro", ".pridict-projects-planning-intro", ".pridict-projects-summary",
		".pridict-domain-journey", ".pridict-domain-intro", ".pridict-domain-summary",
		".pridict-admin-journey", ".pridict-admin-intro", ".pridict-admin-summary",
	].join(",");

	function displayTitle(context) {
		if (context.doctype) return context.doctype;
		if (context.parts[1]) return context.parts[1];
		return context.slug.replaceAll("-", " ");
	}

	function ensureJourney(page, context, config) {
		const currentRoute = context.route || context.parts.join("/") || context.slug;
		const nav = surface.ensureJourney(page, {
			className: "pridict-generic-journey",
			label: `${config[0]} navigation`,
			items: [[config[0], config[1]], [displayTitle(context), currentRoute]],
		});
		nav.querySelectorAll("button").forEach((button, index) => button.classList.toggle("is-active", index === 1));
	}

	function apply(context) {
		const config = modules[context.module];
		if (!config || context.slug.startsWith("pridict-")) {
			surface.remove(".pridict-generic-journey,.pridict-generic-intro,.pridict-generic-summary");
			return;
		}
		const page = surface.visiblePage();
		if (!page) return;
		if (page.querySelector(specificSurfaceSelector)) {
			surface.remove(".pridict-generic-journey,.pridict-generic-intro,.pridict-generic-summary");
			return;
		}
		ensureJourney(page, context, config);

		const title = displayTitle(context);
		if (context.surface === "list") {
			surface.remove(".pridict-generic-intro");
		} else if (["report", "workspace", "page", "tree"].includes(context.surface)) {
			const description = context.surface === "report"
				? "Use native filters, calculations, exports, and drill-down links within the Pridict frame."
				: "Use the complete native records, controls, permissions, and actions within the shared Pridict layout.";
			surface.ensureIntro(page, "pridict-generic-intro", config[2], title, description);
		}
		if (context.surface === "form" && window.cur_frm?.doc?.doctype === context.doctype) {
			const doc = window.cur_frm.doc;
			components.ensureDocumentSummary({
				page,
				className: "pridict-generic-summary",
				eyebrow: config[2],
				name: doc.name,
				status: components.documentStatus(doc),
				guidance: "Native fields, permissions, validation, links, and document actions are preserved.",
			});
			components.tagNativeDocumentRegions(page, { grid: "pridict-generic-grid", timeline: "pridict-generic-timeline", linked: "pridict-generic-linked-documents" });
		}
	}

	const refresh = routes.onRouteChange((context) => {
		setTimeout(() => apply(context), 160);
		setTimeout(() => apply(context), 540);
	});
	const observer = new MutationObserver(() => refresh());
	observer.observe(document.documentElement, { childList: true, subtree: true });
	window.setTimeout(() => observer.disconnect(), 20000);
	namespace.genericModule = { apply };
})();
