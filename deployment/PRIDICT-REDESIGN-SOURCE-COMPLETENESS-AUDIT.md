# Pridict Redesign Source Completeness Audit

Date: September 28, 2026

Status: Source audit complete. Runtime visual review, functional verification, build, migration, deployment, and acceptance remain pending.

## Audit basis

- Authoritative plan: `deployment/PRIDICT-REDESIGN-EXECUTION-PLAN.md`.
- Milestone handoffs: M1 through M21.
- Enabled ERPNext workspace JSON present in this source tree.
- Current Pridict Page metadata, shell navigation, route registry, module adapters, generic fallback adapter, customer-facing adapter, and cross-product adapter.
- Current source is authoritative for implementation. Older screenshots and release records remain dated evidence only.

## Enabled workspace coverage

The source tree contains 16 ERPNext workspaces:

- Accounting
- Assets
- Buying
- CRM
- ERPNext Integrations
- ERPNext Settings
- Financial Reports
- Home
- Manufacturing
- Payables
- Projects
- Quality
- Receivables
- Selling
- Stock
- Support

Every workspace is assigned to a canonical Pridict shell area. Standard workspaces remain available as compatibility and specialist-navigation routes.

## Structural Pridict Pages

The source contains 12 structural Pridict Pages:

- Pridict Home
- Pridict Procurement
- Pridict Finance
- Pridict Sales
- Pridict Inventory
- Pridict Assets
- Pridict Manufacturing
- Pridict Projects
- Pridict Quality
- Pridict Support
- Pridict Administration
- Pridict Integrations

Schema Intelligence remains a separate existing governance Page and is integrated into the shared shell.

## Workspace-link audit

The automated source comparison inspected every Link row in the 16 local ERPNext workspace definitions.

| Link type | Workspace link occurrences | Unique registered routes | Unassigned |
|---|---:|---:|---:|
| DocType | 286 | 214 | 0 |
| Report | 120 | 111 | 0 |
| Page | 6 | 4 specialist Page routes plus shared routes | 0 |

Repeated links across workspaces explain why occurrence counts exceed unique route counts.

## Coverage model

### Dedicated structural adapters

Dedicated module implementations exist for the primary operational journeys:

- Procurement: Material Request, Purchase Order, Purchase Receipt, Purchase Invoice.
- Finance: Payment Entry, Journal Entry, Account, Cost Center, and principal financial reports.
- Sales and CRM: Lead, Opportunity, Quotation, Sales Order, Delivery Note, Sales Invoice.
- Inventory: Item, Warehouse, Stock Entry, Pick List, Stock Reconciliation, Serial No, Batch.
- Assets: Asset, Asset Category, Asset Movement, Asset Repair, Asset Maintenance, Asset Depreciation Schedule.
- Manufacturing: BOM, Production Plan, Work Order, Job Card, Operation, Workstation.
- Projects: Project, Task, Timesheet, Activity Type, including retained Gantt and Kanban behavior.
- Quality: Quality Inspection, Quality Goal, Quality Review, Quality Action, Non Conformance.
- Support: Issue, Service Level Agreement, Warranty Claim.
- Administration and Integrations: safe configuration summaries and grouped operating Pages.

### Generic structural adapter

Every remaining workspace-linked master, setup DocType, secondary transaction, report, tree, and specialist Page is assigned canonical module ownership. When no dedicated adapter exists, the generic adapter provides:

- persistent module context and navigation;
- a module-specific introduction for lists, reports, workspaces, trees, and specialist Pages;
- a safe document identity and status summary for forms;
- preservation of native fields, permissions, validation, links, and actions.

Generic coverage is not equivalent to a screen-specific redesign. Each generic screen still requires separate visual and functional review, and may be promoted to a dedicated adapter when its workflow justifies one.

## Shared product surfaces

