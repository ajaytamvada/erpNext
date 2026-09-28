# Pridict redesign execution plan

Plan date: 28 September 2026.

Status: plan for review only. No product code, image, deployment, live configuration, customer data, or broad test suite was changed while preparing this plan.

## Objective and correction

Pridict must become a consistently branded, modern enterprise ERP across enabled modules, workspaces, lists, forms, reports, portals, help, onboarding, emails, errors, and release communication while preserving ERPNext business behavior.

The prior completion statement is not a reliable description of the intended product redesign. The dated evidence proves that routes rendered, shared styling loaded, selected screenshots had no document-level horizontal overflow, and some branding was reconciled. It does not prove that ordinary workspaces, lists, forms, and reports received the structural redesign shown by the approved reference.

The current implementation is best described as:

- a structurally custom Pridict executive home;
- a large shared CSS skin over native Frappe/ERPNext layouts;
- a small global JavaScript bootstrap for branding, theme control, and help-link filtering;
- targeted styling for selected transaction routes;
- branding setup and reconciliation hooks;
- separate, genuinely custom Schema Intelligence pages and governance functionality.

The correction is to preserve those assets and functional components, stop treating generic styling as completed redesign work, and build a reusable Pridict interface layer that carries the approved hierarchy into ordinary ERP use.

## Evidence basis and chronology

| Evidence class | Source | What it proves | Limit |
|---|---|---|---|
| Current source inspected on 28 September 2026 | Pridict hooks, assets, Pages, and setup source | What code exists in this workspace now | Does not prove the same code is active in a browser or deployed |
| Approved visual direction | `design/reference-dashboard.png`, editable executive-home design, rendered preview | Desired shell, hierarchy, density, navigation, cards, role-focused home patterns, and light/dark direction | Sample data and the UNIFIED name are reference content, not product requirements |
| Dated local runtime evidence | 17 and 21 September screenshots and capture manifests | Those exact local routes rendered at those dates and viewports | A screenshot, route load, styling, or no-overflow result is not structural or functional acceptance |
| Dated UAT release evidence | 23 September release record in `deployment/PRIDICT-HANDOFF.md` | Pridict 0.1.0 and Schema Intelligence Milestone 3 were deployed and smoke-verified on UAT | This turn did not independently perform a new authenticated UAT visual review |

Important current-source findings:

- `pridict_app/pridict/hooks.py` includes one Desk CSS bundle, one Desk JavaScript bundle, matching web bundles, branding hooks, and Schema Intelligence scheduling. It does not register purchasing-specific form, list, workspace, or page adapters.
- `pridict_app/pridict/public/js/pridict.bundle.js` adds the Pridict root class, changes the navbar logo destination to `/app/pridict-home`, adds a theme button, and filters selected upstream help links. It does not provide a persistent shared application shell or route adapters.
- `pridict_app/pridict/public/scss/pridict.bundle.scss` is approximately 91 KB and contains broad selectors against Frappe DOM structures. It includes route-specific styling for Purchase Order and Purchase Invoice, but no equivalent structural implementation for Material Request or Purchase Receipt.
- `pridict_home.js` creates a purpose-built sidebar and dashboard, but its navigation sends users back into standard routes such as Buying, reports, workflows, and forms. Its shell is page-local rather than shared.
- The 21 September capture set contains explicit purchasing evidence for Buying, Purchase Order list/form, and Purchase Invoice list/form. It does not contain equivalent Material Request or Purchase Receipt list/form captures.
- The dated UI milestone itself describes Buying, Purchase Order list/form, and reports as native structures with product-wide styling. That description is accurate and explains the current mismatch.

## 1. Concrete gaps

### What currently exists

| Area | Current implementation | Keep |
|---|---|---|
| Brand assets and product title | Pridict wordmark, icon, favicon, splash, app title, Navbar/Website/System settings | Yes |
| Theme foundation | Shared tokens, light/dark variables, persistent theme selection | Yes, refactor into explicit tokens and components |
| Executive home | Custom Frappe Page with permission-aware data, sidebar, filters, KPIs, tasks, business links, activity, and chart | Yes, integrate into shared shell |
| Schema Intelligence | Custom page, governance DocTypes, APIs, tests, and role handling | Yes, adopt shared shell without changing functionality |
| Generic visual layer | Extensive CSS for shell, workspaces, lists, forms, reports, dialogs, portal, login, print preview, and responsive containment | Yes as a compatibility layer, not as redesign completion |
| Branding reconciliation | Idempotent setup for names, logos, support destination, optional upstream learning/help links, and email footer behavior | Yes |
| Release controls | Versioned image, backup, verification, release-state, and rollback tooling | Yes, use only after milestone acceptance |

### What is only restyled

