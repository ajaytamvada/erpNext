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

		const [moduleLabel, moduleRoute] = moduleHomes[context.module] || moduleHomes.overview;
		const currentTitle = pageTitle(page, context);
		const currentRoute = context.route || context.parts.join("/") || context.slug;
		const atModuleHome = currentRoute === moduleRoute;
		const markup = atModuleHome
			? `<span aria-current="page">${surface.escape(__(moduleLabel))}</span>`
			: `<button type="button" data-route="${surface.escape(moduleRoute)}">${surface.escape(__(moduleLabel))}</button><span aria-hidden="true">/</span><span aria-current="page">${surface.escape(currentTitle)}</span>`;
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
