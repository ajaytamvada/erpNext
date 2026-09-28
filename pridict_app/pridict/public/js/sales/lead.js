frappe.ui.form.on("Lead", { refresh: refreshPridictLead, onload_post_render: refreshPridictLead, lead_name: refreshPridictLead, company_name: refreshPridictLead, status: refreshPridictLead, lead_owner: refreshPridictLead });
function refreshPridictLead(frm) { window.pridict?.sales?.refreshForm(frm); }
