frappe.ui.form.on("Schema Snapshot Record", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Export Summary"), async () => {
			const result = await frappe.xcall("pridict.schema_intelligence.api.export_snapshot_summary", { snapshot_id: frm.doc.name });
			const blob = new Blob([result.content], { type: result.content_type });
			const link = document.createElement("a");
			link.href = URL.createObjectURL(blob);
			link.download = result.filename;
			link.click();
			URL.revokeObjectURL(link.href);
		});
		if (!frappe.user.has_role("System Manager")) return;
		if (!frm.doc.is_baseline && frm.doc.completeness === "complete") {
			frm.add_custom_button(__("Promote to Baseline"), () => {
				frappe.confirm(__("Promote this snapshot to the site baseline?"), async () => {
					await frappe.xcall("pridict.schema_intelligence.api.promote_baseline", { snapshot_id: frm.doc.name, confirmed: 1 });
					frm.reload_doc();
				});
			}, __("Governance"));
		}
		frm.add_custom_button(__("Delete Snapshot"), () => {
			frappe.confirm(__("Permanently delete this snapshot file and governance record?"), async () => {
				await frappe.xcall("pridict.schema_intelligence.api.delete_snapshot", { snapshot_id: frm.doc.name, confirmed: 1 });
				frappe.set_route("List", "Schema Snapshot Record");
			});
		}, __("Governance"));
	},
});
