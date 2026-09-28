frappe.ui.form.on("Item", { refresh: refreshPridictItem, onload_post_render: refreshPridictItem, item_name: refreshPridictItem, item_group: refreshPridictItem, stock_uom: refreshPridictItem, is_stock_item: refreshPridictItem, disabled: refreshPridictItem, valuation_rate: refreshPridictItem });
function refreshPridictItem(frm) { window.pridict?.inventory?.refreshForm(frm); }
