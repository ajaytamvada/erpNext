const PRIDICT_ROOT_CLASS = "pridict-ui";
const PRIDICT_LOGO_PATH = "/assets/pridict/images/pridict-wordmark.svg";
const UPSTREAM_HELP_HOSTS = new Set([
	"docs.erpnext.com",
	"docs.frappe.io",
	"discuss.frappe.io",
	"erpnext.com",
	"frappe.io",
	"frappecloud.com",
	"github.com",
]);

function updateThemeToggle(button) {
	const isDark = document.documentElement.getAttribute("data-theme") === "dark";
	button.textContent = isDark ? "☀" : "☾";
	button.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
	button.setAttribute("title", isDark ? "Switch to light theme" : "Switch to dark theme");
}

function toggleTheme(button) {
	const root = document.documentElement;
	const nextTheme = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
	root.setAttribute("data-theme-mode", nextTheme);

	if (window.frappe?.ui?.set_theme) {
		window.frappe.ui.set_theme(nextTheme);
	} else {
		root.setAttribute("data-theme", nextTheme);
	}

	updateThemeToggle(button);

	if (window.frappe?.xcall && window.frappe.session?.user !== "Guest") {
		window.frappe
			.xcall("frappe.core.doctype.user.user.switch_theme", {
				theme: nextTheme === "dark" ? "Dark" : "Light",
			})
			.catch(() => undefined);
	}
}

function ensureThemeToggle() {
	const navbarActions = document.querySelector(".navbar .navbar-nav:not(#navbar-breadcrumbs)");
	if (!navbarActions || navbarActions.querySelector(".pridict-theme-toggle-item")) {
		return;
	}

	const item = document.createElement("li");
	item.className = "nav-item pridict-theme-toggle-item";

	const button = document.createElement("button");
	button.type = "button";
	button.className = "btn-reset nav-link pridict-theme-toggle";
	button.addEventListener("click", () => toggleTheme(button));
	updateThemeToggle(button);

	item.appendChild(button);
	navbarActions.prepend(item);
}

function removeUpstreamContextualHelp() {
	if (!window.frappe?.help?.help_links) {
		return;
	}

	Object.keys(window.frappe.help.help_links).forEach((route) => {
		window.frappe.help.help_links[route] = window.frappe.help.help_links[route].filter((item) => {
			if (!item?.url) {
				return true;
			}
			try {
				const url = new URL(item.url, window.location.origin);
				return !UPSTREAM_HELP_HOSTS.has(url.hostname.toLowerCase());
			} catch (_error) {
				return true;
			}
		});
	});
}

function removeUpstreamTourLinks() {
	if (!window.frappe?.tour) {
		return;
	}

	Object.values(window.frappe.tour).forEach((steps) => {
		if (!Array.isArray(steps)) {
			return;
		}
		steps.forEach((step) => {
			if (!step?.description || !/<a\b/i.test(step.description)) {
				return;
			}
			const container = document.createElement("div");
			container.innerHTML = step.description;
			container.querySelectorAll("a[href]").forEach((link) => {
				try {
					const url = new URL(link.href, window.location.origin);
					if (UPSTREAM_HELP_HOSTS.has(url.hostname.toLowerCase())) {
						link.replaceWith(document.createTextNode(link.textContent || ""));
					}
				} catch (_error) {
					// Preserve malformed or relative links owned by the active site.
				}
			});
			step.description = container.innerHTML;
		});
	});
}

function enablePridictUi() {
	document.documentElement.classList.add(PRIDICT_ROOT_CLASS);

	const navbarHome = document.querySelector(".navbar-home");
	const navbarLogo = navbarHome?.querySelector("img");
	if (navbarLogo) {
		if (navbarLogo.getAttribute("src") !== PRIDICT_LOGO_PATH) {
			navbarLogo.setAttribute("src", PRIDICT_LOGO_PATH);
		}
		navbarLogo.setAttribute("alt", "Pridict");
	}
	if (navbarHome && window.frappe?.session?.user && window.frappe.session.user !== "Guest") {
		navbarHome.setAttribute("href", "/app/pridict-home");
		navbarHome.setAttribute("title", "Pridict Executive Home");
	}

	ensureThemeToggle();
	removeUpstreamContextualHelp();
	removeUpstreamTourLinks();
}

if (document.readyState === "loading") {
	document.addEventListener("DOMContentLoaded", enablePridictUi, { once: true });
} else {
	enablePridictUi();
}

const navbarObserver = new MutationObserver(enablePridictUi);
navbarObserver.observe(document.documentElement, { childList: true, subtree: true });
window.setTimeout(() => navbarObserver.disconnect(), 10000);

const themeObserver = new MutationObserver(() => {
	const button = document.querySelector(".pridict-theme-toggle");
	if (button) {
		updateThemeToggle(button);
	}
});
themeObserver.observe(document.documentElement, {
	attributes: true,
	attributeFilter: ["data-theme"],
});
