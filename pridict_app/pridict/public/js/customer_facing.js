(() => {
	const root = document.documentElement;
	const translate = window.__ || ((value) => value);
	const PORTAL_ROOTS = new Set([
		"addresses",
		"boms",
		"invoices",
		"issues",
		"material-requests",
		"orders",
		"project",
		"purchase-invoices",
		"purchase-orders",
		"quotations",
		"rfq",
		"shipments",
		"supplier-quotations",
		"tasks",
		"timesheets",
	]);
	const AUTH_ROOTS = new Set(["login", "signup", "update-password"]);

	function routeRoot() {
		return window.location.pathname.split("/").filter(Boolean)[0] || "home";
	}

	function classifySurface() {
		const route = routeRoot();
		if (AUTH_ROOTS.has(route)) return "auth";
		if (PORTAL_ROOTS.has(route)) return "portal";
		if (route === "pridict-notices" || route === "pridict-release-notes") return "information";
		if (document.querySelector(".web-form, .web-form-wrapper")) return "web-form";
		if (document.querySelector(".page-card-head .indicator, .error-page")) return "error";
		return "website";
	}

	function ensurePortalContext(surface) {
		const existing = document.querySelector(".pridict-public-context");
		if (surface !== "portal") {
			existing?.remove();
			return;
		}
		if (existing) return;

		const host = document.querySelector(".web-page-content, main, .page-content");
		if (!host) return;

		const context = document.createElement("section");
		context.className = "pridict-public-context";
		context.setAttribute("aria-label", "Pridict customer portal");
		context.innerHTML = `
			<span>${translate("Pridict customer portal")}</span>
			<strong>${translate("Your business documents and service activity")}</strong>
			<p>${translate("Use the available navigation and document actions to review records shared with your account.")}</p>
		`;
		host.prepend(context);
	}

	function applyCustomerFacingUi() {
		if (window.location.pathname.startsWith("/app")) return;

		const surface = classifySurface();
		root.classList.add("pridict-public");
		root.dataset.pridictSurface = surface;
		document.body?.setAttribute("data-pridict-surface", surface);

		document.querySelectorAll(".navbar-brand img, .navbar-home img").forEach((image) => {
			image.setAttribute("alt", "Pridict");
		});
		ensurePortalContext(surface);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", applyCustomerFacingUi, { once: true });
	} else {
		applyCustomerFacingUi();
	}

	const observer = new MutationObserver(() => applyCustomerFacingUi());
	observer.observe(document.documentElement, { childList: true, subtree: true });
	window.setTimeout(() => observer.disconnect(), 10000);
})();
