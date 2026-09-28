# Pridict Redesign M15 Purchasing Component Migration Handoff

Date: September 28, 2026

Status: Purchasing shared-component migration complete in source. Runtime visual review and functional verification remain pending.

## Objective

Move the first transaction family onto reusable document guidance, item-region, linked-document, and totals presentation while keeping ERPNext's purchasing calculations and controls authoritative.

## Shared component extensions

`pridict_app/pridict/public/js/ui/components.js` now supports:

- compatibility classes for specialized summary headers and field grids;
- guidance tones such as attention and complete;
- reusable native field-section tagging;
- reusable, idempotent mobile child-table scroll notes.

`pridict_app/pridict/public/scss/pridict/_document-components.scss` now provides shared guidance-tone, native totals, and native item-grid presentation.

## Purchasing migration

`pridict_app/pridict/public/js/purchasing.js` now uses the shared components for:

- document identity, native status, configured field summaries, and lifecycle guidance;
- Material Request, Purchase Order, Purchase Receipt, and Purchase Invoice forms;
- item-table section identification;
- taxes and totals section identification;
- native child-table, timeline, dashboard, and linked-document tagging;
- mobile item-grid guidance.

Existing purchasing compatibility classes remain attached, so the approved module-specific visual direction and responsive rules remain active.

## Totals preservation boundary

No totals are copied, recalculated, cached, or rendered from a separate Pridict formula. The implementation only identifies and styles the native form section containing fields such as `taxes` or `grand_total`.

ERPNext remains authoritative for:

- net, tax, grand, rounded, outstanding, advance, and remaining amounts;
- currency conversion and precision;
- taxes and charges templates;
- item-level valuation, stock, and accounting effects;
- returns, debit notes, payment status, and document lifecycle calculations.

## Action preservation

- Native Save, Submit, Cancel, Amend, Update, Create, Make, Print, Email, and menu actions retain their handlers.
- Existing purchasing action-kind classification remains in place for visual hierarchy.
- Mapped-document actions and linked-document navigation are not recreated or intercepted.
- No permission, workflow, required-field, stock, buying, or accounting logic changed.

## Targeted validation

- All 77 current Pridict JavaScript files passed `node --check`.
- All 16 SCSS imports resolved.
- All 31 used Pridict design tokens remained defined.
- A focused simulated-DOM check confirmed idempotent summary rendering, compatibility classes, guidance-tone output, item/totals tagging, and single scroll-note insertion.
- `git diff --check` passed.

## Runtime checks still required

- Draft, submitted, cancelled, returned, closed, stopped, partially received, partially billed, overdue, and paid states as applicable.
- Native totals and taxes visibility across all four purchasing forms.
- Child-row editing, row actions, item dialogs, keyboard navigation, and mobile horizontal scrolling.
- Create/Make mapped-document actions and linked-document counts.
- Workflow, permission, and role-specific action visibility.
- Light and dark theme visual review.

## Next task

Migrate Finance to the shared components while preserving its tree views, accounting report behavior, payment/journal action analysis, currency formatting, and native debit/credit totals.
