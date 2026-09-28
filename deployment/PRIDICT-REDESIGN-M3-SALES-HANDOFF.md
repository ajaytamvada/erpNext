# Pridict Redesign Milestone 3: Sales and CRM Source Handoff

Date: September 28, 2026

Status: Source implementation complete for this checkpoint. Not visually reviewed, functionally verified in a Frappe runtime, built, migrated, deployed, or accepted.

## Scope completed in source

- Added a dedicated `Pridict Sales & CRM` Page with permission-aware company selection, exact-definition operational counts, dated follow-up records, customer-document pipeline, create actions, recent activity, and standard CRM and Selling workspace links.
- Changed the executive-home Sales tile and persistent Pridict shell Sales destination to open the new Sales Page.
- Added Sales route classification for Lead, Opportunity, Quotation, Sales Order, Delivery Note, and Sales Invoice.
- Added a persistent customer journey across the Sales Page and all six native list and form routes.
- Added native list introductions and filter presets for prospect, pipeline, quotation, fulfillment, and billing states.
- Added list-row progress for Opportunity probability, Sales Order delivery and billing, Delivery Note billing, and Sales Invoice outstanding value.
- Added read-only form summaries using existing document values.
- Added document-state guidance for lead qualification, opportunity conversion, quotation conversion, order delivery and billing, delivery billing, invoice payment, draft, and cancelled states.
- Added presentation tagging for native customer details, item tables, taxes, totals, linked documents, sidebars, timelines, and action containers.
- Added responsive horizontal handling for native item tables without hiding commercial, stock, tax, or accounting columns.
- Added additive form lifecycle hooks for all six customer documents.

## Sales Invoice ownership clarification

- Sales Invoice is now classified as the final stage of the primary Sales and CRM journey.
- The Finance Page may still create and link to Sales Invoices because they remain accounting-relevant.
- Opening a Sales Invoice uses the Sales route adapter and highlights Sales and CRM in the shared shell.
- The earlier Finance handoff is a dated source record; its statement that Sales Invoice used the Finance form adapter is superseded by this milestone.
- No Sales Invoice business, stock, tax, payment, or accounting behavior changed.

## Files added

- `pridict_app/pridict/pridict/page/pridict_sales/__init__.py`
- `pridict_app/pridict/pridict/page/pridict_sales/pridict_sales.json`
- `pridict_app/pridict/pridict/page/pridict_sales/pridict_sales.py`
- `pridict_app/pridict/pridict/page/pridict_sales/pridict_sales.js`
- `pridict_app/pridict/pridict/page/pridict_sales/test_pridict_sales.py`
- `pridict_app/pridict/public/js/sales.js`
- `pridict_app/pridict/public/js/sales/lead.js`
- `pridict_app/pridict/public/js/sales/opportunity.js`
- `pridict_app/pridict/public/js/sales/quotation.js`
- `pridict_app/pridict/public/js/sales/sales_order.js`
- `pridict_app/pridict/public/js/sales/delivery_note.js`
- `pridict_app/pridict/public/js/sales/sales_invoice.js`
- `pridict_app/pridict/public/scss/pridict/_sales.scss`

## Existing files updated

- `pridict_app/pridict/hooks.py`
- `pridict_app/pridict/public/js/ui/route_context.js`
- `pridict_app/pridict/public/js/ui/shell.js`
- `pridict_app/pridict/public/js/finance.js`
- `pridict_app/pridict/pridict/page/pridict_home/pridict_home.py`
- `pridict_app/pridict/public/scss/pridict.bundle.scss`

## Functional-preservation boundary

- No lead conversion, opportunity workflow, pricing, taxes, stock posting, delivery logic, invoice posting, payment status, permissions, approvals, required fields, document relationships, communication history, or mapped-document actions were replaced.
- Page metrics are permission-aware counts rather than invented monetary aggregations.
- List presets use native Frappe route options.
- Form integrations are read-only summaries and presentation classes attached through additive `doctype_js` handlers.
- Native item grids remain intact and horizontally scrollable on small screens.
- Standard CRM and Selling workspaces remain available for compatibility and administration.

## Targeted validation completed

- `node --check` passed for the Sales Page, route context, shared shell, Finance adapter, Sales adapter, and all six Sales lifecycle hooks.
- The Sales Page JSON parsed successfully.
- Python bytecode compilation passed for the Sales service and focused test module.
- `git diff --check` passed.

## Validation not completed

- No local Frappe runtime review was available.
- Focused Frappe tests were not executed because the host environment does not provide the project test runtime.
- No asset build, migration, browser capture, workflow transaction, image build, or deployment was run.
- Every Sales and CRM screen remains `Implemented in source` only. None is yet `Visually reviewed`, `Functionally verified`, or `Deployed`.

## Required runtime review

Review each route separately with representative Sales User, Sales Manager, Stock User, and Accounts User permissions:

1. Pridict Sales and CRM Page.
2. Lead list, form, assignment, communication, and conversion actions.
3. Opportunity list, form, probability, expected closing, and quotation conversion.
4. Quotation list, form, pricing, taxes, validity, and Sales Order conversion.
5. Sales Order list, form, item table, delivery and billing progress, hold, close, reopen, and mapped-document actions.
6. Delivery Note list, form, stock posting, return, transport, installation, billing, and Delivery Trip actions.
7. Sales Invoice list, form, taxes, payment status, returns, credit notes, and accounting links.
8. Desktop and mobile behavior in light and dark themes.

## Next development target

Continue with Inventory and Delivery:

1. Add a role-focused Inventory home.
2. Adapt Item, Warehouse, Stock Entry, Pick List, Delivery Note, Purchase Receipt, and Stock Reconciliation routes without duplicating Sales or Procurement ownership.
3. Add native-preserving adapters for stock reports, serial and batch workflows, and warehouse trees.
4. Extract stable shared list, summary, progress, grid, and guidance primitives from Procurement, Finance, and Sales to reduce duplication before further module expansion.

Do not treat this handoff as runtime acceptance or deployment readiness.
