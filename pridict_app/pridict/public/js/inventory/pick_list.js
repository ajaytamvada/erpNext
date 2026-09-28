frappe.ui.form.on("Pick List", { refresh: refreshPridictPickList, onload_post_render: refreshPridictPickList, purpose: refreshPridictPickList, customer_name: refreshPridictPickList, parent_warehouse: refreshPridictPickList, status: refreshPridictPickList });
function refreshPridictPickList(frm) { window.pridict?.inventory?.refreshForm(frm); }