- Standard Frappe Workspace pages, including Buying.
- Standard Frappe List View toolbars, filter sidebar, rows, pagination, and view switching.
- Standard ERPNext forms, tabs, sections, child tables, timelines, dashboards, and action menus.
- Query and script reports, their filters, result grids, charts, and export controls.
- Most trees, calendars, Kanban boards, dashboards, dialogs, dropdowns, portal pages, and print-preview chrome.
- Purchase Order and Purchase Invoice routes have more targeted CSS but still use native layout hierarchy.
- Material Request and Purchase Receipt currently receive only broad generic styling.

### What needs structural redesign

- One persistent Pridict navigation system across executive home, module homes, lists, forms, and reports.
- One route-aware header with stable search, company context where applicable, notifications, help, user menu, and theme control.
- Consistent breadcrumbs, screen title, document identity/status, primary actions, secondary actions, and overflow actions.
- A reusable content frame with predictable width, density, section hierarchy, side panels, responsive behavior, and state handling.
- Role-focused module landing pages, beginning with Procurement, rather than a styled standard Buying workspace.
- Lists that present useful business columns, filters, status, and actions as designed operating screens.
- Transaction forms that prioritize document identity, parties, dates, status, items, amounts, linked documents, and next actions while retaining native controls.
- Reports that consistently separate context, filters, summaries, result data, and export/actions.
- Customer-facing branding for unreviewed channels and runtime states.

### Implementation gaps

- No shared shell component exists outside the executive-home page.
- No route classification or adapter registry exists for Workspace, List, Form, Report, Tree, Calendar, Kanban, or portal contexts.
- No Procurement Page exists as a structural implementation of the approved Procurement Home direction.
- No purchasing-specific JavaScript is registered through supported hooks.
- No reusable document header, status treatment, action cluster, summary strip, linked-document panel, items-table wrapper, totals panel, or responsive drawer exists.
- The monolithic SCSS bundle mixes tokens, shell rules, generic fixes, route-specific behavior, responsive rules, and branding.
- DOM selectors depend heavily on framework class names and route attributes without an explicit compatibility boundary.
- The executive-home sidebar disappears when the user enters a normal ERP route.
- Navigation labels are not governed by one role-aware information architecture.

### Visual-review gaps

- No approved structural review exists for Material Request list/form or Purchase Receipt list/form.
- Purchase Invoice evidence is an empty list and new-form state, not a complete realistic journey.
- Purchase Order screenshots demonstrate restyling, not the target shared shell or transaction layout.
- Current screenshots do not prove long names, many statuses, discounts, taxes, multi-currency, long item tables, serial/batch data, attachments, comments, validation messages, or linked-document density.
- Ordinary-role visual review is incomplete outside a narrow Purchase User Purchase Order slice.
- A new authenticated UAT visual baseline has not been produced in this planning turn.
- Dark/light and desktop/mobile captures were treated as aggregate coverage rather than independent screen acceptance.

### Functional-testing gaps

- The Material Request → Purchase Order → Purchase Receipt → Purchase Invoice journey has not been recorded as a focused redesign regression flow.
- Create-from-document actions, mapped-document dialogs, submit/cancel/amend/return behavior, approvals, assignments, comments, attachments, print, email, and timeline interactions require targeted checks.
- List bulk actions, filters, view switching, paging, sorting, keyboard navigation, link search, autocomplete, and permission-filtered results require targeted checks.
- Item-grid editing, row operations, serial/batch dialogs, pricing, taxes, totals, currency conversion, and recalculation require regression checks.
- Direct route/API permissions and User Permission restrictions require representative Purchase User and Purchase Manager checks.
- Loading, validation, conflict, permission denied, server error, offline/retry, session expiry, and empty states are not fully accepted.
- Populated portal transactions, remaining email variants, and visual PDF verification remain incomplete.

### Deployment work

- Do not build a release image during small visual iterations.
- Implement and review the purchasing milestone locally in coherent slices.
- After acceptance, run focused source checks, targeted functional checks, and one clean production asset build.
- Build one immutable candidate image from an identified source revision only after local acceptance.
- Create a fresh verified backup and snapshot before any UAT cutover.
- Require separate authorization for UAT deployment.
- Track deployed status separately from implemented, visually reviewed, and functionally verified status.

## 2. Shared interface architecture

### Architecture principles

1. Preserve Frappe routing, permissions, document models, controllers, report engines, and native business controls.
2. Add a Pridict presentation and navigation layer around supported native surfaces rather than rewriting ERPNext as a separate frontend.
3. Use explicit route adapters instead of accumulating unrelated CSS selectors and mutation observers.
4. Use native page, list, form, and report lifecycle events to synchronize presentation.
5. Keep a compatibility layer for framework DOM differences and isolate it from product components.
6. Prefer configuration and public hooks; document every override or monkey patch and give it a targeted regression test.
7. Make mobile intentional: fixed desktop rail, accessible mobile drawer, safe sticky actions, and honest horizontal scrolling for irreducible business grids.

