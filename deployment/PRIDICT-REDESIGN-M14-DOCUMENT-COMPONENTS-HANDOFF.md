# Pridict Redesign M14 Document Components Handoff

Date: September 28, 2026

Status: First shared document-component migration complete. Runtime visual review and functional verification remain pending.

## Objective

Replace repeated form-summary implementation with reusable Pridict components while preserving each module's existing content, native ERPNext controls, and module-specific visual refinements.

## Shared components

Added `pridict_app/pridict/public/js/ui/components.js` with:

- `documentStatus`: resolves existing status fields and native `docstatus` presentation without changing document state.
- `ensureDocumentSummary`: creates and idempotently renders a document identity, status, field grid, and guidance card.
- `tagNativeDocumentRegions`: additively tags native child tables, timelines, dashboards, form links, and linked-document badges.

Added `pridict_app/pridict/public/scss/pridict/_document-components.scss` with shared responsive presentation for those primitives.

## First migration boundary

The following structurally equivalent adapters now use the shared components:

- Assets: Asset, Asset Category, Asset Movement, Asset Repair, Asset Maintenance, and Asset Depreciation Schedule.
- Manufacturing: BOM, Production Plan, Work Order, Job Card, Operation, and Workstation.
- Projects: Project, Task, Timesheet, and Activity Type.

Existing module class names remain on every generated block and native region, so the detailed module styles remain active.

## Functional preservation

- Existing displayed fields and module formatters remain unchanged.
- Asset status still prefers the native `status` value before `repair_status` fallback.
- Project cancellation display retains its prior fallback behavior for parity.
- Existing guidance functions remain authoritative.
- Native grids, timelines, dashboards, links, permissions, calculations, and actions are not moved or replaced.
- No Frappe or ERPNext core files were changed.

## Deliberately deferred modules

- Purchasing and Finance contain specialized action analysis, totals, and transaction guidance.
- Sales and Inventory contain specialized progress and guidance states.
- Administration/Integrations contains protected configuration treatment.
- Quality/Support uses a combined domain adapter.
- The generic adapter has a deliberately minimal compatibility summary.

Each deferred adapter should be migrated only after its distinct markup and behavior are represented by an explicit shared-component option rather than flattened into a lowest-common-denominator card.

## Targeted validation

- All 77 current Pridict JavaScript files passed `node --check`.
- All 16 SCSS imports resolved.
- All 31 used Pridict design tokens remained defined.
- All 62 JavaScript and CSS hook references resolved.
- A focused simulated-DOM check confirmed status precedence, single insertion, idempotent rendering, document-name escaping, and additive native-region classes.
- `git diff --check` passed.

## Runtime checks still required

- Summary placement and field wrapping on each migrated form.
- Draft, submitted, cancelled, and module-specific status display.
- Child-table editing, row actions, horizontal scrolling, and keyboard navigation.
- Timeline, dashboard, and linked-document operation.
- Light/dark themes and narrow/mobile viewports.

## Next task

Design shared totals and specialized guidance primitives, then migrate one transaction family at a time. Purchasing should be reviewed first because its totals, mapped-document actions, and lifecycle states define the strongest acceptance requirements.
