frappe.pages["pridict-integrations"].on_page_load = (wrapper) => {
	frappe.pridict_integrations = new PridictIntegrations(wrapper);
};
frappe.pages["pridict-integrations"].on_page_show = () => frappe.pridict_integrations?.refresh();

class PridictIntegrations {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Integrations"), single_column: true });
		this.$root = $('<div class="pridict-admin-home"></div>').appendTo(this.page.main.empty());
	}

	async refresh() {
		this.$root.html(`<div class="pridict-admin-state">${__("Loading integrations")}</div>`);
		try {
			this.data = await frappe.xcall("pridict.pridict.page.pridict_integrations.pridict_integrations.get_overview");
			this.render();
		} catch (_error) {
			this.$root.html(`<div class="pridict-admin-state">${__("Integrations could not be loaded.")}</div>`);
		}
	}

	render() {
		const labels = { webhooks: "Webhooks", oauth_clients: "OAuth clients", social_login_providers: "Social login providers", google_calendars: "Google calendars" };
		const routeFor = (doctype) => doctype.toLowerCase().replaceAll(" ", "-");
		this.$root.html(`
			<header><span>${__("Connected services")}</span><h1>${__("Integrations")}</h1><p>${__("Configure authentication, communications, Google services, backups, and banking connections without exposing protected credentials.")}</p></header>
			<section class="pridict-admin-metrics">${Object.entries(this.data.metrics).map(([key, value]) => `<article><span>${__(labels[key])}</span><strong>${value ?? "—"}</strong><small>${frappe.utils.escape_html(this.data.definitions[key])}</small></article>`).join("")}</section>
			<section class="pridict-admin-groups">${this.data.groups.map((group) => `<article><h2>${group.label}</h2><p>${group.description}</p><div>${group.items.map((doctype) => `<button data-route="${routeFor(doctype)}">${__(doctype)}</button>`).join("")}</div></article>`).join("")}</section>
			<footer><div>${this.data.compatibility_routes.map((item) => `<button data-route="${item.route}">${item.label}</button>`).join("")}</div></footer>
		`);
		this.$root.find("[data-route]").on("click", (event) => frappe.set_route(event.currentTarget.dataset.route));
	}
}