### Proposed layers

| Layer | Responsibility |
|---|---|
| Design tokens | Color, type, spacing, elevation, borders, radii, focus, status, density, breakpoints, motion |
| Shared shell | Persistent product rail, top header, route context, content frame, mobile drawer, skip link |
| Route context | Current module, screen type, DocType/report, document state, visible navigation, active item |
| Page header | Breadcrumbs, title, identity, status, primary action, secondary actions, overflow actions |
| Surface adapters | Workspace/Page, List, Form, Report, Tree/Calendar/Kanban, Portal |
| Business components | KPI cards, queues, status badges, summaries, tables, totals, linked documents, activity |
| Module configuration | Navigation, labels, shortcuts, summaries, list columns, layout policies |
| Compatibility layer | Narrow lifecycle bridges and selectors for pinned Frappe v15 structures |
| Evidence hooks | Stable screen and state identifiers for capture and acceptance records |

### Navigation sidebar

- Mount one Pridict sidebar at the Desk shell level, not only inside executive home.
- Build items from a controlled module map filtered by route access, Workspace visibility, DocType read permission, and relevant roles.
- Keep internal Workspace and DocType identifiers unchanged; labels may show Procurement, Finance, Sales, Inventory, Manufacturing, Projects, Quality, Support, Website, Administration, and Schema Intelligence.
- Highlight the active module and screen across Page, Workspace, List, Form, and Report routes.
- Support compact desktop mode and an accessible mobile drawer.
- Preserve operator/developer surfaces for authorized roles without presenting them as ordinary business modules.
- Do not infer authorization from the sidebar; direct route/API permissions remain enforced by Frappe.

### Header, breadcrumbs, and actions

- Retain native global search/command behavior, notifications, help, user menu, and theme persistence.
- Recompose their placement without replacing underlying event handlers.
- Show company context only where meaningful and never imply it changes document data unless the native screen supports it.
- Normalize route breadcrumbs into the main page header.
- Preserve native action buttons and handlers. The adapter may group their containers but must not recreate actions from labels.
- Emphasize the native primary action; keep secondary and overflow actions permission- and state-driven.
- Mobile must keep every action reachable.

### Dashboard and module pages

- Keep `/app/pridict-home` as executive overview but remove its duplicate private shell after the shared shell is ready.
- Create a dedicated Procurement Page because the approved direction requires a role-focused operating home that a standard Workspace cannot provide alone.
- Use permission-aware real data. New calculations require approved definitions and reconciliation sources.
- Retain standard Workspaces as compatibility/administration surfaces until each module receives an accepted role-focused home.

### Lists, forms, and reports

- Preserve List View loading, permissions, filters, sorting, pagination, selection, saved filters, view switching, and row navigation.
- Add the Pridict header, filter presentation, status, configured business columns, density, states, and responsive rows through a list adapter.
- Preserve actual Frappe form controls and values. Do not create parallel editable controls.
- Use existing DocType tabs and sections as initial semantic grouping. Apply card/grid composition without metadata changes in this milestone.
- Keep the native item grid, grid dialogs, calculations, timeline, assignments, tags, attachments, comments, and document dashboard accessible.
- Any later field-order, hidden-field, or Property Setter proposal requires separate review.
- Preserve query/script report execution, filters, prepared reports, grouping, charts, totals, export, print, and permissions.
- Add shared report context, filter, summary, result, and state regions without inventing calculations.

### Supported customization and override risk

Exact hook names and lifecycle methods must be confirmed against the pinned Frappe 15 source before implementation.

| Approach | Use | Risk |
|---|---|---|
| App CSS/JS bundles and Frappe Page source | Shared shell, components, adapters, module homes | Low to moderate; supported but DOM compatibility matters |
| `doctype_js` and list-view hooks/settings | Form lifecycle, summaries, indicators, columns | Low to moderate when additive |
| Workspace configuration/custom HTML blocks | Small supported workspace enhancements | Moderate; insufficient alone for structural Procurement home |
| Native page/form/list lifecycle events | Synchronize adapters without replacing controllers | Moderate; verify cleanup across routes |
| Presentation-only DOM reparenting | Group existing containers while retaining controls | Moderate to high; isolate and test upgrades |
| Monkey patching Frappe classes/render methods | Only for a documented unsupported gap | High; explicit approval, version guard, upgrade tests |
| Core source edits or copied Frappe frontend | Not recommended | Very high |
| Complete independent frontend | Not recommended for this objective | Very high; duplicates permissions, metadata, workflows, and reports |

No server-side DocType class override is currently justified.

