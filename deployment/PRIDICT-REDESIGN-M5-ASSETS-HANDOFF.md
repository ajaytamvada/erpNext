# Pridict Redesign Milestone 5: Assets Source Handoff

Date: September 28, 2026

Status: Implemented in source only. Not visually reviewed, functionally verified, built, migrated, deployed, or accepted.

## Source scope

- Added the `Pridict Assets` operating Page with company filtering, lifecycle counts, pending work, reports, create actions, and recent activity.
- Added route adapters for Asset, Asset Category, Asset Movement, Asset Repair, Asset Maintenance, and Asset Depreciation Schedule.
- Added report adapters for Fixed Asset Register, Asset Activity, and Asset Maintenance.
- Added native list presets, read-only summaries, lifecycle guidance, grid treatment, linked documents, timelines, and mobile handling.
- Added additive form lifecycle hooks for all six asset records.
- Added `public/js/ui/surface.js` as the first shared utility for visible-page detection, HTML escaping, journey creation, introductions, and cleanup.

## Functional boundary

- Native capitalization, depreciation, accounting, movement, custody, maintenance, repair, stock consumption, disposal, permissions, submission, and report calculations remain unchanged.
- The new code adds permission-aware overview queries and presentation adapters only.

## Validation

- JavaScript syntax checks passed for the shared utility, route context, Assets Page, Assets adapter, and lifecycle hooks.
- Assets Page JSON parsing passed.
- Python compilation passed for the Assets service and focused test module.
- `git diff --check` passed.
- No Frappe test run, asset build, migration, browser review, image build, or deployment was performed.

## Runtime review required

Review the Assets Page; Asset lifecycle forms; movement rows; repair cost and stock consumption; maintenance tasks; depreciation schedules; report filters and drill-downs; permissions; and mobile/light/dark layouts.

## Next development target

Continue with Manufacturing, using the shared surface utility and preserving BOM, Work Order, Job Card, Production Plan, subcontracting, stock, and accounting behavior.

Do not treat this handoff as runtime acceptance or deployment readiness.
