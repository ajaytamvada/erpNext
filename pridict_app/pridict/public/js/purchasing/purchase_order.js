frappe.ui.form.on("Purchase Order", {
	refresh: refreshPridictPurchaseOrder,
	onload_post_render: refreshPridictPurchaseOrder,
	supplier: refreshPridictPurchaseOrder,
	company: refreshPridictPurchaseOrder,
	transaction_date: refreshPridictPurchaseOrder,
	schedule_date: refreshPridictPurchaseOrder,
	currency: refreshPridictPurchaseOrder,
	grand_total: refreshPridictPurchaseOrder,
});

function refreshPridictPurchaseOrder(frm) {
	window.pridict?.purchasing?.refreshForm(frm);
}
