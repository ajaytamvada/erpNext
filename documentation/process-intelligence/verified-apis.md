# Verified Local APIs

Verified on September 29, 2026 against:

- Frappe `15.120.1`, source revision `9f8ae9c`
- ERPNext `15.121.2`, source revision `df8b7f9`
- Pridict `0.1.0`

## Frappe APIs

- `frappe.get_all`: `apps/frappe/frappe/__init__.py:2043`
- `frappe.get_meta`: `apps/frappe/frappe/__init__.py:1352`
- `frappe.only_for`: `apps/frappe/frappe/__init__.py:947`
- `frappe.db.table_exists`: `apps/frappe/frappe/database/database.py:1220`

The collector uses `frappe.get_all(..., ignore_permissions=True)` only inside a System Manager-protected service boundary. It uses `frappe.get_meta` to intersect requested fields with the installed schema and `frappe.db.table_exists` before optional configuration reads.

## Configuration Schemas

- Workflow document selector: `apps/frappe/frappe/workflow/doctype/workflow/workflow.json:34`
- Workflow Transition condition: `apps/frappe/frappe/workflow/doctype/workflow_transition/workflow_transition.json:75`
- Assignment Rule document selector: `apps/frappe/frappe/automation/doctype/assignment_rule/assignment_rule.json:36`
- Notification document selector: `apps/frappe/frappe/email/doctype/notification/notification.json:99`

## Transaction Evidence Schemas

- Version reference fields and inert change payload: `apps/frappe/frappe/core/doctype/version/version.json:18`, `:31`, `:38`
- Workflow Action status, reference, workflow state and completed-by fields: `apps/frappe/frappe/workflow/doctype/workflow_action/workflow_action.json:20`, `:27`, `:33`, `:48`, `:55`
- Request for Quotation item Material Request links: `apps/erpnext/erpnext/buying/doctype/request_for_quotation_item/request_for_quotation_item.json:170`, `:182`
- Supplier Quotation item RFQ and Material Request links: `apps/erpnext/erpnext/buying/doctype/supplier_quotation_item/supplier_quotation_item.json:406`, `:428`, `:448`
- Purchase Order item Material Request and Supplier Quotation links: `apps/erpnext/erpnext/buying/doctype/purchase_order_item/purchase_order_item.json:473`, `:488`, `:520`, `:528`
- Purchase Receipt item Purchase Order and Material Request links: `apps/erpnext/erpnext/stock/doctype/purchase_receipt_item/purchase_receipt_item.json:549`, `:612`, `:769`, `:776`
- Purchase Invoice item Purchase Order, Purchase Receipt and Material Request links: `apps/erpnext/erpnext/accounts/doctype/purchase_invoice_item/purchase_invoice_item.json:630`, `:682`, `:694`, `:716`, `:946`, `:956`
- Payment Entry reference type, name and allocation: `apps/erpnext/erpnext/accounts/doctype/payment_entry_reference/payment_entry_reference.json:32`, `:42`, `:87`

All source references above were verified against the installed disposable-site versions on September 29, 2026. Conditions and Version payloads are recorded as data; no expression, Server Script or controller code is executed by Process Intelligence.

## Schema Intelligence Contract

- `SchemaSnapshot`: `pridict_app/pridict/schema_intelligence/models.py:282`
- Snapshot format version: `pridict_app/pridict/schema_intelligence/models.py:7`
- Snapshot capture service: `pridict_app/pridict/schema_intelligence/service.py:13`
- Atomic snapshot repository: `pridict_app/pridict/schema_intelligence/persistence.py:54`

The adapter accepts SchemaSnapshot major version `1` and fails explicitly for incompatible major versions.