- Shared application rail, header integration, route-aware active state, and responsive shell.
- Shared route-aware breadcrumbs and native page-action treatment across Desk page headers.
- Shared document summary, status, field-grid, guidance, native child-table, timeline, and linked-document primitives.
- Customer-facing login, portal, Web Form, public error, notices, release-notice, and footer treatment.
- Assignment, sharing, workflow, email, print, import/export, upload, filter, confirmation, notification, search, loading, empty, message, and keyboard-focus treatment.
- Light and dark design tokens shared across module and cross-product surfaces.

## Confirmed source gaps closed in this audit

- Secondary workspace-linked DocTypes no longer fall back to the Overview shell context.
- Secondary reports now retain their owning module context.
- Sales Funnel, BOM Comparison Tool, Backups, and Print Format Builder receive named module ownership.
- Shared masters with multiple workspace entry points have one canonical shell owner while remaining reachable from every native route.
- Standard Home is explicitly classified as Overview.

## Source hardening verification

The September 28, 2026 hardening pass corrected two implementation defects without changing ERPNext behavior:

- Replaced the undefined `--pridict-warning` reference with the existing `--pridict-warning-text` token on cross-product surfaces.
- Added the shared idempotent `surface.render` helper and applied it to persistent-observer summaries so unchanged markup does not repeatedly mutate the DOM.

Targeted verification after those corrections reported:

- 75 Pridict JavaScript files passed `node --check`.
- 13 Page JSON files parsed successfully and all 13 Page directories contained matching JavaScript, JSON, and Python files.
- 85 readable Python files passed AST parsing.
- 15 SCSS files had balanced braces; all 14 bundle imports resolved; all 31 used Pridict custom properties had definitions.
- All 60 JavaScript and CSS references extracted from `hooks.py` resolved to source files.
- No mojibake signatures were found in the 198 inspected Pridict text files.
- The route registry retained 214 registered DocTypes, 111 registered report routes, four specialist Page routes, and zero unassigned links across all 16 local ERPNext workspaces.
- A simulated DOM assertion confirmed that `surface.render` performs no write for identical markup and exactly one write for changed markup.

These are source-integrity checks only. They do not replace authenticated visual review or workflow testing.

## Shared page-header milestone

The shared header architecture now includes an additive `page_header.js` adapter and `_page-header.scss` partial. The adapter:

- derives module and current-page breadcrumbs from the existing route registry;
- links the module breadcrumb to the appropriate Pridict operating Page or retained native area;
- decorates the existing `.page-actions` container and native buttons without moving, cloning, hiding, or replacing them;
- preserves native button event handlers, permission visibility, dropdowns, workflow actions, and document-state behavior;
- uses idempotent rendering under a persistent child-list observer so dynamically added native actions receive the same presentation.

The adapter passed JavaScript syntax validation, hook/import resolution, CSS token validation, and a focused simulated-DOM check for breadcrumb idempotency and native action classification. Runtime layout and workflow review remain pending.

## Shared document-component milestone

The shared component architecture now includes `components.js` and `_document-components.scss`. Assets, Manufacturing, and Projects use the shared helpers for their structurally equivalent form summaries and native document-region tagging while retaining their existing module-specific classes and visual refinements.

The shared helper centralizes:

- document-state fallback handling without changing native document state;
- safe document identity and status rendering;
- reusable summary field grids and guidance presentation;
- additive tagging of native child tables, timelines, dashboards, form links, and document-link badges;
- idempotent summary rendering for observer-driven refreshes.

Finance, Sales, Inventory, Purchasing, Administration/Integrations, Quality/Support, and the generic fallback remain intentionally unmigrated in this milestone because their summaries contain specialized layouts, guidance states, action analysis, security treatment, or compatibility behavior requiring separate review.

## Purchasing shared-component migration

Purchasing now uses the shared document summary, status, field-grid, guidance-tone, native child-table, timeline, linked-document, and field-section helpers. Native ERPNext totals remain authoritative: the shared component tags and presents the existing totals section rather than copying or recalculating monetary values.

The migration preserves:

- the Material Request, Purchase Order, Purchase Receipt, and Purchase Invoice field selections;
- existing currency, percentage, and check formatting;
- the procurement lifecycle guidance and its attention/complete tones;
- native item grids, taxes, totals, linked documents, document actions, and mapped-document actions;
- the existing action-kind analysis used by the purchasing adapter.

