import frappe


def ensure_governance_setup():
	if not frappe.db.exists("Role", "Schema Reviewer"):
		frappe.get_doc({"doctype": "Role", "role_name": "Schema Reviewer", "desk_access": 1}).insert(ignore_permissions=True)
	_ensure_schema_intelligence_page_roles()
	if frappe.db.exists("DocType", "Notification Type") and not frappe.db.exists(
		"Notification Type", "Schema Intelligence"
	):
		frappe.get_doc(
			{"doctype": "Notification Type", "type_name": "Schema Intelligence", "enabled": 1}
		).insert(ignore_permissions=True)
	if frappe.db.exists("DocType", "Schema Snapshot Record"):
		from pridict.schema_intelligence.governance import index_existing_snapshots

		index_existing_snapshots()


def _ensure_schema_intelligence_page_roles():
	if not frappe.db.exists("Page", "schema-intelligence"):
		return

	page = frappe.get_doc("Page", "schema-intelligence")
	existing_roles = {row.role for row in page.roles}
	changed = False
	for role in ("System Manager", "Schema Reviewer"):
		if role not in existing_roles:
			page.append("roles", {"role": role})
			changed = True

	if changed:
		page.save(ignore_permissions=True)
