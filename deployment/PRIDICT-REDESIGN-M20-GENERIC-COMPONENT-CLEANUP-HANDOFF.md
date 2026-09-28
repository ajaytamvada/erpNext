# Pridict Redesign M20 Generic Component Cleanup Handoff

Date: September 28, 2026

Status: Generic secondary-screen component migration and observer-render cleanup complete in source. Runtime visual review and functional verification remain pending.

## Objective

Move the generic secondary-screen form presentation onto the shared Pridict document primitives, prevent generic and dedicated summaries from appearing together, and remove avoidable observer-triggered markup rewrites without changing native ERPNext behavior.

## Generic adapter changes

The generic adapter now uses the shared document summary and native document-region helpers for secondary forms without a dedicated adapter.

Generic summaries intentionally contain only:

- module context;
- native document identity;
- native document state;
- a short statement that native fields, permissions, validation, links, and actions remain preserved.

They do not enumerate arbitrary document fields, duplicate totals, infer business state, or replace native controls.

The dedicated-screen suppression list now includes the shared and module-specific document-summary selectors used by Purchasing, Finance, Sales, Inventory, Assets, Manufacturing, Projects, Quality, Support, Administration, and Integrations. This prevents a generic compatibility summary from appearing beside a dedicated presentation.

## Shared component adjustment

`ensureDocumentSummary` no longer emits an empty field-grid container when no fields are configured. Dedicated summaries with fields retain their existing grid. Minimal generic summaries render only their header and preservation guidance.

## Native region preservation

Generic forms add presentation classes to existing native:

- child tables;
- timelines;
- dashboards;
- form links;
- linked-document badges.

The adapter does not move, clone, hide, or replace those regions. Native controllers, permissions, events, validation, and document relationships remain authoritative.

## Observer-render cleanup

Observer-refreshed introductions and progress blocks in Assets, Manufacturing, Projects, Finance, and Sales now use the shared idempotent renderer. Identical markup is not written again.

The remaining direct HTML assignments are limited to:

- creation-time navigation or shell markup;
- customer-facing context creation;
- the detached element used to sanitize tour content;
- the purchasing progress block, which is protected by an existing content signature.

No native business action or state transition was changed.

## Targeted validation

- All 77 current Pridict JavaScript files passed `node --check`.
- All 16 SCSS imports resolved.
- All 31 used Pridict design tokens remained defined.
- All 62 unique JavaScript and CSS hook references resolved.
- The generic adapter includes every current dedicated document-summary selector in its suppression boundary.
- Empty shared-summary field configuration produces no empty field-grid markup.
- Sales retains only its creation-time navigation direct write after the list-introduction migration.
- `git diff --check` passed.

## Validation not performed

- No Frappe runtime or authenticated browser review was performed.
- No broad automated test suite was run.
- No asset build, migration, release image, deployment, or commit was performed.
- No visual or functional acceptance status was advanced.

## Runtime checks still required

- Open representative generic master, setup, secondary transaction, report, tree, and specialist Page routes in each enabled module.
- Confirm generic summaries never appear beside dedicated summaries during initial load, route changes, or delayed form rendering.
- Confirm child tables, timelines, dashboards, links, and actions remain usable for ordinary roles.
- Confirm light/dark themes, long titles, translations, and narrow/mobile viewports.
- Confirm observer refreshes do not cause visible flicker, focus loss, duplicated blocks, or action-menu interruption.

## Next task

Perform a consolidated source-level cleanup review of the remaining dedicated adapters and shared components, limited to duplicated presentation logic, stale selectors, and avoidable observer work. After that pass, hold source implementation for the user-led runtime verification matrix and address only route-specific findings.
