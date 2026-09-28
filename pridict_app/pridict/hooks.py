app_name = "pridict"
app_title = "Pridict"
app_publisher = "RiditStack"
app_description = "Pridict branding and Enterprise UI for ERPNext"
app_license = "GNU General Public License (v3)"
app_logo_url = "/assets/pridict/images/pridict-wordmark.svg"
brand_html = '<img src="/assets/pridict/images/pridict-wordmark.svg" alt="Pridict">'

website_context = {
	"favicon": "/assets/pridict/images/pridict-icon.svg",
	"splash_image": "/assets/pridict/images/pridict-icon.svg",
}

required_apps = ["erpnext"]

app_include_css = "pridict.bundle.css"
app_include_js = [
	"/assets/pridict/js/ui/route_context.js",
	"/assets/pridict/js/ui/surface.js",
	"/assets/pridict/js/ui/components.js",
	"/assets/pridict/js/ui/shell.js",
	"/assets/pridict/js/ui/page_header.js",
	"/assets/pridict/js/purchasing.js",
	"/assets/pridict/js/finance.js",
	"/assets/pridict/js/sales.js",
	"/assets/pridict/js/inventory.js",
	"/assets/pridict/js/assets.js",
	"/assets/pridict/js/manufacturing.js",
	"/assets/pridict/js/projects.js",
	"/assets/pridict/js/quality_support.js",
	"/assets/pridict/js/administration_integrations.js",
	"/assets/pridict/js/ui/generic_module.js",
	"/assets/pridict/js/ui/cross_product.js",
	"pridict.bundle.js",
]

doctype_js = {
	"Material Request": "public/js/purchasing/material_request.js",
	"Purchase Order": "public/js/purchasing/purchase_order.js",
	"Purchase Receipt": "public/js/purchasing/purchase_receipt.js",
	"Purchase Invoice": "public/js/purchasing/purchase_invoice.js",
	"Lead": "public/js/sales/lead.js",
	"Opportunity": "public/js/sales/opportunity.js",
	"Quotation": "public/js/sales/quotation.js",
	"Sales Order": "public/js/sales/sales_order.js",
	"Delivery Note": "public/js/sales/delivery_note.js",
	"Sales Invoice": "public/js/sales/sales_invoice.js",
	"Item": "public/js/inventory/item.js",
	"Warehouse": "public/js/inventory/warehouse.js",
	"Stock Entry": "public/js/inventory/stock_entry.js",
	"Pick List": "public/js/inventory/pick_list.js",
	"Stock Reconciliation": "public/js/inventory/stock_reconciliation.js",
	"Serial No": "public/js/inventory/serial_no.js",
	"Batch": "public/js/inventory/batch.js",
	"Asset": "public/js/assets/asset.js",
	"Asset Category": "public/js/assets/asset_category.js",
	"Asset Movement": "public/js/assets/asset_movement.js",
	"Asset Repair": "public/js/assets/asset_repair.js",
	"Asset Maintenance": "public/js/assets/asset_maintenance.js",
	"Asset Depreciation Schedule": "public/js/assets/asset_depreciation_schedule.js",
	"BOM": "public/js/manufacturing/bom.js",
	"Production Plan": "public/js/manufacturing/production_plan.js",
	"Work Order": "public/js/manufacturing/work_order.js",
	"Job Card": "public/js/manufacturing/job_card.js",
	"Operation": "public/js/manufacturing/operation.js",
	"Workstation": "public/js/manufacturing/workstation.js",
	"Project": "public/js/projects/project.js",
	"Task": "public/js/projects/task.js",
	"Timesheet": "public/js/projects/timesheet.js",
	"Activity Type": "public/js/projects/activity_type.js",
	"Quality Inspection": "public/js/quality/quality_inspection.js",
	"Quality Goal": "public/js/quality/quality_goal.js",
	"Quality Review": "public/js/quality/quality_review.js",
	"Quality Action": "public/js/quality/quality_action.js",
	"Non Conformance": "public/js/quality/non_conformance.js",
	"Issue": "public/js/support/issue.js",
	"Service Level Agreement": "public/js/support/service_level_agreement.js",
	"Warranty Claim": "public/js/support/warranty_claim.js",
	"Payment Entry": "public/js/finance/payment_entry.js",
	"Journal Entry": "public/js/finance/journal_entry.js",
}
web_include_css = "pridict.bundle.css"
web_include_js = ["pridict.bundle.js", "/assets/pridict/js/customer_facing.js"]

welcome_email = "pridict.email.get_welcome_email_subject"

after_install = "pridict.setup.install.apply_pridict_setup"
after_migrate = "pridict.setup.install.apply_pridict_setup"

scheduler_events = {
	"hourly": ["pridict.schema_intelligence.scheduler.hourly"],
}

notification_skip_email_types = ["Schema Intelligence"]
