# Pridict Redesign Milestone 2: Finance Source Handoff

Date: September 28, 2026

Status: Source implementation in progress. Not visually reviewed, functionally verified in a Frappe runtime, built, migrated, deployed, or accepted.

## Scope completed in source

- Added a dedicated `Pridict Finance` Page with company and date filters, Profit and Loss-derived revenue and expense metrics, exact overdue receivable and payable counts, an overdue invoice attention queue, report links, permission-aware create actions, and recent permitted financial activity.
- Added Finance to the persistent Pridict shell and changed the executive-home Finance tile to open the new Finance Page.
- Added Finance route classification for Accounting, Financial Reports, Receivables, Payables, Sales Invoice, Payment Entry, Journal Entry, Account, Cost Center, and the six primary financial reports.
- Added a Finance journey bar that keeps the native Accounting workspace available as a compatibility and administration surface.
- Added native-list introductions and filter presets for Sales Invoice, Payment Entry, and Journal Entry.
- Added a native Sales Invoice outstanding-progress treatment using values already loaded by ERPNext list settings.
- Added read-only form summaries for Sales Invoice, Payment Entry, and Journal Entry.
- Added document-state guidance for draft, cancelled, outstanding invoice, submitted payment, and balanced or unbalanced journal states.
- Added presentation tagging for native details, invoice items, payment references, deductions, journal account rows, totals, linked documents, sidebars, timelines, and action containers.
- Added responsive horizontal handling for native financial grids without hiding accounting columns.
- Added report introductions and presentation adapters for Profit and Loss Statement, Balance Sheet, Cash Flow, General Ledger, Accounts Receivable, and Accounts Payable while preserving native filters, calculations, charts, exports, and drill-downs.
- Added native tree presentation adapters for Chart of Accounts and Cost Center routes while preserving native company filters and tree actions.
- Added an additive Sales Invoice form lifecycle hook alongside the existing Payment Entry and Journal Entry hooks.
- Removed the Payment Entry query-field alias from recent-activity retrieval and now resolves its account currency explicitly.
- Added company-currency fallback for Journal Entry activity values.

## Files added

- `pridict_app/pridict/pridict/page/pridict_finance/pridict_finance.json`
- `pridict_app/pridict/pridict/page/pridict_finance/pridict_finance.py`
- `pridict_app/pridict/pridict/page/pridict_finance/pridict_finance.js`
- `pridict_app/pridict/pridict/page/pridict_finance/test_pridict_finance.py`
- `pridict_app/pridict/public/js/finance.js`
- `pridict_app/pridict/public/js/finance/sales_invoice.js`
- `pridict_app/pridict/public/js/finance/payment_entry.js`
- `pridict_app/pridict/public/js/finance/journal_entry.js`
- `pridict_app/pridict/public/scss/pridict/_finance.scss`

## Existing files updated

- `pridict_app/pridict/hooks.py`
- `pridict_app/pridict/public/js/ui/route_context.js`
- `pridict_app/pridict/public/js/ui/shell.js`
- `pridict_app/pridict/pridict/page/pridict_home/pridict_home.py`
- `pridict_app/pridict/public/scss/pridict.bundle.scss`

## Functional-preservation boundary

- No accounting calculations, posting rules, reconciliation behavior, payment allocation, invoice logic, ledger generation, permissions, approvals, required fields, document relationships, report execution, tree actions, or native transaction actions were replaced.
- The new Page reads permitted data and calls the existing Profit and Loss implementation for financial totals.
- List presets use native Frappe route options.
- Form integrations are read-only summaries and CSS classes applied through additive `doctype_js` hooks.
- Report and tree adapters add introductions and presentation classes only; they do not replace report or tree controllers.
- Purchase Invoice remains in the Procurement journey even when opened from Finance links.

## Targeted validation completed

- `node --check` passed for the Finance Page, route context, shared shell, purchasing adapter, Finance adapter, and the Sales Invoice, Payment Entry, and Journal Entry hooks.
- The Finance Page JSON parsed successfully.
- Python bytecode compilation passed for the Finance service and focused test module.
- `git diff --check` passed.
- Generated Finance `__pycache__` files were removed after compilation.

## Validation not completed

- No local Frappe runtime review was available.
- Focused Frappe tests were not executed because the host environment does not provide the project test runtime.
- No asset build, migration, browser capture, workflow transaction, image build, or deployment was run.
- Every Finance screen remains `Implemented in source` only. None is yet `Visually reviewed`, `Functionally verified`, or `Deployed`.

## Required runtime review

Review each route separately in desktop and mobile layouts, with representative permissions and both light and dark themes:

1. Pridict Finance Page.
2. Sales Invoice list and form.
3. Payment Entry list and form, including references and deductions.
4. Journal Entry list and form, including account rows and imbalance states.
5. Profit and Loss Statement, Balance Sheet, Cash Flow, General Ledger, Accounts Receivable, and Accounts Payable.
6. Chart of Accounts and Cost Center trees.
7. Native dialogs, exports, drill-down links, create actions, submit/cancel/amend flows, linked documents, and timelines.

## Next development target

Continue with the Sales and CRM milestone using the same supported architecture:

1. Add a role-focused Sales home.
2. Adapt Lead, Opportunity, Quotation, Sales Order, Delivery Note, and Sales Invoice journeys.
3. Preserve CRM activities, communication timelines, mapped-document actions, pricing, taxes, stock impact, and accounting integration.
4. Reuse the shared shell and extract repeated list/form/report primitives where the Finance and Procurement implementations now demonstrate stable duplication.

Do not treat this handoff as runtime acceptance or deployment readiness.
