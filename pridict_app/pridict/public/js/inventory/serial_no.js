frappe.ui.form.on("Serial No", { refresh: refreshPridictSerialNo, onload_post_render: refreshPridictSerialNo, item_code: refreshPridictSerialNo, company: refreshPridictSerialNo, warehouse: refreshPridictSerialNo, status: refreshPridictSerialNo, batch_no: refreshPridictSerialNo });
function refreshPridictSerialNo(frm) { window.pridict?.inventory?.refreshForm(frm); }
