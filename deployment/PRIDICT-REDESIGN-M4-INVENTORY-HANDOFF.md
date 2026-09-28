# Pridict Redesign Milestone 4: Inventory Source Handoff

Date: September 28, 2026

Status: Implemented in source only. Not visually reviewed, functionally verified in a Frappe runtime, built, migrated, deployed, or accepted.

## Source scope

- Added a dedicated `Pridict Inventory` Page with permission-aware company selection, exact stock counts, follow-up records, operational pipeline, report links, create actions, and recent stock activity.
- Changed the executive-home Inventory tile and persistent shell destination to open the new Inventory Page.
- Added Inventory route ownership for Item, Warehouse, Stock Entry, Pick List, Stock Reconciliation, Serial No, and Batch.
- Added native report adapters for Stock Balance, Stock Ledger, Stock Ageing, and Stock Projected Qty.
- Added a native Warehouse tree adapter.
- Added list introductions and native filter presets for all seven Inventory records.
- Added read-only form summaries, state guidance, item-grid handling, timeline treatment, and linked-document presentation.
- Added additive form lifecycle hooks for all seven records.
- Preserved Delivery Note under Sales and Purchase Receipt under Procurement. Inventory links to those existing journeys rather than duplicating ownership.

## Files added

- `pridict_app/pridict/pridict/page/pridict_inventory/`
- `pridict_app/pridict/public/js/inventory.js`
- `pridict_app/pridict/public/js/inventory/`
- `pridict_app/pridict/public/scss/pridict/_inventory.scss`

## Existing files updated

- `pridict_app/pridict/hooks.py`
- `pridict_app/pridict/public/js/ui/route_context.js`
- `pridict_app/pridict/public/js/ui/shell.js`
- `pridict_app/pridict/pridict/page/pridict_home/pridict_home.py`
- `pridict_app/pridict/public/scss/pridict.bundle.scss`

## Functional-preservation boundary

- No stock posting, valuation, serial or batch logic, warehouse hierarchy behavior, reconciliation calculation, barcode action, permissions, required fields, submission workflow, linked transaction, or report calculation was replaced.
- Item and Batch metrics are explicitly treated as shared master-data scope rather than company-owned totals.
- Company filters are applied only to native records that support a company field.
- Reports and trees retain their native filters, controllers, actions, exports, and drill-down behavior.

## Validation completed

- JavaScript syntax checks passed for the Inventory Page, shared route context and shell, Inventory adapter, and seven lifecycle hooks.
- Inventory Page JSON parsing passed.
- Python bytecode compilation passed for the Inventory service and focused test module.
- `git diff --check` passed.

## Validation outstanding

- No Frappe test execution, asset build, migration, browser review, workflow transaction, screenshot capture, image build, or deployment was run.
- Every Inventory screen remains `Implemented in source`; none is yet `Visually reviewed`, `Functionally verified`, or `Deployed`.

## Required runtime review

1. Inventory Page permissions and company switching.
2. Item and Warehouse list/form behavior plus Warehouse tree actions.
3. Stock Entry purposes, item rows, valuation totals, submission, cancellation, and ledger links.
4. Pick List source documents, scanning, locations, submission, and completion status.
5. Stock Reconciliation quantities, valuation, difference totals, posting, and cancellation.
6. Serial No and Batch traceability, linked transactions, status, expiry, and ledger access.
7. Stock reports, filters, exports, charts, and drill-down links.
8. Mobile item-table scrolling and light/dark themes.

## Next development target

Continue with Assets, then Manufacturing. Before expanding beyond those modules, extract stable shared Page, list, form-summary, progress, report, tree, and responsive-grid primitives demonstrated across Procurement, Finance, Sales, and Inventory.

Do not treat this handoff as runtime acceptance or deployment readiness.
