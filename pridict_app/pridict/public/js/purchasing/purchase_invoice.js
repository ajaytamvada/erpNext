frappe.ui.form.on("Purchase Invoice", {
	refresh: refreshPridictPurchaseInvoice,
	onload_post_render: refreshPridictPurchaseInvoice,
	supplier: refreshPridictPurchaseInvoice,
	company: refreshPridictPurchaseInvoice,
	posting_date: refreshPridictPurchaseInvoice,
	due_date: refreshPridictPurchaseInvoice,
	bill_no: refreshPridictPurchaseInvoice,
	currency: refreshPridictPurchaseInvoice,
	grand_total: refreshPridictPurchaseInvoice,
	outstanding_amount: refreshPridictPurchaseInvoice,
});

function refreshPridictPurchaseInvoice(frm) {
	window.pridict?.purchasing?.refreshForm(frm);
}
