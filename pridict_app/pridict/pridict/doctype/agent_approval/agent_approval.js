frappe.ui.form.on("Agent Approval", {
	refresh(frm) {
		frm.add_custom_button(__("Open in Approval Inbox"), () => frappe.set_route("agent-approvals"));
		if (frm.doc.status !== "Pending") return;
		const decide = (decision, note) =>
			frappe
				.xcall("pridict.agent_studio.approvals.decide", { approval: frm.doc.name, decision, note })
				.then((r) => {
					frappe.show_alert({ message: r.status === "Pending" ? __("Recorded; still waiting for {0}", [r.remaining.join(", ")]) : __(r.status), indicator: "green" });
					frm.reload_doc();
				});
		frm.add_custom_button(__("Approve"), () => frappe.confirm(__("Approve this proposal? The agent will create a Draft RFQ."), () => decide("approve", "")), __("Decide"));
		frm.add_custom_button(
			__("Reject"),
			() => frappe.prompt({ fieldname: "note", fieldtype: "Small Text", label: __("Reason"), reqd: 1 }, ({ note }) => decide("reject", note), __("Reject proposal")),
			__("Decide")
		);
	},
});
