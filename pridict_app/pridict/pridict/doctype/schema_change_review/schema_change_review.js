frappe.ui.form.on("Schema Change Review", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (["Open", "Acknowledged"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Acknowledge"), () => transitionReview(frm, "Acknowledged"), __("Review"));
			frm.add_custom_button(__("Approve"), () => transitionReview(frm, "Approved"), __("Review"));
			frm.add_custom_button(__("Reject"), () => transitionReview(frm, "Rejected"), __("Review"));
		}
		frm.add_custom_button(__("Add Comment"), () => addReviewComment(frm), __("Review"));
		if (frm.doc.status === "Approved" && !frm.doc.baseline_promoted && frappe.user.has_role("System Manager")) {
			frm.add_custom_button(__("Promote Candidate to Baseline"), () => promoteBaseline(frm), __("Review"));
		}
		if (frm.doc.notification_state === "Failed") {
			frm.add_custom_button(__("Retry Notification"), async () => {
				await frappe.xcall("pridict.schema_intelligence.api.retry_review_notification", { review_name: frm.doc.name });
				frm.reload_doc();
			}, __("Review"));
		}
		frm.add_custom_button(__("Export JSON"), () => downloadExport("export_review", frm.doc.name), __("Export"));
		frm.add_custom_button(__("Export Findings CSV"), () => downloadExport("export_findings_csv", frm.doc.name), __("Export"));
	},
});

function transitionReview(frm, status) {
	const dialog = new frappe.ui.Dialog({
		title: __(`Set review to ${status}`),
		fields: [{ fieldname: "comment", fieldtype: "Small Text", label: __("Audit comment"), reqd: 1 }],
		primary_action_label: __("Confirm"),
		primary_action: async (values) => {
			dialog.disable_primary_action();
			await frappe.xcall("pridict.schema_intelligence.api.transition_review", { review_name: frm.doc.name, status, comment: values.comment });
			dialog.hide();
			frm.reload_doc();
		},
	});
	dialog.show();
}

function addReviewComment(frm) {
	frappe.prompt(
		[{ fieldname: "comment", fieldtype: "Small Text", label: __("Comment"), reqd: 1 }],
		async (values) => {
			await frappe.xcall("pridict.schema_intelligence.api.add_review_comment", { review_name: frm.doc.name, comment: values.comment });
			frm.reload_doc();
		},
		__("Add Review Comment")
	);
}

function promoteBaseline(frm) {
	frappe.confirm(__("Promote the approved candidate snapshot to the site baseline?"), async () => {
		await frappe.xcall("pridict.schema_intelligence.api.promote_review_baseline", { review_name: frm.doc.name, confirmed: 1 });
		frm.reload_doc();
	});
}

async function downloadExport(method, reviewName) {
	const result = await frappe.xcall(`pridict.schema_intelligence.api.${method}`, { review_name: reviewName });
	const blob = new Blob([result.content], { type: result.content_type });
	const link = document.createElement("a");
	link.href = URL.createObjectURL(blob);
	link.download = result.filename;
	link.click();
	URL.revokeObjectURL(link.href);
}
