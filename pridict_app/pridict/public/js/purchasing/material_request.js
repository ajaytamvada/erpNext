frappe.ui.form.on("Material Request", {
	refresh: refreshPridictMaterialRequest,
	onload_post_render: refreshPridictMaterialRequest,
	material_request_type: refreshPridictMaterialRequest,
	company: refreshPridictMaterialRequest,
	schedule_date: refreshPridictMaterialRequest,
	set_warehouse: refreshPridictMaterialRequest,
});

function refreshPridictMaterialRequest(frm) {
	window.pridict?.purchasing?.refreshForm(frm);
}
