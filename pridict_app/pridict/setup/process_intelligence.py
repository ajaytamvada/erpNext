import frappe


def ensure_process_intelligence_setup():
	# This role allows analysis only; business permissions must be assigned separately.
	if not frappe.db.exists("Role", "Process Analyst"):
		frappe.get_doc({"doctype": "Role", "role_name": "Process Analyst", "desk_access": 1}).insert(ignore_permissions=True)
