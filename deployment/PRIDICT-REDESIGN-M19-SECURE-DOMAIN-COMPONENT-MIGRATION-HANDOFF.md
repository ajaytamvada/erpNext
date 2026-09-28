# Pridict Redesign M19 Secure Domain Component Migration Handoff

Date: September 28, 2026

Status: Quality, Support, Administration, and Integrations shared-component migration complete in source. Runtime visual review and functional verification remain pending.

## Objective

Move the remaining dedicated domain summaries onto reusable Pridict document components while preserving Quality and Support workflows and preventing protected Administration or Integration values from entering summary markup.

## Migrated Quality and Support screens

- Quality Inspection
- Quality Goal
- Quality Review
- Quality Action
- Non Conformance
- Issue
- Service Level Agreement
- Warranty Claim

These forms now use shared identity, status, field-grid, child-table, timeline, dashboard, and linked-document components. The existing Quality and Support field selections and native metadata labels remain unchanged.

## Migrated Administration and Integration screens

The existing configured Administration and Integration DocTypes now use the shared summary and native-grid components. Their descriptions, state labels, and field selections remain unchanged.

Administration guidance remains before the field grid to preserve the existing information hierarchy. The empty-document label remains `New configuration` rather than the generic document label.

## Protected-data boundary

Added `safeDocumentFields` to `pridict_app/pridict/public/js/ui/components.js`.

The helper:

- accepts an explicit list of permitted field names;
- reads only those named values;
- resolves only their display labels;
- escapes every displayed value;
- never enumerates the full document;
- never serializes hidden or unlisted fields.

The configured summary allowlists contain no password, secret, token, API-key, access-key, webhook-URL, or authorization-payload fields. Sensitive terms found in the source are explanatory warnings stating that those values remain in native protected controls.

## Functional preservation

- Quality inspection readings, acceptance, references, and submission remain native.
- Quality goals, reviews, actions, procedures, and non-conformance workflows remain native.
- Issue communication, assignment, priority, SLA timing, response, and resolution remain native.
- Warranty and Service Level Agreement rules remain native.
- User, role, workflow, notification, import/export, print, system, website, and integration configuration controls remain native.
- Authentication, credentials, provider authorization, backup secrets, and webhook delivery remain native and protected.

## Targeted validation

- All 77 current Pridict JavaScript files passed `node --check`.
- All 16 SCSS imports resolved.
- All 31 used Pridict design tokens remained defined.
- All 62 JavaScript and CSS hook references resolved.
- Focused simulation confirmed that an unlisted secret value was absent from generated markup.
- Focused simulation confirmed Administration guidance order and Quality/Support communication-timeline tagging.
- `git diff --check` passed.

## Runtime checks still required

- Quality submission, acceptance/rejection, review, corrective-action, and non-conformance workflows.
- Issue assignment, communication, SLA pause/resume, response, resolution, reopening, and escalation states.
- Warranty Claim and Service Level Agreement behavior.
- Administration role and permission visibility.
- Integration forms with masked, password, encrypted, authorization, and provider-managed controls.
- Light/dark themes, long values, translated labels, and narrow/mobile viewports.

## Next task

Review and migrate the generic secondary-screen adapter to the shared allowlisted document primitives, then perform a focused cleanup audit for remaining duplicate summary implementations and observer-driven direct markup writes.