## 3. First implementation milestone: purchasing

### Journey and boundary

The first milestone is the complete visible journey:

`Pridict Home → Procurement → Material Request list/form → Purchase Order list/form → Purchase Receipt list/form → Purchase Invoice list/form`

It includes shared shell work required by those screens. It does not redesign unrelated modules, change purchasing policy, or add business calculations.

### Pridict Home

Current state: structurally custom and deployed, but it owns a private sidebar that does not continue into normal routes.

Visible changes:

- Replace the page-local sidebar with the shared Pridict shell.
- Keep executive KPIs, attention queue, business areas, activity, chart, company, and period controls.
- Make Procurement a clear business-area entry and keep it active on Procurement routes.
- Align header, breadcrumbs, actions, content width, cards, states, and mobile navigation with the shared system.
- Preserve the permission-aware API and existing financial reconciliation behavior.

### Procurement home

Current state: no structural Procurement home exists. `/app/buying` is a styled standard Workspace.

Recommended implementation: a dedicated Frappe Page linked as Procurement while preserving the standard Buying workspace for compatibility and authorized configuration access.

Visible layout:

- Shared sidebar with Procurement active.
- Header with `Procurement`, company context, optional period context, and approved quick actions.
- KPI row initially limited to approved native states such as pending Material Requests, Purchase Orders to receive, Purchase Orders to bill, and overdue/open Purchase Invoices.
- `Action required` panel for permitted documents needing review or follow-up.
- `Purchasing pipeline` for Material Request → Purchase Order → Purchase Receipt → Purchase Invoice.
- Permission-aware quick actions for creating each purchasing document.
- Supplier/item shortcuts and recent permitted procurement activity.
- Mobile single-column composition with stacked stages and an accessible action menu.

### Material Request list

Current state: generic List View styling only; no route-specific implementation or recorded 21 September capture.

Visible layout:

- Header: Procurement / Material Requests, count, view selector, refresh, filters, and native add action.
- Business columns: ID/title, Purpose, Company, Requested By, Schedule Date, Status, ordered progress where available, and modified time.
- Native status badges for draft, pending, stopped, cancelled, ordered, partially ordered, and transferred states.
- Accessible filter chips for Company, Purpose, Status, Schedule Date, Requested By, and type while retaining the full filter builder.
- Mobile rows show purpose, schedule date, status, and progress below the identifier.
- Empty state explains the document purpose without changing create permission or behavior.

### Material Request form

- Header: identifier/title, native status, Purpose, Company, owner/modified context, and native Save/Submit/action menus.
- Summary strip: Purpose, Schedule Date, Company, warehouse context, and requested/ordered progress when present.
- Grouping: request details; items; quantities and warehouse/date requirements; configured accounting dimensions; terms/more information.
- Full-width native items table emphasizing Item, Description, Required By, Quantity, UOM, Warehouse, and native progress fields.
- Linked documents: RFQs, Supplier Quotations, Purchase Orders, Stock Entries, and other permitted native links.
- Preserve submitted Purchase-purpose `Create → Purchase Order` and all mapped-document behavior.
- Keep timeline, comments, attachments, assignments, tags, and sharing accessible.

### Purchase Order list

Current state: route-specific styling and dated populated screenshots; native List View structure.

Visible layout:

- Header: Procurement / Purchase Orders with native view, refresh, filter, add, and overflow controls.
- Business columns: Supplier, Status, Transaction Date, Required By/Schedule Date, Grand Total, Currency, received percentage, billed percentage, and ID.
- Clear treatment for To Receive, To Bill, To Receive and Bill, Completed, On Hold, Closed, and Cancelled.
- Supplier, Company, Status, date, received, and billed filters while retaining advanced filters.
- Mobile rows prioritize Supplier, Status, Required By, Grand Total, and receive/bill progress.
- Preserve bulk actions, saved filters, likes/comments, paging, sorting, and alternate views.

### Purchase Order form

- Header: ID, Supplier, native status, receive/bill progress, Grand Total, and native Save/Submit/Cancel/Amend/Print/Email/Create actions.
- Summary strip: Supplier, Company, Transaction Date, Required By, Currency/Price List, Target Warehouse, and configured payment terms.
- Grouping: supplier/order details; items; taxes and charges; totals; terms; additional information.
- Full-width native items table emphasizing Item, Description, Required By, Quantity, UOM, Warehouse, Rate, Amount, received quantity, and billed amount.
- Totals panel emphasizes native Net Total, Taxes, Grand Total, Rounded Total, advances, and remaining values.
- Linked documents: Material Requests, RFQs, Supplier Quotations, Purchase Receipts, Purchase Invoices, Payments, subcontracting documents, and returns as applicable.
- Native `Create` actions remain state- and permission-driven; no duplicate custom business actions.
- Mobile keeps totals and actions reachable without covering the native item grid.

