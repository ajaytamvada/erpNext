frappe.ui.form.on("Batch", { refresh: refreshPridictBatch, onload_post_render: refreshPridictBatch, item: refreshPridictBatch, manufacturing_date: refreshPridictBatch, expiry_date: refreshPridictBatch, batch_qty: refreshPridictBatch, disabled: refreshPridictBatch });
function refreshPridictBatch(frm) { window.pridict?.inventory?.refreshForm(frm); }
