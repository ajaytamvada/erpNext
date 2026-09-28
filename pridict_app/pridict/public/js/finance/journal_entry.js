frappe.ui.form.on("Journal Entry", {
	refresh: refreshPridictJournalEntry,
	onload_post_render: refreshPridictJournalEntry,
	voucher_type: refreshPridictJournalEntry,
	company: refreshPridictJournalEntry,
	posting_date: refreshPridictJournalEntry,
	total_debit: refreshPridictJournalEntry,
	total_credit: refreshPridictJournalEntry,
	difference: refreshPridictJournalEntry,
});

function refreshPridictJournalEntry(frm) {
	window.pridict?.finance?.refreshForm(frm);
}
