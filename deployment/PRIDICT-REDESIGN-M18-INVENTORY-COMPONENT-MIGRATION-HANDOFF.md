# Pridict Redesign M18 Inventory Component Migration Handoff

Date: September 28, 2026

Status: Inventory shared-component migration complete in source. Runtime visual review and functional verification remain pending.

## Objective

Move Inventory forms onto reusable Pridict document components while preserving warehouse hierarchy, stock-entry purposes, reconciliation, serial and batch controls, stock-ledger behavior, permissions, and calculations.

## Migrated journey

- Item
- Warehouse
- Stock Entry
- Pick List
- Stock Reconciliation
- Serial No
- Batch

`pridict_app/pridict/public/js/inventory.js` now uses the shared components for document identity, native status, configured summary fields, inventory guidance, child tables, timelines, linked documents, and mobile stock-table guidance.

## Native section presentation

- Stock Entry retains its native item table and `total_amount` section.
- Stock Reconciliation retains its native item table and `difference_amount` section.
- Pick List uses the native `locations` table, with `items` retained as a compatibility fallback.
- Item, Warehouse, Serial No, and Batch retain their native layouts without synthetic totals.

Pridict only tags these existing sections for presentation. It does not duplicate their values or create an alternate stock model.

## Reports and trees

The migration does not replace or restructure:

- Warehouse Tree;
- Stock Balance;
- Stock Ledger;
- Stock Ageing;
- Stock Projected Qty.

Their native filters, calculations, exports, charts, drill-down links, hierarchy actions, and permissions remain intact. Report, tree, and list introductions now use idempotent rendering to avoid observer-driven rewrites.

## Functional preservation

ERPNext remains authoritative for:

- stock quantities and projected quantities;
- valuation rates and stock value differences;
- warehouse and company validation;
- stock ledger and general-ledger posting;
- serial and batch allocation;
- barcode and Pick List operations;
- Stock Reconciliation posting;
- manufacturing-related stock movements;
- submit, cancel, amend, return, and permission behavior.

## Targeted validation

- All 77 current Pridict JavaScript files passed `node --check`.
- Inventory retains only one direct `innerHTML` write, used when initially creating its navigation element.
- All 16 SCSS imports resolved.
- All 31 used Pridict design tokens remained defined.
- All 62 JavaScript and CSS hook references resolved.
- Focused simulation confirmed Pick List location fallback, item/totals classes, and single mobile-note insertion.
- `git diff --check` passed.

## Runtime checks still required

- Stock Entry receipt, issue, transfer, manufacture, repack, return, and cancellation flows.
- Pick List scanning, locations, quantities, completion, and linked fulfilment documents.
- Stock Reconciliation quantity, valuation, difference, posting, and cancellation states.
- Item variants, reorder settings, prices, stock settings, and linked transactions.
- Warehouse Tree navigation and node actions.
- Serial No and Batch ledger links, warranty, delivery, and expiry states.
- Stock report filters, exports, drill-downs, light/dark themes, and mobile layouts.

## Next task

Migrate the remaining dedicated operational adapters—Quality/Support and Administration/Integrations—where their security and domain-specific summaries can use shared components without exposing protected values or flattening workflow-specific guidance.
