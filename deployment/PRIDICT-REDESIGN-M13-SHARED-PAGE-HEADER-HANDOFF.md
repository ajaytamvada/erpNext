# Pridict Redesign M13 Shared Page Header Handoff

Date: September 28, 2026

Status: Shared page-header source implementation complete. Runtime visual review and functional verification remain pending.

## Objective

Provide one consistent page-header layer across Pridict Desk surfaces while preserving the native Frappe and ERPNext title, document status, permissions, actions, menus, and event handlers.

## Implementation

- Added `pridict_app/pridict/public/js/ui/page_header.js`.
- Added `pridict_app/pridict/public/scss/pridict/_page-header.scss`.
- Registered the adapter after the shared shell in `pridict_app/pridict/hooks.py`.
- Imported the stylesheet through `pridict_app/pridict/public/scss/pridict.bundle.scss`.

The adapter adds:

- route-aware module and current-page breadcrumbs;
- module-home navigation using the established Pridict route registry;
- a consistent page-head surface treatment;
- presentation classes for native page actions;
- primary and danger visual classification derived only from existing native button classes;
- responsive breadcrumb truncation and action spacing.

## Functional preservation

- Native page titles remain the source of the visible current-page label when available.
- Native actions are not reordered, cloned, replaced, or assigned new behavior.
- Permission-controlled visibility and document-state action changes remain native.
- Dropdowns, workflow actions, save, submit, cancel, amend, print, email, and mapped-document actions retain their existing handlers.
- No core Frappe or ERPNext source files were changed.

## Targeted validation

- `page_header.js` passed `node --check`.
- All 76 current Pridict JavaScript files passed syntax validation.
- All 15 SCSS imports resolved and all used Pridict design tokens remained defined.
- The new JavaScript hook reference resolved to its source file.
- A focused simulated-DOM check confirmed that breadcrumbs are inserted once, unchanged markup is not rewritten, and native primary/danger action classes are detected without replacing controls.
- `git diff --check` passed after implementation.

## Runtime checks still required

- Breadcrumb title accuracy on module Pages, lists, forms, trees, reports, Gantt, Kanban, and specialist Pages.
- Long document names, translated titles, narrow viewports, and mobile action menus.
- Dynamic action changes after save, submit, cancel, amend, workflow transitions, and mapped-document operations.
- Keyboard focus, dropdown operation, and screen-reader breadcrumb labeling.
- Light and dark theme visual review.

## Next task

Continue the shared interface architecture with reusable document status, summary, linked-document, and totals primitives, applying them first where dedicated module adapters currently duplicate equivalent markup. Keep native document controls and calculations authoritative.
