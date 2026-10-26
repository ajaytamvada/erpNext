const AUTOMATION_API = "pridict.automation.api";

frappe.ui.form.on("Automation", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Open Builder"), () => frappe.set_route("automation-builder", frm.doc.name));
		if (!frm.perm[0]?.write) return;

		const call = (method, args = {}) =>
			frappe
				.call({ method: `${AUTOMATION_API}.${method}`, args: { name: frm.doc.name, ...args }, freeze: true })
				.then(() => frm.reload_doc());

		if (["Draft", "Paused", "Disabled", "Active"].includes(frm.doc.status)) {
			const label = frm.doc.status === "Active" ? __("Activate Changes") : __("Activate");
			frm.add_custom_button(label, () =>
				frappe.prompt(
					{ fieldname: "change_note", fieldtype: "Small Text", label: __("What changed?") },
					(values) => call("activate", values),
					label
				)
			);
		}
		if (frm.doc.status === "Active") {
			frm.add_custom_button(__("Pause"), () => call("pause"));
			if (frm.doc.trigger_type === "trigger.manual" || frm.doc.trigger_type === "trigger.document_event") {
				frm.add_custom_button(__("Run Now"), () => run_now(frm));
			}
		}
		if (frm.doc.status === "Paused" && frm.doc.active_version) {
			frm.add_custom_button(__("Resume"), () => call("resume"));
		}
		if (frm.doc.status === "Paused" && frm.doc.paused_reason) {
			frm.dashboard.set_headline_alert(frappe.utils.escape_html(frm.doc.paused_reason), "orange");
		}
	},
});

function run_now(frm) {
	const doctype = frm.doc.trigger_doctype;
	const start = (name) =>
		frappe
			.call({
				method: "pridict.automation.triggers.run_now",
				args: { automation: frm.doc.name, doctype: name ? doctype : null, name: name || null },
			})
			.then(({ message }) => {
				frappe.show_alert({ message: __("Started run {0}", [message.run]), indicator: "green" });
				frappe.set_route("automation-builder", frm.doc.name);
			});
	if (!doctype) return start(null);
	frappe.prompt(
		{ fieldname: "name", fieldtype: "Link", options: doctype, label: __(doctype), reqd: 1 },
		(values) => start(values.name),
		__("Run on which {0}?", [__(doctype)])
	);
}
