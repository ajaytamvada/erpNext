frappe.ui.form.on("Work Order",{refresh:refreshPridictWorkOrder,onload_post_render:refreshPridictWorkOrder});function refreshPridictWorkOrder(){window.pridict?.manufacturing?.refreshForm();}
