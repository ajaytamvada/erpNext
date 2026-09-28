# Pridict redesign milestone 1 handoff

Checkpoint date: 28 September 2026.

Status: implementation started; source checkpoint only. Not visually reviewed, functionally verified in Frappe, built into an image, or deployed.

## Implemented in this checkpoint

- Added an additive persistent Pridict Desk navigation rail with route-aware active module state and a mobile navigation toggle.
- Kept native Frappe search, notifications, help, user menu, routing, page actions, and permissions.
- Added route classification for Page, Workspace, List, Form, Report, and purchasing routes.
- Added a shared page-context label without replacing native page titles or action handlers.
- Added a dedicated `pridict-procurement` Frappe Page with permission-aware company selection, exact-definition purchasing counts, document pipeline, action-required records, create actions, recent activity, and a link to the standard Buying workspace.
- Changed the executive-home Procurement tile to open the new Procurement Page.
- Added purchasing journey navigation across Material Request, Purchase Order, Purchase Receipt, and Purchase Invoice routes.
- Added purchasing list introductions and read-only form summary panels using existing document values. No editable field, DocType metadata, business calculation, status, permission, or native action was replaced.
- Added native-filter presets for the four purchasing lists, using Frappe route options rather than a replacement query layer.
- Added document-specific progress and financial summary fields for Material Request, Purchase Order, Purchase Receipt, and Purchase Invoice.
- Added presentation classes for native detail, item-grid, totals, and linked-document sections without moving or recreating their controls.
- Added mobile navigation backdrop and Escape-key dismissal for the shared shell.
- Added supported additive `doctype_js` handlers for Material Request, Purchase Order, Purchase Receipt, and Purchase Invoice so the Pridict summary refreshes with native form lifecycle and field changes.
- Added per-document list filter presets using native Frappe route options.
- Added list-row progress displays sourced from the fields already loaded by ERPNext list settings: ordered/received, received/billed, billed, and invoice outstanding ratio.
- Added consistent visual treatment for native document action groups, item grids, form sidebars, timelines, and linked-document areas.
- Added read-only document-state guidance for draft, cancelled, ordering, receiving, billing, return, and outstanding-payment states. The guidance points users to native actions and does not create replacement workflow actions.
- Added language-independent native action classification using Frappe button classes, with secondary text matching only as a fallback.
- Added mobile item-table scroll guidance and preserved wide native grids through touch-enabled horizontal scrolling rather than hiding business columns.
- Added `aria-current` state for shared and purchasing navigation plus synchronized mobile navigation `aria-expanded` behavior.
- Added focused Procurement Page tests for guest denial, permitted company selection, metric contract, pipeline contract, and create-permission keys.

## Files

- `pridict_app/pridict/hooks.py`
- `pridict_app/pridict/public/js/ui/route_context.js`
- `pridict_app/pridict/public/js/ui/shell.js`
- `pridict_app/pridict/public/js/purchasing.js`
- `pridict_app/pridict/public/scss/pridict/_shell.scss`
- `pridict_app/pridict/public/scss/pridict/_purchasing.scss`
- `pridict_app/pridict/public/scss/pridict/_procurement.scss`
- `pridict_app/pridict/public/scss/pridict.bundle.scss`
- `pridict_app/pridict/pridict/page/pridict_procurement/`
- `pridict_app/pridict/pridict/page/pridict_home/pridict_home.py`

## Validation completed

- `node --check` passed for the new shared shell, route context, purchasing adapter, and Procurement Page JavaScript.
- Python bytecode compilation passed for the Procurement service and its focused test module.
- `git diff --check` passed for the changed tracked source.
- The Procurement Page JSON was created as a standard Page record in the Pridict module.

## Validation not completed

- The local site at `http://127.0.0.1:8000` was unavailable during this checkpoint.
- The expected Docker CLI was not available at the previously recorded user-level location.
- The host Python environment does not contain `pytest`, so the focused Frappe tests were not executed.
- No asset build, migration, browser capture, workflow transaction, image build, or deployment was run.

## Next targeted step

Restore or locate the isolated Frappe development runtime, migrate the new Page, build the Pridict assets once, and perform a focused visual/interaction review of:

1. Pridict Home with the shared shell.
2. Procurement desktop and mobile layouts in light/dark themes.
3. Material Request, Purchase Order, Purchase Receipt, and Purchase Invoice list/form route adaptation.
4. Navigation cleanup, native actions, item grids, dialogs, and permission-aware content.

## Current development continuation

The current source slice completes the planned source-side purchasing navigation, summary, progress, status-guidance, action, item-table, totals, timeline, and linked-document treatment. It remains unreviewed at runtime. The next development milestone is the Finance module shell and role-focused Finance home, followed by finance lists, forms, reports, and trees using the same reusable architecture. No deployment work should begin before visual and functional review.

Do not treat this source checkpoint as milestone acceptance or deployment readiness.
