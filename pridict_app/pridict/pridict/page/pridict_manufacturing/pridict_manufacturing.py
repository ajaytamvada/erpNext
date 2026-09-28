import frappe
from frappe import _

DOCTYPES=("BOM","Production Plan","Work Order","Job Card","Operation","Workstation")
def count(doctype,filters):
	if not frappe.has_permission(doctype,"read"): return None
	rows=frappe.get_list(doctype,filters=filters,fields=["count(name) as count"],limit_page_length=1)
	return (rows[0].count or 0) if rows else 0
@frappe.whitelist()
def get_overview(company=None):
	if frappe.session.user=="Guest": frappe.throw(_("Please sign in to view Manufacturing."),frappe.PermissionError)
	companies=frappe.get_list("Company",fields=["name","default_currency"],order_by="name asc",limit_page_length=100)
	if not companies:return {"companies":[],"message":_("You do not have access to a company.")}
	names={row.name:row for row in companies};company=company or frappe.defaults.get_user_default("Company") or companies[0].name
	if company not in names:frappe.throw(_("You do not have access to company {0}.").format(frappe.bold(company)),frappe.PermissionError)
	metrics={"active_boms":count("BOM",{"company":company,"is_active":1,"docstatus":1}),"open_plans":count("Production Plan",{"company":company,"status":["in",["Draft","Submitted","Not Started","In Process","Material Requested"]]}),"open_work_orders":count("Work Order",{"company":company,"status":["in",["Not Started","In Process"]]}),"open_job_cards":count("Job Card",{"company":company,"status":["in",["Open","Work In Progress","On Hold"]]})}
	return {"companies":companies,"filters":{"company":company,"currency":names[company].default_currency},"metrics":metrics,"create_permissions":{d:frappe.has_permission(d,"create") for d in DOCTYPES},"reports":[{"label":_("Production Analytics"),"route":"query-report/Production Analytics"},{"label":_("Production Planning Report"),"route":"query-report/Production Planning Report"},{"label":_("Work Order Summary"),"route":"query-report/Work Order Summary"},{"label":_("Job Card Summary"),"route":"query-report/Job Card Summary"}],"definitions":{"active_boms":_("Submitted active BOMs for the selected company."),"open_plans":_("Production Plans that remain operational."),"open_work_orders":_("Work Orders not started or in process."),"open_job_cards":_("Job Cards open, in progress, or on hold.")}}
