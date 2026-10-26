frappe.ui.form.on("Agent Run", {
	refresh(frm) {
		const pending = frm.doc.pending_json ? JSON.parse(frm.doc.pending_json) : null;
		if (frm.doc.automation) {
			frm.add_custom_button(__("Open in Builder"), () =>
				frappe.set_route("automation-builder", frm.doc.automation)
			);
		}
		// An automation's Ask step links people here from their notification.
		if (frm.doc.automation && !frm.doc.is_test && frm.doc.status === "Waiting" && pending?.type === "ask") {
			frm.dashboard.set_headline_alert(frappe.utils.escape_html(pending.question || ""), "orange");
			frm.add_custom_button(__("Answer"), () => {
				const field = pending.choices?.length
					? { fieldname: "answer", fieldtype: "Select", options: pending.choices.join("\n"), reqd: 1, label: __("Answer") }
					: { fieldname: "answer", fieldtype: "Small Text", reqd: 1, label: __("Answer") };
				frappe.prompt(
					field,
					({ answer }) =>
						frappe
							.call({ method: "pridict.automation.api.answer", args: { run: frm.doc.name, answer }, freeze: true })
							.then(() => frm.reload_doc()),
					pending.question || __("Answer")
				);
			}).addClass("btn-primary");
		}
	},
});