### Purchase Receipt list

Current state: generic List View styling only; no route-specific implementation or recorded 21 September capture.

Visible layout:

- Header: Procurement / Purchase Receipts with native add, view, refresh, filters, and bulk controls.
- Business columns: Supplier, Posting Date, Status, Company, Grand Total, Return state, Purchase Order reference summary where available, and ID.
- Filters for Supplier, Company, Posting Date, Status, Return, and warehouse criteria while retaining advanced filtering.
- Native status treatment for Draft, To Bill, Completed, Return, Closed, and Cancelled.
- Mobile rows prioritize Supplier, Posting Date, Status, Grand Total, and return/billing state.

### Purchase Receipt form

- Header: ID, Supplier, native status, return indicator, billing progress, Grand Total, and native actions.
- Summary strip: Supplier, Company, Posting Date/Time, Accepted Warehouse, Rejected Warehouse when used, Currency, and linked Purchase Order context.
- Grouping: supplier/receipt details; items; stock/warehouse details; taxes and valuation; totals; transport/quality/additional information according to enabled fields.
- Items table prioritizes Purchase Order reference, Item, Accepted Quantity, Rejected Quantity, UOM, Warehouse, Batch/Serial controls, Rate, and Amount.
- Keep native quality inspection, batch/serial, putaway, rejected-material, and stock behavior intact.
- Linked documents: Purchase Orders, Quality Inspections, Purchase Invoices, Landed Cost Vouchers, native ledger/accounting references, and returns.
- Preserve native invoice creation, return, print, email, submit, cancel, and amend behavior.

### Purchase Invoice list

Current state: route-specific styling and dated empty/new-form screenshots; no realistic completed journey evidence.

Visible layout:

- Header: Procurement / Purchase Invoices with native add, view, refresh, filters, bulk, and report controls.
- Business columns: Supplier, Supplier Invoice No., Posting Date, Due Date, Status, Grand Total, Outstanding Amount, Currency, and ID.
- Native treatment for Draft, Unpaid, Overdue, Partly Paid, Paid, Return, Debit Note Issued, Cancelled, and internal-transfer states.
- Filters for Supplier, Company, Posting/Due Date, Status, Outstanding, and return state.
- Mobile rows prioritize Supplier, invoice number, Due Date, Status, Grand Total, and Outstanding Amount.

### Purchase Invoice form

- Header: ID, Supplier, supplier invoice number, native status, payment/outstanding state, Grand Total, and native actions.
- Summary strip: Supplier, Company, Posting Date, Bill No./Date, Due Date, Currency/Price List, and linked Purchase Order/Receipt context.
- Grouping: supplier/invoice details; items; taxes and charges; totals; payment/accounting dimensions; terms; additional information.
- Items table prioritizes Purchase Order/Receipt references, Item, Quantity, UOM, Rate, Amount, Expense Account, Cost Center, and enabled tax fields.
- Totals panel emphasizes native Net Total, Taxes, Grand Total, Outstanding Amount, advances, write-off, and payment schedule.
- Linked documents: Purchase Orders, Purchase Receipts, Payments, Journal Entries, Debit Notes/returns, and General Ledger links where permitted.
- Preserve native accounting dimensions, tax withholding, advances, payment schedule, submit/cancel/amend, return/debit-note, payment, print, and email behavior.

### Purchasing milestone functional checks

- Navigate the full journey through the shared shell and breadcrumbs.
- Create/save a Material Request and verify required fields and validation.
- Submit a Purchase-purpose Material Request and create a Purchase Order through the native mapped-document action.
- Submit a Purchase Order and create a Purchase Receipt through the native action.
- Submit a Purchase Receipt and create a Purchase Invoice through the native action.
- Verify originating/resulting links and native statuses at every transition.
- Check one cancellation/return path only in isolated test data after the primary journey passes.
- Exercise Purchase User and Purchase Manager access, company User Permissions, direct routes, and direct API reads.
- Verify list filters, sorting, paging, selection, alternate views, item-grid editing, comments, attachments, print preview, and email dialog without external delivery.

## 4. Full-product rollout

Purchasing is the first milestone, not the project boundary. Later milestones reuse the same shell and adapters.

