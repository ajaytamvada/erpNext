(() => {
	const namespace = (window.pridict = window.pridict || {});
	const routes = namespace.routeContext;
	const surface = namespace.surface;
	if (!routes || !surface) return;

	const moduleHomes = {
		overview: ["Overview", "pridict-home"],
		procurement: ["Procurement", "pridict-procurement"],
		finance: ["Finance", "pridict-finance"],
		sales: ["Sales & CRM", "pridict-sales"],
		inventory: ["Inventory", "pridict-inventory"],
		assets: ["Assets", "pridict-assets"],
		manufacturing: ["Manufacturing", "pridict-manufacturing"],
		projects: ["Projects", "pridict-projects"],
		quality: ["Quality", "pridict-quality"],
		support: ["Support", "pridict-support"],
		website: ["Website", "website"],
		integrations: ["Integrations", "pridict-integrations"],
		governance: ["Schema Intelligence", "schema-intelligence"],
		"process-intelligence": ["Process Intelligence", "process-intelligence"],
		"decision-intelligence": ["Decision Intelligence", "decision-intelligence"],
		administration: ["Administration", "pridict-administration"],
	};

	function pageTitle(page, context) {
		const title = page.querySelector(".page-head .title-text, .page-head .page-title h3, .page-head h3")?.textContent?.trim();
		if (title) return title;
		if (context.doctype) return context.doctype;
		if (context.parts[1]) return String(context.parts[1]).replaceAll("-", " ");
		return String(context.slug || __("Overview")).replaceAll("-", " ");
	}

	function ensureBreadcrumbs(page, context) {
		const titleArea = page.querySelector(".page-head .title-area, .page-head .page-title");
		if (!titleArea) return;
		titleArea.classList.add("pridict-has-breadcrumbs");
		titleArea.querySelector(".pridict-page-context")?.remove();

		let breadcrumbs = titleArea.querySelector(".pridict-page-breadcrumbs");
		if (!breadcrumbs) {
			breadcrumbs = document.createElement("nav");
			breadcrumbs.className = "pridict-page-breadcrumbs";
			breadcrumbs.setAttribute("aria-label", __("Breadcrumbs"));
			breadcrumbs.addEventListener("click", (event) => {
				const button = event.target.closest("[data-route]");
				if (button) window.frappe?.set_route?.(button.dataset.route);
			});
			titleArea.prepend(breadcrumbs);
		}

		const sidebarBtn = titleArea.querySelector(".sidebar-toggle-btn");
		if (sidebarBtn) {
			titleArea.prepend(breadcrumbs);
			titleArea.prepend(sidebarBtn);
		}

		const [moduleLabel, moduleRoute] = moduleHomes[context.module] || moduleHomes.overview;
		const currentTitle = pageTitle(page, context);
		const currentRoute = context.route || context.parts.join("/") || context.slug;
		const normTitle = routes.normalize(currentTitle);
		const normModule = routes.normalize(moduleLabel);
		const atModuleHome = currentRoute === moduleRoute || normTitle === normModule ||
			(context.surface === "page" && ["process-intelligence", "decision-intelligence", "schema-intelligence", "pridict-home"].includes(context.slug));

		if (atModuleHome) {
			breadcrumbs.style.display = "none";
			surface.render(breadcrumbs, "");
			return;
		}

		breadcrumbs.style.display = "inline-flex";
		const crumbs = [];
		crumbs.push(`<button type="button" class="pridict-breadcrumb-link" data-route="${surface.escape(moduleRoute)}">${surface.escape(__(moduleLabel))}</button>`);

		if ((context.surface === "form" || (context.parts.length > 2 && context.doctype)) && context.doctype) {
			const doctypeRoute = context.slug || `List/${context.doctype}`;
			if (normTitle !== routes.normalize(context.doctype)) {
				crumbs.push(`<button type="button" class="pridict-breadcrumb-link" data-route="${surface.escape(doctypeRoute)}">${surface.escape(__(context.doctype))}</button>`);
			}
		}

		const markup = crumbs.map((crumb) => `${crumb}<span class="pridict-breadcrumb-separator" aria-hidden="true">/</span>`).join("");
		surface.render(breadcrumbs, markup);
	}

	function decorateActions(page) {
		const actions = page.querySelector(".page-actions");
		if (!actions) return;
		actions.classList.add("pridict-page-actions");
		actions.querySelectorAll("button, .btn").forEach((button) => {
			button.classList.add("pridict-page-action");
			button.classList.toggle("is-primary", button.classList.contains("primary-action") || button.classList.contains("btn-primary"));
			button.classList.toggle("is-danger", button.classList.contains("btn-danger"));
		});
	}

	function apply(context = routes.classify()) {
		const page = surface.visiblePage();
		if (!page) return;
		const pageHead = page.querySelector(".page-head");
		if (!pageHead) return;
		pageHead.classList.add("pridict-page-head");
		ensureBreadcrumbs(page, context);
		decorateActions(page);
	}

	let scheduled;
	function schedule(context = routes.classify()) {
		window.clearTimeout(scheduled);
		scheduled = window.setTimeout(() => apply(context), 60);
	}

	routes.onRouteChange((context) => {
		window.setTimeout(() => apply(context), 80);
		window.setTimeout(() => apply(context), 320);
	});
	new MutationObserver(() => schedule()).observe(document.documentElement, { childList: true, subtree: true });
	namespace.pageHeader = { apply, decorateActions, ensureBreadcrumbs };
})();
