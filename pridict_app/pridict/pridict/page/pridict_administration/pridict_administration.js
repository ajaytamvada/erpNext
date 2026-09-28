frappe.pages["pridict-administration"].on_page_load = (wrapper) => {
	frappe.pridict_administration = new PridictAdministration(wrapper);
};
frappe.pages["pridict-administration"].on_page_show = () => frappe.pridict_administration?.refresh();

class PridictAdministration {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Administration"), single_column: true });
		this.$root = $('<div class="pridict-admin-home"></div>').appendTo(this.page.main.empty());
	}

	async refresh() {
		this.$root.html(`<div class="pridict-admin-state">${__("Loading administration")}</div>`);
		try {
			this.data = await frappe.xcall("pridict.pridict.page.pridict_administration.pridict_administration.get_overview");
			this.render();
		} catch (_error) {
			this.$root.html(`<div class="pridict-admin-state">${__("Administration could not be loaded.")}</div>`);
		}
	}

	render() {
		const labels = { enabled_users: "Enabled users", workflows: "Workflows", notifications: "Notifications", email_accounts: "Email accounts" };
		const routeFor = (doctype) => doctype.toLowerCase().replaceAll(" ", "-");
		this.$root.html(`
			<header><span>${__("System operations")}</span><h1>${__("Administration")}</h1><p>${__("Manage access, workflows, communication, data tools, printing, and protected system configuration.")}</p></header>
			<section class="pridict-admin-metrics">${Object.entries(this.data.metrics).map(([key, value]) => `<article><span>${__(labels[key])}</span><strong>${value ?? "—"}</strong><small>${frappe.utils.escape_html(this.data.definitions[key])}</small></article>`).join("")}</section>
			<section class="pridict-admin-groups">${this.data.groups.map((group) => `<article><h2>${group.label}</h2><p>${group.description}</p><div>${group.items.map((doctype) => `<button data-route="${routeFor(doctype)}">${__(doctype)}</button>`).join("")}</div></article>`).join("")}</section>
			<footer><div>${this.data.compatibility_routes.map((item) => `<button data-route="${item.route}">${item.label}</button>`).join("")}</div></footer>
		`);
		this.$root.find("[data-route]").on("click", (event) => frappe.set_route(event.currentTarget.dataset.route));
	}
}