| Rollout area | Enabled workspaces/surfaces | Primary reusable components | Genuine exceptions |
|---|---|---|---|
| Finance | Accounting, Financial Reports, Payables, Receivables | Module home, list, transaction form, report shell, KPI/aging summaries, tree | Chart of Accounts, reconciliation, payment allocation, financial statements |
| Sales and CRM | CRM, Selling | Module home, lists/forms, transactions, pipeline, activity | Opportunity pipeline, mappings, communications |
| Inventory and delivery | Stock | Module home, item/warehouse lists/forms, transactions, reports | Stock Entry purposes, serial/batch, pick list, delivery, stock ledger |
| Assets | Assets | Module home, list/form, summary/totals, reports | Lifecycle, depreciation, maintenance, movement |
| Manufacturing | Manufacturing | Module home, list/form, tables, status, links | BOM tree, Work Order operations, Job Cards, planning |
| Projects | Projects | Module home, list/form, activity, Kanban | Gantt, dependencies, time tracking, costing |
| Quality | Quality | Module home, list/form, readings, status | Inspection readings/templates and non-conformance |
| Support | Support | Module home, list/form, activity, SLA status | Email threading, SLA timers, escalation |
| Website and portal | Website, Web Forms, Customer/Supplier portal | Public shell, navigation, cards/tables, forms, states | Builder/editor, tenant content, portal controllers |
| Administration | Users, Pridict Settings, Tools, Build | Shared shell and cautious adapters | Recovery, developer, permission, secret, and system screens |
| Integrations | Integrations, Pridict Integrations | Shared shell, list/form adapters, provider cards | Truthful provider names, callbacks, secrets, marketplace links |
| Product governance | Schema Intelligence | Shared shell and page header | Graph, comparison, review/governance workflows |
| Cross-product | Search, dialogs, notifications, onboarding, print, email, errors | Shared primitives and state patterns | Generated content, letterheads, provider errors, legal notices |

Distinct screen types must be inventoried separately: role-focused module homes; retained Workspaces; list/image/report/dashboard/calendar/Kanban/tree/Gantt views; new/draft/submitted/cancelled/amended/returned forms; master and transaction forms; child-table-heavy forms; query/script/prepared/financial/ledger reports; mapping/search/filter/print/email/share/workflow/error dialogs; login/recovery/session/permission/not-found/maintenance/server states; portal/Web Forms; print/PDF; emails; notifications; and release/help content.

Each exception must be named, designed for its purpose, and accepted separately. It is not complete merely because the shared shell appears around it.

## 5. Branding

### Customer-facing plan

- Keep Pridict title, wordmark, icon, favicon, splash, and support destination through supported settings and hooks.
- Carry Pridict navigation, header, typography, controls, status, empty/loading/error presentation into ordinary Desk routes.
- Publish `documentation/pridict/` guides through an approved help destination before adding in-product links.
- Add contextual help only when maintained content exists for the active version/workflow.
- Create Pridict purchasing onboarding instead of only removing upstream learning actions.
- Review invitation, reset, verification, assignment, share, workflow, print/email dialog, and notification output with non-delivery capture tests.
- Review populated Customer/Supplier portal states, Web Forms, public errors, and session flows in both themes and narrow layouts.
- Create a release-notice format showing version, visible changes, limitations, support, and required notices.
- Provide an accessible About/Open Source Notices surface rather than deleting truthful provenance.

### Truthful boundaries

- Preserve required licence, copyright, attribution, and open-source notices.
- Preserve `frappe`, `erpnext`, DocType, package, table, route, API, and asset identifiers where technical.
- Preserve real provider names in integrations, authentication, callbacks, errors, and operator settings.
- Preserve tenant legal names, letterheads, tax identities, parties, custom print formats, templates, pages, attachments, and user-authored content.
- Never bulk replace database text or customer-authored records.
- Do not relabel a provider, report, or calculation in a misleading way.

## 6. Functional preservation

The redesign must not change:

- business rules or controller logic;
- accounting calculations, ledgers, taxes, currency conversion, rounding, or payment allocation;
- stock valuation, stock ledger behavior, serial/batch handling, warehouses, or quality rules;
- permissions, User Permissions, roles, sharing, assignments, or direct API authorization;
- workflow states, approvals, submit/cancel/amend/return behavior, or document status rules;
- required fields, validation, naming, defaults, or document relationships;
- native transaction actions or mapped-document behavior;
- report calculations, filters, export output, or prepared-report behavior;
- portal permissions, party data boundaries, or tenant-authored content.

### Frontend regression areas

- Route changes and browser back/forward behavior.
- Shell/sidebar cleanup across Page, Workspace, List, Form, and Report routes.
- Native keyboard shortcuts, focus order, skip link, search, and command palette.
- Primary/secondary/menu actions after visual regrouping.
- Unsaved-change prompts and dirty state.
- Form refresh, dependencies, conditional visibility, read-only/mandatory state, and tabs.
- Child-table add/edit/delete, grid dialogs, keyboard entry, paging, and columns.
- Recalculation after quantity, rate, tax, currency, and discount changes.
- List refresh, filters, route options, sorting, paging, selection, bulk actions, indicators, and views.
- Dialog focus trapping, escape/close, stacking, and mobile sizing.
- Timeline, comments, attachments, tags, assignments, sharing, and dashboard links.
- Print, email, download, export, and upload interactions.
- Loading, realtime updates, background jobs, validation, permission errors, and session expiry.

