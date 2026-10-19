import frappe


def extend_bootinfo(bootinfo):
	if frappe.session.user == "Guest":
		return

	# Lets the Pridict shell place any DocType / report / page under the right module
	# instead of relying only on the hand-written lists in route_context.js.
	bootinfo.pridict_modules = {
		"doctypes": dict(frappe.get_all("DocType", filters={"istable": 0}, fields=["name", "module"], as_list=True)),
		"reports": dict(frappe.get_all("Report", fields=["name", "module"], as_list=True)),
		"pages": dict(frappe.get_all("Page", fields=["name", "module"], as_list=True)),
	}

	# The "What's new" dialog lists upstream framework releases by name.
	bootinfo.change_log = []
