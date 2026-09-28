frappe.ui.form.on("Payment Entry", {
	refresh: refreshPridictPaymentEntry,
	onload_post_render: refreshPridictPaymentEntry,
	payment_type: refreshPridictPaymentEntry,
	posting_date: refreshPridictPaymentEntry,
	party_type: refreshPridictPaymentEntry,
	party: refreshPridictPaymentEntry,
	mode_of_payment: refreshPridictPaymentEntry,
	paid_amount: refreshPridictPaymentEntry,
	received_amount: refreshPridictPaymentEntry,
	difference_amount: refreshPridictPaymentEntry,
});

function refreshPridictPaymentEntry(frm) {
	window.pridict?.finance?.refreshForm(frm);
}