## 7. Acceptance and evidence

### Required state model

Every screen has four independent states:

1. **Implemented**: the intended structural design exists in current source.
2. **Visually reviewed**: a named reviewer accepted that exact screen/state/theme/viewport.
3. **Functionally verified**: targeted interactions and permissions passed with recorded evidence.
4. **Deployed**: the accepted source revision is active in the named environment and verified there.

`Blocked`, `not tested`, `historical capture`, `generic styling`, and `route loaded` are not completion.

### Purchasing baseline on 28 September 2026

| Screen | Implemented | Visually reviewed | Functionally verified | Deployed |
|---|---|---|---|---|
| Pridict Home | Partial: custom page exists; shared shell integration missing | Historical 17 September captures; new review required | Representative API tests/navigation only | Current custom page recorded in 23 September UAT release |
| Procurement home | No: styled Buying Workspace is not target structure | Historical Buying screenshots only | Workspace route/access only | Only styled standard Buying Workspace is deployed |
| Material Request list | No: generic List View styling only | No screen-specific accepted evidence identified | Not verified for redesign | Generic styling may be deployed; target is not |
| Material Request form | No: generic native form styling only | No screen-specific accepted evidence identified | Full journey not verified | Generic styling may be deployed; target is not |
| Purchase Order list | No target structure; route-specific styling exists | Historical populated captures; not structural acceptance | Restricted read/list evidence only | Restyled native list is recorded as deployed; target is not |
| Purchase Order form | No target structure; route-specific styling exists | Historical populated captures; not structural acceptance | Restricted read/render only | Restyled native form is recorded as deployed; target is not |
| Purchase Receipt list | No: generic List View styling only | No screen-specific accepted evidence identified | Not verified for redesign | Generic styling may be deployed; target is not |
| Purchase Receipt form | No: generic native form styling only | No screen-specific accepted evidence identified | Not verified for redesign | Generic styling may be deployed; target is not |
| Purchase Invoice list | No target structure; route-specific styling exists | Historical empty-state captures only | Not verified as journey | Restyled native list is recorded as deployed; target is not |
| Purchase Invoice form | No target structure; route-specific styling exists | Historical new-form captures only | No populated submit/accounting flow | Restyled native form is recorded as deployed; target is not |

### Evidence required per screen

- Exact route, role, company/User Permission context, document state, fixture, source revision, environment, theme, and viewport.
- Desktop light/dark and narrow light/dark review for customer-facing screens.
- At least one realistic populated state plus relevant empty/loading/error/permission state.
- Actions exercised, including primary and overflow actions.
- Administrator/System Manager where relevant and the ordinary role owning the workflow.
- Visual evidence plus machine-readable interaction/test output for functional claims.
- Named exceptions and blocked items.
- Deployment verification against the exact candidate revision.

Explicitly insufficient by themselves:

- a working route;
- shared CSS loading;
- screenshot count;
- absence of horizontal overflow;
- absence of upstream branding text;
- Administrator-only capture;
- empty form/list;
- successful image build;
- broad tests that do not exercise the changed screen.

## 8. Execution discipline

### Milestone workflow

1. Freeze the current source baseline and preserve all existing work.
2. Implement the shared shell and integrate only Pridict Home plus Procurement.
3. Review shell and Procurement before transaction adapters.
4. Implement and review Material Request list/form.
5. Implement and review Purchase Order list/form.
6. Implement and review Purchase Receipt list/form.
7. Implement and review Purchase Invoice list/form.
8. Run the focused purchasing regression and ordinary-role checks.
9. Produce the milestone evidence matrix and concise handoff.
10. After acceptance, run one clean build and prepare an immutable candidate.
11. Stop for separate UAT deployment authorization.

### Inspection and test discipline

- Read only source needed for the current screen and shared component.
- Avoid repeated full-repository scans and unchanged broad tests.
- Use syntax checks, targeted Python tests, and targeted browser interactions for changed areas.
- Do not rebuild a release image between minor CSS/JS iterations.
- Use local asset development for iteration; run production build once the milestone is coherent.
- Re-run only purchasing and shared-shell regressions unless evidence identifies wider impact.
- Add compatibility checks when framework DOM adaptation changes.
- Keep one concise handoff with files, decisions, evidence, blockers, and next action.
- Do not report completion percentages without an enumerated screen/state matrix.

## Recommended implementation approach

Build a shared Pridict Desk shell and route-adapter architecture inside the existing `pridict` app. Deliver Procurement as the first role-focused module page and adapt the four purchasing document types using native Frappe controls and lifecycle hooks.

