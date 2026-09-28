# Pridict Redesign M21 Final Source Cleanup Handoff

Date: September 28, 2026

Status: Final dedicated-adapter source cleanup complete. Runtime visual review and functional verification remain pending.

## Objective

Perform the final focused source review for duplicate presentation logic, stale selectors, and unnecessary observer work before holding the implementation for user-led runtime verification.

## Duplicate-framing correction

The generic adapter's dedicated-surface suppression list contained obsolete placeholder classes for several module introductions and summaries. Those classes were not emitted by the current dedicated adapters, creating a risk that generic navigation or introductions could be added to an already redesigned list or report.

The suppression boundary now includes the actual current classes for:

- Purchasing journeys, list introductions, and document summaries.
- Finance journeys, list/report/tree introductions, and document summaries.
- Sales journeys, list introductions, and document summaries.
- Inventory journeys, list/report/tree introductions, and document summaries.
- Assets journeys, list/report introductions, and document summaries.
- Manufacturing journeys, list/report introductions, and document summaries.
- Projects journeys, list/report/planning introductions, and document summaries.
- Quality and Support journeys, introductions, and document summaries.
- Administration and Integrations journeys, introductions, and document summaries.

The obsolete placeholder selectors were removed rather than retained as undocumented compatibility behavior.

## Observer cleanup

Administration/Integrations, Quality/Support, and the generic secondary-screen adapter now disconnect their initial DOM observers after 20 seconds, matching the existing lifecycle used by the other dedicated module adapters.

Their route-change and form-refresh handlers remain registered, so later navigation and document refreshes still schedule the adapter directly. The bounded observers exist only to cover delayed initial native rendering.

The page-header and cross-product observers remain persistent by design:

- native page actions can be added after initial route rendering;
- dialogs, notifications, uploads, messages, loading states, and output surfaces can appear at any time;
- both observers already debounce their work before applying presentation classes.

## Shared helper cleanup

Finance report and tree introductions now call `surface.ensureIntro` directly. The equivalent local `ensureSurfaceIntro` implementation was removed.

No other local helper was removed where it also owns filters, event delegation, workflow-specific markup, progress calculation, or native-region behavior.

## Selector audit

A cross-source comparison inspected Pridict class selectors in the SCSS bundle against JavaScript, Python, JSON, and template source references. It found no SCSS Pridict class without a corresponding source reference.

This check establishes source linkage only. It does not prove that every selector matches the exact runtime DOM produced by the installed Frappe and ERPNext versions.

## Functional preservation

- No ERPNext or Frappe core source was changed.
- No business rules, calculations, permissions, workflows, required fields, document links, or native actions were changed.
- No dedicated module route, report, tree, Gantt, Kanban, portal, or customer-facing behavior was removed.
- Generic summaries remain minimal and do not inspect arbitrary document values.

## Targeted validation

- All 77 current Pridict JavaScript files passed `node --check`.
- Every expected current dedicated-surface selector is present in the generic suppression boundary.
- No obsolete generic suppression selector remains.
- Every module-level observer is bounded to its initial rendering window.
- Only the intentionally persistent, debounced page-header and cross-product observers remain unbounded.
- Finance contains no remaining `ensureSurfaceIntro` duplicate helper and uses `surface.ensureIntro` for both report and tree introductions.
- All 16 SCSS imports resolved.
- All 31 used Pridict design tokens remained defined.
- All 62 unique JavaScript and CSS hook references resolved.
- `git diff --check` passed.

## Validation not performed

- No Frappe runtime or authenticated browser review was performed.
- No broad automated test suite was run.
- No asset build, migration, release image, deployment, or commit was performed.
- No visual or functional acceptance status was advanced.

## Recommended next task

Hold broad source development and begin the user-led checks in `deployment/PRIDICT-REDESIGN-RUNTIME-VERIFICATION-MATRIX.md`. Record each problem by exact route, role, document state, theme, viewport, and action. Apply targeted source corrections from those findings before building assets or preparing a release candidate.
