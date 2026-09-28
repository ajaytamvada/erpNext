# Pridict Redesign M17 Sales Component Migration Handoff

Date: September 28, 2026

Status: Sales and CRM shared-component migration complete in source. Runtime visual review and functional verification remain pending.

## Objective

Move the Sales and CRM journey onto reusable Pridict document components while preserving lead conversion, customer transactions, pricing, taxes, stock effects, accounting effects, permissions, and mapped-document actions.

## Migrated journey

- Lead
- Opportunity
- Quotation
- Sales Order
- Delivery Note
- Sales Invoice

`pridict_app/pridict/public/js/sales.js` now uses the shared components for document identity, status, configured summary fields, lifecycle guidance, detail sections, item sections, taxes and totals sections, child tables, timelines, linked documents, and mobile item-grid guidance.

## Preserved presentation logic

- Lead qualification and conversion guidance remains specific to Lead status.
- Opportunity guidance continues to distinguish converted and active opportunities.
- Quotation guidance retains order-conversion context.
- Sales Order guidance continues to evaluate delivery and billing progress independently.
- Delivery Note guidance continues to reflect billing completion.
- Sales Invoice guidance continues to reflect the native outstanding amount.
- Existing list progress for opportunity probability, quotation ordering, delivery, billing, and invoice outstanding ratios remains unchanged.

## Native totals and actions

No price, discount, tax, grand total, outstanding amount, delivery percentage, billing percentage, or stock/accounting value is recalculated by Pridict.

Native ERPNext behavior remains authoritative for:

- pricing rules and item rates;
- taxes and charges;
- currency and precision;
- stock posting and returns;
- delivery and billing percentages;
- payment and outstanding status;
- Lead/Opportunity conversion and Quotation/Sales Order/Delivery Note/Sales Invoice mapped-document actions;
- permissions, workflows, submit, cancel, amend, print, and email actions.

## Observer hardening

Sales list-row progress now uses `surface.render` instead of unconditional `innerHTML` replacement. Navigation and list-introduction markup remain direct writes only at initial element creation.

## Targeted validation

- All 77 current Pridict JavaScript files passed `node --check`.
- All 16 SCSS imports resolved.
- All 31 used Pridict design tokens remained defined.
- All 62 JavaScript and CSS hook references resolved.
- Focused simulation confirmed detail, item, multiple totals-section, and single mobile-note tagging.
- Only initial Sales navigation and list-introduction creation retain direct `innerHTML` writes.
- `git diff --check` passed.

## Runtime checks still required

- Lead and Opportunity conversion actions and linked records.
- Quotation to Sales Order conversion.
- Sales Order delivery and billing progress states.
- Delivery Note stock posting, returns, and billing actions.
- Sales Invoice payment, outstanding, return, and accounting states.
- Taxes, totals, item dialogs, child-row actions, keyboard navigation, and mobile scrolling.
- Role-specific permissions, workflows, light/dark themes, and narrow viewports.

## Next task

Migrate Inventory to the shared components while preserving stock-entry purposes, warehouse tree behavior, serial/batch controls, reconciliation logic, item tables, and native stock calculations.
