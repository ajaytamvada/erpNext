# Pridict Redesign M16 Finance Component Migration Handoff

Date: September 28, 2026

Status: Finance shared-component migration complete in source. Runtime visual review and functional verification remain pending.

## Objective

Move Payment Entry and Journal Entry presentation onto the shared Pridict document components without changing accounting calculations, currencies, balancing rules, reports, tree views, permissions, or actions.

## Shared component extensions

`pridict_app/pridict/public/js/ui/components.js` now supports:

- optional cancelled-state precedence for adapters whose original presentation checked `docstatus` before `status`;
- optional translation of native status labels;
- module-specific guidance classes alongside shared guidance tones;
- tagging every distinct native section matched by a field list;
- module-specific mobile grid-note classes.

The plural field-section behavior also preserves purchasing layouts where taxes and grand totals may appear in separate sections.

## Finance migration

`pridict_app/pridict/public/js/finance.js` now uses shared components for:

- Payment Entry and Journal Entry identity, status, summary fields, and guidance;
- references and account-line section identification;
- deductions, difference, debit, and credit totals-section presentation;
- native child tables, timelines, dashboards, form links, and linked-document badges;
- mobile accounting-grid guidance.

Finance-specific classes remain attached, preserving the existing four-column desktop summary, responsive layouts, sidebar spacing, action treatment, and accounting-grid design.

## Accounting preservation boundary

No debit, credit, difference, allocation, deduction, exchange-rate, paid, received, or outstanding value is recalculated by Pridict.

ERPNext remains authoritative for:

- Journal Entry balancing and validation;
- Payment Entry allocations and deductions;
- account currencies and exchange rates;
- general-ledger posting and cancellation;
- accounting dimensions and references;
- submit, cancel, amend, reconciliation, and ledger navigation behavior.

## Reports and trees

The migration does not modify Finance report or tree adapters. Native behavior remains intact for:

- Profit and Loss Statement;
- Balance Sheet;
- Cash Flow;
- General Ledger;
- Accounts Receivable and Accounts Payable;
- Chart of Accounts;
- Cost Center Tree.

## Targeted validation

- All 77 current Pridict JavaScript files passed `node --check`.
- All 16 SCSS imports resolved.
- All 31 used Pridict design tokens remained defined.
- All 62 JavaScript and CSS hook references resolved.
- Focused simulation confirmed translated status output, cancelled-state precedence, and tagging of multiple distinct totals sections.
- `git diff --check` passed.

## Runtime checks still required

- Payment Entry Receive, Pay, and Internal Transfer flows.
- Allocation, deduction, write-off, exchange-rate, and difference states.
- Balanced and unbalanced Journal Entries.
- Draft, submitted, cancelled, amended, and permission-restricted states.
- Native ledger links, references, print, email, and workflow actions.
- Report filters, charts, exports, drill-downs, and tree operations.
- Light/dark themes and narrow/mobile viewports.

## Next task

Migrate Sales and CRM to the shared document components while preserving funnel progress, customer lifecycle guidance, taxes, totals, delivery/billing progress, and mapped-document actions.