Do not replace ERPNext's document engine, reports, permissions, or controllers. Do not continue expanding the monolithic stylesheet as the primary architecture. Refactor existing assets into tokens, shell components, reusable surface adapters, and a contained legacy compatibility layer. Use a custom Page for structural module homes and additive form/list hooks for native transaction screens.

## Exact first milestone and files/components involved

### Existing files expected to change

- `pridict_app/pridict/hooks.py`: register supported page/form/list assets after confirming pinned Frappe v15 hook names.
- `pridict_app/pridict/public/js/pridict.bundle.js`: small bootstrap for shell/adapters while retaining theme and branding behavior.
- `pridict_app/pridict/public/scss/pridict.bundle.scss`: bundle entry point with imported component files and preserved legacy rules.
- `pridict_app/pridict/pridict/page/pridict_home/pridict_home.js`: remove duplicate shell and link Procurement to the new page.
- `pridict_app/pridict/pridict/page/pridict_home/pridict_home.py`: only if approved Procurement summaries safely reuse existing services.
- `pridict_app/pridict/setup/install.py`: only if an idempotent supported navigation record is required.

### Proposed components/files

- `pridict_app/pridict/public/js/ui/shell.js`: sidebar, mobile drawer, header integration, cleanup.
- `pridict_app/pridict/public/js/ui/route_context.js`: route/screen/module classification and active navigation.
- `pridict_app/pridict/public/js/ui/page_header.js`: breadcrumbs, title, status, native action grouping.
- `pridict_app/pridict/public/js/ui/adapters/workspace.js`: retained Workspace compatibility.
- `pridict_app/pridict/public/js/ui/adapters/list.js`: List View presentation lifecycle.
- `pridict_app/pridict/public/js/ui/adapters/form.js`: Form presentation lifecycle and cleanup.
- `pridict_app/pridict/public/js/ui/adapters/report.js`: shared report composition.
- `pridict_app/pridict/public/js/ui/components/`: status, summary, links, totals, states, responsive actions.
- `pridict_app/pridict/public/js/modules/procurement.js`: navigation/configuration and route policies.
- `pridict_app/pridict/public/js/purchasing/`: additive purchasing list/form integrations.
- `pridict_app/pridict/public/scss/pridict/_tokens.scss`: design tokens.
- `pridict_app/pridict/public/scss/pridict/_shell.scss`: shared rail/header/content frame.
- `pridict_app/pridict/public/scss/pridict/_components.scss`: reusable primitives.
- `pridict_app/pridict/public/scss/pridict/_surfaces.scss`: list/form/report/workspace adapters.
- `pridict_app/pridict/public/scss/pridict/_purchasing.scss`: purchasing composition.
- `pridict_app/pridict/public/scss/pridict/_legacy.scss`: retained compatibility rules.
- `pridict_app/pridict/pridict/page/pridict_procurement/pridict_procurement.json`: Page definition.
- `pridict_app/pridict/pridict/page/pridict_procurement/pridict_procurement.js`: rendering and interaction.
- `pridict_app/pridict/pridict/page/pridict_procurement/pridict_procurement.py`: permission-aware summary API using approved definitions.
- Focused tests beside the Procurement Page and existing test modules; no broad suite during minor UI iteration.

The exact split may be adjusted for the pinned Frappe bundler after confirming import resolution, but responsibilities should remain separated.

## Decisions genuinely requiring product-owner input

1. Confirm user-facing **Procurement** while the internal Workspace/module identifier remains **Buying**.
2. Confirm whether Procurement replaces the ordinary sidebar destination or appears beside a named `Buying Workspace` compatibility/admin link.
3. Approve exact Procurement KPI definitions and source reports/counts. No metric will be invented.
4. Confirm acceptance roles: recommended minimum Purchase User and Purchase Manager, plus Administrator for recovery/configuration.
5. Confirm whether company context belongs globally or only on pages that can apply it safely.
6. Confirm expanded fixed desktop rail or user-collapsible remembered rail.
7. Confirm whether field order may change through site metadata later. Recommendation: no Property Setter/Customize Form changes in milestone one.
8. Provide or approve purchasing help/onboarding content and publication destination before linking it.
9. Identify mandatory languages beyond English/`en-GB`.
10. Approve the milestone visually before image or UAT release preparation.

## What will visibly change

The Pridict sidebar and header will remain consistent from Home into Procurement, lists, transaction forms, and reports. Procurement will become a designed operating home instead of a styled ERPNext workspace. Material Requests, Purchase Orders, Purchase Receipts, and Purchase Invoices will receive consistent business-focused headers, statuses, actions, field hierarchy, item tables, totals, linked documents, and mobile behavior while retaining the same ERPNext fields, calculations, permissions, workflows, and transaction actions.

Stop point: review and approve or amend this plan before implementation.
