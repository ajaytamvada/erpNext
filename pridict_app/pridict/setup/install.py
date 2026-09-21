import json
import re
from pathlib import Path

import frappe


APP_NAME = "Pridict"
APP_LOGO = "/assets/pridict/images/pridict-wordmark.svg"
APP_ICON = "/assets/pridict/images/pridict-icon.svg"
SUPPORT_LABEL = "Contact Pridict Support"
SUPPORT_ROUTE = "mailto:pavan@riditstack.com"
FOOTER_POWERED = f'Pridict <span aria-hidden="true">&middot;</span> <a href="{SUPPORT_ROUTE}">Contact support</a>'

UPSTREAM_LEARNING_URLS = {
	"https://school.frappe.io/lms/courses/erpnext-accounting?utm_source=in_app",
	"https://school.frappe.io/lms/courses/procurement?utm_source=in_app",
	"https://school.frappe.io/lms/courses/production-planning-and-execution",
	"https://school.frappe.io/lms/courses/project-management?utm_source=in_app",
	"https://school.frappe.io/lms/courses/sales-management-course?utm_source=in_app",
	"https://school.frappe.io/lms/courses/inventory-management?utm_source=in_app",
}

UPSTREAM_HELP_ROUTES = {
	"https://docs.erpnext.com/",
	"https://discuss.frappe.io",
	"https://frappe.io/school?utm_source=in_app",
	"https://frappe.io/support",
	"https://github.com/frappe/erpnext/issues",
}

CONTEXTUAL_HELP_SOURCE_PATHS = (
	"accounts/doctype/accounts_settings/accounts_settings.json",
	"accounts/doctype/payment_reconciliation/payment_reconciliation.json",
	"accounts/doctype/process_payment_reconciliation/process_payment_reconciliation.json",
	"selling/form_tour/selling_settings/selling_settings.json",
	"stock/doctype/item/item.json",
	"stock/doctype/stock_settings/stock_settings.json",
	"stock/form_tour/stock_entry/stock_entry.json",
	"stock/form_tour/stock_settings/stock_settings.json",
)


def apply_branding():
	frappe.db.set_single_value("Website Settings", "app_name", APP_NAME)
	frappe.db.set_single_value("Website Settings", "app_logo", APP_LOGO)
	frappe.db.set_single_value("Website Settings", "favicon", APP_ICON)
	frappe.db.set_single_value("System Settings", "app_name", APP_NAME)
	frappe.db.set_single_value("Navbar Settings", "app_logo", APP_LOGO)
	_apply_website_footer()
	_remove_upstream_learning_shortcuts()
	_remove_upstream_help_items()
	_ensure_pridict_support_item()
	_reconcile_standard_onboarding()
	_reconcile_contextual_help()
	frappe.db.set_default("disable_standard_email_footer", 1)
	# Workspace titles participate in routing. Keep their identifiers unchanged;
	# translations provide the Pridict display names instead.
	for name in ("ERPNext Settings", "ERPNext Integrations"):
		if frappe.db.get_value("Workspace", name, "title") == name.replace("ERPNext", APP_NAME):
			frappe.db.set_value("Workspace", name, {
				"label": name,
				"title": name,
			}, update_modified=False)
	for doctype, name, field in (
		("Module Onboarding", "Home", "title"),
		("Onboarding Step", "Create an Item", "description"),
	):
		value = frappe.db.get_value(doctype, name, field)
		if value and "ERPNext" in value:
			frappe.db.set_value(doctype, name, field, value.replace("ERPNext", APP_NAME),
				update_modified=False)
	frappe.clear_cache()


def _apply_website_footer():
	footer = frappe.db.get_single_value("Website Settings", "footer_powered")
	if (
		not footer
		or "frappe.io/erpnext" in footer.lower()
		or footer.strip().lower() == "erpnext"
		or footer.strip() == APP_NAME
	):
		frappe.db.set_single_value("Website Settings", "footer_powered", FOOTER_POWERED)


def _remove_upstream_learning_shortcuts():
	for row in frappe.get_all(
		"Workspace Shortcut",
		filters={"url": ["in", sorted(UPSTREAM_LEARNING_URLS)]},
		fields=["name"],
	):
		frappe.db.delete("Workspace Shortcut", {"name": row.name})


def _remove_upstream_help_items():
	navbar_settings = frappe.get_single("Navbar Settings")
	changed = False
	for row in navbar_settings.help_dropdown:
		if row.is_standard and row.item_type == "Route" and row.route in UPSTREAM_HELP_ROUTES and not row.hidden:
			row.hidden = 1
			changed = True
	if changed:
		navbar_settings.save(ignore_permissions=True)


