frappe.ui.form.on("Quotation", { refresh: refreshPridictQuotation, onload_post_render: refreshPridictQuotation, party_name: refreshPridictQuotation, transaction_date: refreshPridictQuotation, valid_till: refreshPridictQuotation, grand_total: refreshPridictQuotation, status: refreshPridictQuotation });
function refreshPridictQuotation(frm) { window.pridict?.sales?.refreshForm(frm); }