Focused simulation confirmed idempotent summary rendering, compatibility classes, guidance-tone output, native item/totals section tagging, and single scroll-note insertion. Runtime transaction-state and action verification remain pending.

## Finance shared-component migration

Payment Entry and Journal Entry now use the shared document summary, localized status, guidance-tone, accounting-line, totals-section, child-table, timeline, and linked-document helpers. The migration retains Finance-specific currency resolution, debit/credit guidance, action classification, sidebar treatment, and module classes.

Finance report and tree behavior was deliberately left unchanged. Profit and Loss Statement, Balance Sheet, Cash Flow, General Ledger, Accounts Receivable, Accounts Payable, Chart of Accounts, and Cost Center Tree continue to use the existing native report/tree adapters and ERPNext calculations.

The shared field-section helper now tags every distinct matching native section rather than stopping at the first match. This preserves Payment Entry layouts where deductions and difference totals may occupy separate sections and also restores equivalent handling for purchasing taxes and grand totals.

Focused simulation confirmed cancelled-state precedence, translated native status labels, and multiple totals-section tagging. Runtime accounting workflow and report verification remain pending.

## Sales and CRM shared-component migration

Lead, Opportunity, Quotation, Sales Order, Delivery Note, and Sales Invoice now use the shared document summary, status, lifecycle-guidance, native item/totals section, child-table, timeline, and linked-document helpers.

The migration preserves:

- Lead and Opportunity qualification and conversion guidance;
- Quotation validity, pricing, tax, and order-conversion context;
- Sales Order delivery and billing progress;
- Delivery Note stock, return, and billing behavior;
- Sales Invoice outstanding-balance presentation and native accounting links;
- existing list-row funnel, delivery, billing, and outstanding progress indicators.

Sales list-progress rendering now uses the shared idempotent renderer, removing an avoidable observer-triggered rewrite while preserving the same progress markup. Native taxes, totals, stock effects, accounting effects, mapped-document actions, and customer permissions remain authoritative.

Focused simulation confirmed detail, item, separate totals-section, and mobile-note tagging. Runtime CRM conversion and sales transaction verification remain pending.

## Inventory shared-component migration

Item, Warehouse, Stock Entry, Pick List, Stock Reconciliation, Serial No, and Batch now use the shared document summary, status, guidance-tone, native child-table, timeline, and linked-document helpers.

The migration adds explicit native section presentation for:

- Stock Entry item rows and the native `total_amount` section;
- Stock Reconciliation item rows and the native `difference_amount` section;
- Pick List location rows, with `items` retained as a compatibility fallback.

Warehouse Tree and the Stock Balance, Stock Ledger, Stock Ageing, and Stock Projected Qty reports remain native. Their Pridict introductions now render idempotently under the existing observer instead of rewriting unchanged markup.

No quantity, valuation, stock ledger, warehouse, serial, batch, reconciliation, or manufacturing-stock value is calculated by Pridict. Focused simulation confirmed Pick List location fallback, inventory totals tagging, and single mobile-note insertion. Runtime stock workflow verification remains pending.

## Quality, Support, and Administration shared-component migration

Quality Inspection, Quality Goal, Quality Review, Quality Action, Non Conformance, Issue, Service Level Agreement, Warranty Claim, and the allowlisted Administration/Integrations forms now use the shared document summary and native-region helpers.

Administration and integration summaries remain explicit allowlists. The shared `safeDocumentFields` helper accepts only named fields supplied by each configuration entry and does not inspect, enumerate, serialize, or copy the remaining document. Passwords, secrets, tokens, API keys, access keys, webhook URLs, authorization payloads, and other protected values are not included in the configured summary fields.

The migration preserves Quality and Support communication timelines, native child tables, dashboards, form links, and status presentation. Administration guidance remains before the field grid, matching the prior information hierarchy, and continues to distinguish Enabled, Disabled, and Configured states without exposing protected settings.

