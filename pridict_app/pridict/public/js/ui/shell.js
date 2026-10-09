(() => {
	const namespace = (window.pridict = window.pridict || {});
	const routeContext = namespace.routeContext;
	if (!routeContext) return;

	const navigation = [
		{ key: "overview", label: "Overview", route: "pridict-home", icon: "home" },
		{ key: "procurement", label: "Procurement", route: "pridict-procurement", icon: "shopping-cart", doctype: "Purchase Order" },
		{ key: "sales", label: "Sales & CRM", route: "pridict-sales", icon: "trend-up", doctype: "Sales Order" },
		{ key: "finance", label: "Finance", route: "pridict-finance", icon: "accounting", doctype: "GL Entry" },
		{ key: "inventory", label: "Inventory", route: "pridict-inventory", icon: "stock", doctype: "Stock Entry" },
		{ key: "assets", label: "Assets", route: "pridict-assets", icon: "assets", doctype: "Asset" },
		{ key: "manufacturing", label: "Manufacturing", route: "pridict-manufacturing", icon: "organization", doctype: "Work Order" },
		{ key: "projects", label: "Projects", route: "pridict-projects", icon: "project", doctype: "Project" },
		{ key: "quality", label: "Quality", route: "pridict-quality", icon: "quality", doctype: "Quality Inspection" },
		{ key: "support", label: "Support", route: "pridict-support", icon: "help", doctype: "Issue" },
		{ key: "website", label: "Website", route: "website", icon: "website", roles: ["Website Manager", "System Manager"] },
		{ key: "integrations", label: "Integrations", route: "pridict-integrations", icon: "integration", roles: ["System Manager"] },
		{ key: "governance", label: "Schema Intelligence", route: "schema-intelligence", icon: "branch", roles: ["Schema Reviewer", "System Manager"] },
		{ key: "process-intelligence", label: "Process Intelligence", route: "process-intelligence", icon: "branch", roles: ["Process Analyst", "System Manager"] },
		{ key: "decision-intelligence", label: "Decision Intelligence", route: "decision-intelligence", icon: "intelligence", roles: ["Purchase Manager", "Process Analyst", "System Manager"] },
		{ key: "administration", label: "Administration", route: "pridict-administration", icon: "setting-gear", roles: ["System Manager"] },
	];

	function hasRole(roles) {
		return !roles?.length || roles.some((role) => window.frappe?.user_roles?.includes(role));
	}

	function canRead(doctype) {
		if (!doctype || !window.frappe?.model?.can_read) return true;
		return Boolean(window.frappe.model.can_read(doctype));
	}

	function visibleNavigation() {
		return navigation.filter((item) => hasRole(item.roles) && canRead(item.doctype));
	}

	function icon(name) {
		try {
			return window.frappe?.utils?.icon ? window.frappe.utils.icon(name, "sm") : "";
		} catch (_error) {
			return "";
		}
	}

	function ensureShell() {
		if (window.frappe?.session?.user === "Guest" || !window.location.pathname.startsWith("/app")) {
			document.querySelector(".pridict-app-rail")?.remove();
			document.documentElement.classList.remove("pridict-shell-active", "pridict-shell-open");
			return null;
		}
		let shell = document.querySelector(".pridict-app-rail");
		if (!shell) {
			shell = document.createElement("aside");
			shell.className = "pridict-app-rail";
			shell.setAttribute("aria-label", __("Pridict navigation"));
			shell.innerHTML = `
				<div class="pridict-app-rail-brand">
					<img src="/assets/pridict/images/pridict-wordmark.svg" alt="${__("Pridict")}">
				</div>
				<nav>${visibleNavigation()
					.map(
						(item) => `<button type="button" class="pridict-app-rail-link" data-pridict-module="${item.key}" data-route="${item.route}">
							<span aria-hidden="true">${icon(item.icon)}</span><span>${__(item.label)}</span>
						</button>`
					)
					.join("")}</nav>
				<div class="pridict-app-rail-footer"><span>${__("Enterprise operations")}</span></div>
			`;
			shell.addEventListener("click", (event) => {
				const button = event.target.closest("[data-route]");
				if (!button) return;
				document.documentElement.classList.remove("pridict-shell-open");
				updateMobileToggle();
				window.frappe?.set_route?.(button.dataset.route);
			});
			document.body.appendChild(shell);
			const backdrop = document.createElement("button");
			backdrop.type = "button";
			backdrop.className = "pridict-shell-backdrop";
			backdrop.setAttribute("aria-label", __("Close navigation"));
			backdrop.addEventListener("click", () => {
				document.documentElement.classList.remove("pridict-shell-open");
				updateMobileToggle();
			});
			document.body.appendChild(backdrop);
		}
		document.documentElement.classList.add("pridict-shell-active");
		ensureMobileToggle();
		return shell;
	}

	function ensureMobileToggle() {
		const actions = document.querySelector(".navbar .navbar-nav:not(#navbar-breadcrumbs)");
		if (!actions || actions.querySelector(".pridict-shell-toggle-item")) return;
		const item = document.createElement("li");
		item.className = "nav-item pridict-shell-toggle-item";
		item.innerHTML = `<button type="button" class="btn-reset nav-link pridict-shell-toggle" aria-label="${__("Open navigation")}">${icon("menu")}</button>`;
		item.querySelector("button").addEventListener("click", () => {
			document.documentElement.classList.toggle("pridict-shell-open");
			updateMobileToggle();
		});
		actions.prepend(item);
		updateMobileToggle();
	}

	function updateMobileToggle() {
		const button = document.querySelector(".pridict-shell-toggle");
		if (!button) return;
		const isOpen = document.documentElement.classList.contains("pridict-shell-open");
		button.setAttribute("aria-expanded", String(isOpen));
		button.setAttribute("aria-label", isOpen ? __("Close navigation") : __("Open navigation"));
	}

	function activePageContainer() {
		return [...document.querySelectorAll(".page-container")].find((element) => element.offsetParent !== null) || null;
	}

	function labelForContext(context) {
		if (context.module === "procurement") return __("Procurement");
		return __(navigation.find((item) => item.key === context.module)?.label || "Overview");
	}

	function applyLayoutOwnership(page, context) {
		document.querySelectorAll(".page-container").forEach((container) => {
			container.classList.remove("pridict-workspace-route", "pridict-contextual-sidebar-route");
		});
		const hasNativeSidebar = Boolean(page.querySelector(".layout-side-section"));
		page.classList.toggle("pridict-workspace-route", context.surface === "workspace" && hasNativeSidebar);
		page.classList.toggle("pridict-contextual-sidebar-route", context.surface !== "workspace" && hasNativeSidebar);
	}

	function applyContext(context) {
		const shell = ensureShell();
		if (!shell) return;
		shell.querySelectorAll("[data-pridict-module]").forEach((button) => {
			button.classList.toggle("is-active", button.dataset.pridictModule === context.module);
			if (button.classList.contains("is-active")) button.setAttribute("aria-current", "page");
			else button.removeAttribute("aria-current");
		});
		document.documentElement.dataset.pridictModule = context.module;
		document.documentElement.dataset.pridictSurface = context.surface;

		const page = activePageContainer();
		if (!page) return;
		page.dataset.pridictModule = context.module;
		page.dataset.pridictSurface = context.surface;
		applyLayoutOwnership(page, context);
		const titleArea = page.querySelector(".page-head .title-area, .page-head .page-title");
		if (titleArea) {
			titleArea.querySelector(".pridict-page-context")?.remove();
		}
	}

	const refresh = routeContext.onRouteChange((context) => {
		document.documentElement.classList.remove("pridict-shell-open");
		updateMobileToggle();
		window.setTimeout(() => applyContext(context), 80);
		window.setTimeout(() => applyContext(context), 350);
	});
	const observer = new MutationObserver(() => refresh());
	observer.observe(document.documentElement, { childList: true, subtree: true });
	window.setTimeout(() => observer.disconnect(), 20000);
	document.addEventListener("keydown", (event) => {
		if (event.key === "Escape") {
			document.documentElement.classList.remove("pridict-shell-open");
			updateMobileToggle();
		}
	});

	namespace.shell = { applyContext, ensureShell, navigation };
})();
