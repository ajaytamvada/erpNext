frappe.ui.form.on("Warehouse", { refresh: refreshPridictWarehouse, onload_post_render: refreshPridictWarehouse, warehouse_name: refreshPridictWarehouse, company: refreshPridictWarehouse, parent_warehouse: refreshPridictWarehouse, is_group: refreshPridictWarehouse, disabled: refreshPridictWarehouse });
function refreshPridictWarehouse(frm) { window.pridict?.inventory?.refreshForm(frm); }
