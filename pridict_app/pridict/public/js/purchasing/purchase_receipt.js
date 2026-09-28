frappe.ui.form.on("Purchase Receipt", {
	refresh: refreshPridictPurchaseReceipt,
	onload_post_render: refreshPridictPurchaseReceipt,
	supplier: refreshPridictPurchaseReceipt,
	company: refreshPridictPurchaseReceipt,
	posting_date: refreshPridictPurchaseReceipt,
	set_warehouse: refreshPridictPurchaseReceipt,
	is_return: refreshPridictPurchaseReceipt,
	grand_total: refreshPridictPurchaseReceipt,
});

function refreshPridictPurchaseReceipt(frm) {
	window.pridict?.purchasing?.refreshForm(frm);
}