def _ensure_pridict_support_item():
	navbar_settings = frappe.get_single("Navbar Settings")
	support_item = next(
		(row for row in navbar_settings.help_dropdown if row.item_label == SUPPORT_LABEL and not row.is_standard),
		None,
	)
	if support_item:
		changed = False
		for fieldname, value in {
			"item_type": "Route",
			"route": SUPPORT_ROUTE,
			"hidden": 0,
		}.items():
			if support_item.get(fieldname) != value:
				support_item.set(fieldname, value)
				changed = True
		if changed:
			navbar_settings.save(ignore_permissions=True)
		return

	navbar_settings.append(
		"help_dropdown",
		{
			"item_label": SUPPORT_LABEL,
			"item_type": "Route",
			"route": SUPPORT_ROUTE,
			"hidden": 0,
		},
	)
	navbar_settings.save(ignore_permissions=True)


def _reconcile_standard_onboarding():
	erpnext_path = Path(frappe.get_app_path("erpnext"))
	patterns = ("**/module_onboarding/*/*.json", "**/onboarding_step/*/*.json")
	for pattern in patterns:
		for source_path in erpnext_path.glob(pattern):
			source = json.loads(source_path.read_text(encoding="utf-8"))
			doctype = source.get("doctype")
			name = source.get("name")
			if not doctype or not name or not frappe.db.exists(doctype, name):
				continue

			updates = {}
			if doctype == "Module Onboarding":
				_update_if_unchanged(source, doctype, name, "documentation_url", updates, _remove_upstream_url)
			for fieldname in (
				"title",
				"subtitle",
				"success_message",
				"description",
				"action_label",
				"callback_message",
				"callback_title",
			):
				_update_if_unchanged(source, doctype, name, fieldname, updates, _brand_onboarding_text)

			if doctype == "Onboarding Step":
				for fieldname in ("video_url", "intro_video_url"):
					_update_if_unchanged(source, doctype, name, fieldname, updates, _remove_upstream_url)
				if source.get("action") == "Watch Video" and any(
					fieldname in updates and not updates[fieldname]
					for fieldname in ("video_url", "intro_video_url")
				):
					_update_if_unchanged(source, doctype, name, "action", updates, lambda _value: "")

			if updates:
				frappe.db.set_value(doctype, name, updates, update_modified=False)


def _reconcile_contextual_help():
	erpnext_path = Path(frappe.get_app_path("erpnext"))
	for relative_path in CONTEXTUAL_HELP_SOURCE_PATHS:
		source_path = erpnext_path / relative_path
		if not source_path.exists():
			continue

		source = json.loads(source_path.read_text(encoding="utf-8"))
		if source.get("doctype") == "DocType":
			_reconcile_doctype_help(source)
		elif source.get("doctype") == "Form Tour":
			_reconcile_form_tour_help(source)


def _reconcile_doctype_help(source):
	for field in source.get("fields", []):
		fieldname = field.get("fieldname")
		if not fieldname:
			continue

		filters = {"parent": source.get("name"), "fieldname": fieldname}
		for property_name, transform in (
			("documentation_url", _remove_upstream_url),
			("description", _remove_upstream_links_from_html),
		):
			source_value = field.get(property_name)
			if not source_value:
				continue
			current_value = frappe.db.get_value("DocField", filters, property_name)
			if current_value != source_value:
				continue
			updated_value = transform(source_value)
			if updated_value != source_value:
				frappe.db.set_value("DocField", filters, property_name, updated_value, update_modified=False)


def _reconcile_form_tour_help(source):
	for step in source.get("steps", []):
		source_value = step.get("description")
		if not source_value:
			continue

		filters = {
			"parent": source.get("name"),
			"fieldname": step.get("fieldname"),
			"title": step.get("title"),
		}
		current_value = frappe.db.get_value("Form Tour Step", filters, "description")
		if current_value != source_value:
			continue
		updated_value = _remove_upstream_links_from_html(source_value)
		if updated_value != source_value:
			frappe.db.set_value("Form Tour Step", filters, "description", updated_value, update_modified=False)


def _update_if_unchanged(source, doctype, name, fieldname, updates, transform):
	source_value = source.get(fieldname)
	if not source_value:
		return
	current_value = frappe.db.get_value(doctype, name, fieldname)
	if current_value != source_value:
		return
	updated_value = transform(source_value)
	if updated_value != source_value:
		updates[fieldname] = updated_value


def _remove_upstream_url(value):
	if not value:
		return value
	lowered = value.lower()
	if any(host in lowered for host in ("erpnext.com", "frappe.io", "youtube.com", "youtu.be")):
		return ""
	return value


def _remove_upstream_links_from_html(value):
	if not value:
		return value
	return re.sub(
		r'<a\b[^>]*href=["\']https?://(?:docs\.erpnext\.com|docs\.frappe\.io/erpnext)[^"\']*["\'][^>]*>(.*?)</a>',
		r"\1",
		value,
		flags=re.IGNORECASE | re.DOTALL,
	)


def _brand_onboarding_text(value):
	if not value:
		return value
	value = re.sub(r"!\[[^]]*]\(https?://[^)]+\)", "", value)
	value = re.sub(
		r"\[([^]]+)]\(https?://(?:[^/]*\.)?(?:erpnext\.com|frappe\.io|youtube\.com|youtu\.be)[^)]+\)",
		r"\1",
		value,
		flags=re.IGNORECASE,
	)
	return value.replace("ERPNext", APP_NAME)