Focused simulation confirmed allowlist enforcement, protected-value exclusion, guidance ordering, and additional communication-timeline tagging. Runtime workflow, SLA, communication, permission, and secure-settings verification remain pending.

## Generic adapter shared-component cleanup

The generic secondary-screen adapter now uses the shared document summary, status, child-table, timeline, dashboard, form-link, and linked-document primitives. Generic form summaries remain deliberately minimal: they show native document identity, state, and preservation guidance without copying arbitrary fields or attempting to infer workflow-specific data.

The cleanup also:

- suppresses the generic adapter when any dedicated module or shared document summary is already present;
- avoids rendering an empty shared field grid when a summary has no configured fields;
- preserves native fields, controls, permissions, validation, timelines, links, grids, and document actions;
- retains generic coverage as a compatibility presentation rather than claiming screen-specific redesign completion;
- moves observer-refreshed list introductions and progress blocks in Assets, Manufacturing, Projects, Finance, and Sales to the shared idempotent renderer.

The remaining direct HTML assignments are limited to creation-time navigation or shell markup, customer-facing context creation, a detached sanitization element, and the existing purchasing progress write guarded by a content signature. Targeted validation reported 77 JavaScript files passing `node --check`, 16 resolved SCSS imports, 31 resolved Pridict token usages, 62 unique resolved hook references, and a clean `git diff --check`. Runtime review remains pending.

## Final dedicated-adapter cleanup

The generic adapter's dedicated-surface boundary now uses the actual current journey, list-introduction, report-introduction, tree-introduction, planning-introduction, and document-summary class names emitted by each dedicated adapter. Obsolete placeholder selectors were removed. This closes a source-level race where a dedicated list or report could receive generic framing because the generic adapter did not recognize the current dedicated class.

Administration/Integrations, Quality/Support, and the generic adapter now follow the same bounded 20-second initial DOM-observation window as the other module adapters. Route-change and form-refresh hooks remain active after observer shutdown. Only the page-header and cross-product adapters retain intentionally persistent, debounced observers because native actions and transient dialogs can be created at any time during the Desk session.

Finance report and tree introductions now call the shared `surface.ensureIntro` helper directly; the duplicate local helper was removed. A cross-source selector audit found no Pridict SCSS class without a corresponding JavaScript, template, JSON, or Python source reference.

Targeted validation reported 77 JavaScript files passing `node --check`, complete current dedicated-selector coverage, zero obsolete generic suppression selectors, bounded module observers, 16 resolved SCSS imports, 31 resolved Pridict token usages, 62 unique resolved hook references, and a clean `git diff --check`. Runtime review remains pending.

## Remaining named exceptions

- Visual builders and editors: Print Format Builder, Website Theme/Builder, report builders, and other drag-and-drop tools.
- High-risk operations: backup restore/download, migration, destructive deletion, transaction deletion, console, and recovery tools.
- Specialized visualizations: Chart of Accounts tree, accounting statements, Gantt, Kanban, calendars, graph views, and Schema Intelligence visualizations.
- Generated/customer content: PDFs, print formats, letterheads, email bodies, attachments, portals, and tenant-authored website content.
- External/native UI: payment-provider pages, OAuth provider consent, browser file pickers, and operating-system dialogs.
- HRMS and Payroll are not installed in this source tree and are therefore not implemented or claimed.

## Acceptance state

| Area | Implemented | Visually reviewed | Functionally verified | Deployed |
|---|---|---|---|---|
| Shared shell and module routing | Yes, source | No | No | No |
| Module operating Pages | Yes, source | No | No | No |
| Primary lists/forms/reports | Yes, source | No | No | No |
| Secondary workspace-linked routes | Yes, generic source coverage | No | No | No |
| Customer-facing surfaces | Yes, source | No | No | No |
| Cross-product dialogs and states | Yes, source | No | No | No |
| Named exceptions | Partial or shared framing only | No | No | No |

No completion percentage is stated because runtime evidence has not been collected for the enumerated routes and states.
