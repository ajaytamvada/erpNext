frappe.pages["automation-builder"].on_page_load = (wrapper) => {
	wrapper.page_obj = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Automation Builder"),
		single_column: true,
	});
};

frappe.pages["automation-builder"].on_page_show = async (wrapper) => {
	const name = frappe.get_route()[1];
	if (!name) {
		frappe.set_route("automations");
		return;
	}
	await frappe.require("automation_builder.bundle.js");
	if (!wrapper.builder) {
		wrapper.builder = new pridict.automation.Builder({ wrapper, page: wrapper.page_obj });
	}
	wrapper.builder.load(name);
};
