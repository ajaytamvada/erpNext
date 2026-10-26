frappe.ui.form.on("Automation", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Open Builder"), () =>
				frappe.set_route("automation-builder", frm.doc.name)
			);
		}
	},
});
