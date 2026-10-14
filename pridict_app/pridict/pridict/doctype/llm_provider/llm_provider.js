frappe.ui.form.on("LLM Provider", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Test Connection"), async () => {
			const result = await frappe.xcall("pridict.agent_studio.gateway.test_provider", { name: frm.doc.name });
			frappe.show_alert({
				message: result.ok ? __("Connected in {0} ms ({1})", [result.latency_ms, result.model]) : result.error,
				indicator: result.ok ? "green" : "red",
			});
			frm.reload_doc();
		});
	},
});
