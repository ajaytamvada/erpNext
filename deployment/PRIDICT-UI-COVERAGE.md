# Pridict UI coverage

Checkpoint date: 21 September 2026. The shared visual system has now been exercised across every routable enabled workspace and representative instances of each major Desk page type in light/dark desktop and 390x844 mobile layouts.

Status meanings: **implemented** means code exists, **tested** requires recorded evidence for the named scope, **blocked** identifies a concrete prerequisite, and **not started** means no product implementation has begun for that item.

## Shared screen types

| Surface | Route/identifier | Roles | Implementation | Status | Theme / viewport / function evidence | Remaining work |
|---|---|---|---|---|---|---|
| Login and password flows | `/login`, forgot password, email link, signup state | Guest | Global Pridict assets/settings and supported footer setting | Implemented; partially tested | Local `/login` HTTP 200; Pridict support footer rendered; no `Powered by ERPNext`; password-reset template captured | Capture remaining states in both themes/mobile; verify recovery path |
| Desk shell | `/app/*` navbar, search, sidebar, breadcrumbs, notifications | Desk roles | Existing scoped SCSS/JS | Implemented and visually tested | Repeated across 21 routable workspaces and 39 representative page routes in light/dark desktop and 390x844 mobile | Functional keyboard/search behavior remains standard Frappe behavior and outside the visual redesign scope |
| Executive home | `/app/pridict-home` | Executive/manager roles | Dedicated Frappe Page and permission-aware server API | Implemented; representative slice tested | Light/dark desktop, dark 390px, restricted-company tests and direct Profit and Loss reconciliation | Exercise populated non-zero periods and additional ordinary roles |
| Workspace/module home | `/app/<workspace>` | Workspace-authorized Desk roles | Existing generic workspace CSS | Implemented and visually tested | All 21 routable enabled workspaces captured in light/dark desktop and 390x844 mobile; Welcome Workspace recorded as a fallback-only route exception | No visual redesign work pending |
| Lists/tables | `/app/<doctype>` | DocType-authorized roles | Existing generic and selected transaction CSS | Implemented and visually tested | Representative Sales, Buying, Stock, Assets, Manufacturing, Projects, Quality, Support, Users and Website lists captured in both themes and viewports | Business actions remain unchanged and are outside the redesign scope |
| Forms/tabs/child tables | `/app/<doctype>/<name>` and new forms | DocType-authorized roles | Existing generic, master-data, and transaction CSS | Implemented and visually tested | Representative saved, submitted and new forms with tabs and child tables captured in both themes and viewports | Business submission workflows remain unchanged and are outside the redesign scope |
| Reports and charts | Query/Script/Report Builder/Dashboard routes | Report-authorized roles | Existing report/dashboard CSS | Implemented and visually tested | General Ledger, Stock Ledger, Accounts Receivable, Accounts Payable, Profit and Loss and workspace charts captured | Financial reconciliation is functional QA, not redesign acceptance |
| Dialogs/dropdowns/notifications | Shared framework overlays | Applicable authenticated roles | Existing generic CSS | Implemented and visually tested representatively | Kanban creation modal, common menus, filters and form controls captured in both themes and mobile | Destructive confirmations were not submitted |
| Search and command surfaces | navbar search, link search, autocomplete | Desk roles | Existing generic CSS | Implemented; not tested in Stage 1 | None | Verify keyboard, labels, result visibility and permissions |
| Kanban/specialized views | Kanban, calendar, tree, dashboard, report-specific views | Applicable roles | Existing generic CSS | Implemented and visually tested | ToDo Kanban dialog, Event Calendar, Chart of Accounts tree, dashboards and report layouts captured in both themes and viewports | No visual redesign work pending |
| Print preview | Desk print route/dialog | Print-authorized roles | Existing preview styling | Implemented; representative prior smoke | Prior handoff records preview/server-rendered output checks | Separate application chrome from tenant letterhead/content; test PDF output |
| Customer/supplier portal | 14 enabled portal menu routes and 6 published Web Forms | Customer, Supplier, Guest | Shared Pridict public shell and existing permission-aware portal controllers | Implemented; representative empty states tested | Disposable Customer/Supplier route sweeps; Customer `/invoices` light/dark 390px; safe `/project` 403 | Exercise populated transactions and capture a Supplier-role visual state |
| System emails/notifications | Invitation, reset, verification, assignment, share, workflow | Recipients vary | ERPNext footer disabled; tenant-aware Pridict welcome hook | Implemented; representative templates tested | Six focused branding tests capture invitation, reset, notification and welcome output without delivery | Expand to remaining assignment/share/workflow variants and validate links |
| About/help/support | Navbar help, About/version, support links, docs links | Guest/Desk/operator depending surface | Upstream promotions hidden; approved support mail link added; required notices retained | Implemented; representative checks tested | Exactly one visible custom support item; five upstream items hidden; About and Keyboard Shortcuts visible; login footer verified | Inspect remaining About/version variants and keyboard behavior |

## Visible UAT workspace coverage

All rows below are database-backed public workspaces. On 21 September 2026, every routable workspace was captured in light/dark desktop and 390x844 mobile layouts. The `Welcome Workspace` database record is a fallback-only entry without a direct route and is documented as an accepted exception.

| Module | Workspace/route identifier | Applicable roles | Implementation | Status | Required verification |
|---|---|---|---|---|---|
| Accounts | Accounting | Accounts User/Manager, Auditor, permitted roles | Shared workspace layer | Visually tested | Light/dark desktop/mobile workspace plus accounting reports and tree views |
| Accounts | Financial Reports | Accounts/report roles | Shared workspace/report layer | Visually tested | Light/dark desktop/mobile workspace plus representative financial reports |
| Accounts | Payables | Accounts/Purchase roles | Shared workspace layer | Visually tested | Light/dark desktop/mobile workspace and Accounts Payable report |
| Accounts | Receivables | Accounts/Sales roles | Shared workspace layer | Visually tested | Light/dark desktop/mobile workspace and Accounts Receivable report |
| Assets | Assets | Accounts/asset-authorized roles | Shared workspace/form/list layer | Visually tested | Light/dark desktop/mobile workspace, list and new form |
| Automation | Tools | System/automation-authorized roles | Shared workspace layer | Visually tested | Light/dark desktop/mobile workspace; operator-only behavior preserved |
| Buying | Buying | Purchase roles | Shared workspace plus transaction styling | Visually tested | Restricted-role workspace and populated Purchase Order list/form plus supplier and invoice views |
| Core | Build | System/Workspace/Developer roles | Shared workspace layer | Visually tested | Light/dark desktop/mobile workspace; identifiers and recovery controls preserved |
| Core | Users | System Manager | Shared workspace/form/list layer | Visually tested | Light/dark desktop/mobile workspace, list and Administrator form |
| Core | Welcome Workspace | Desk roles | Shared workspace/onboarding layer | Accepted route exception | Database entry exists but direct route intentionally resolves to the standard fallback; Home and Pridict Executive Home remain available |
| CRM | CRM | Sales roles | Shared workspace/form/list layer | Visually tested | Light/dark desktop/mobile workspace plus customer and project-related views |
| ERPNext Integrations | ERPNext Integrations | System/integration roles | Shared workspace layer plus translated display name | Visually tested | Light/dark desktop/mobile workspace displays `Pridict Integrations`; provider identities preserved |
| Integrations | Integrations | System/integration roles | Shared workspace layer | Visually tested | Light/dark desktop/mobile workspace; provider identities and secret fields preserved |
| Manufacturing | Manufacturing | Manufacturing roles | Shared workspace/form/list layer | Visually tested | Light/dark desktop/mobile workspace plus BOM and Work Order lists/forms |
| Projects | Projects | Projects roles | Shared workspace/form/list layer | Visually tested | Light/dark desktop/mobile workspace plus Project/Task lists/forms and Kanban |
| Quality Management | Quality | Quality Manager and related roles | Shared workspace/form/list layer | Visually tested | Light/dark desktop/mobile workspace plus Quality Inspection list/form |
| Selling | Selling | Sales roles | Shared workspace plus transaction styling | Visually tested | Light/dark desktop/mobile workspace plus Sales Invoice and Delivery Note lists/forms |
| Setup | ERPNext Settings | System Manager | Shared workspace plus translated display name | Visually tested | Light/dark desktop/mobile workspace displays `Pridict Settings`; route identity preserved |
| Setup | Home | Desk roles | Shared workspace/onboarding layer | Visually tested | Light/dark desktop/mobile standard Home retained alongside Pridict Executive Home |
| Stock | Stock | Stock roles | Shared workspace plus transaction styling | Visually tested | Light/dark desktop/mobile workspace plus Item, Stock Entry and Stock Ledger views |
| Support | Support | Support Team and permitted roles | Shared workspace/form/list layer | Visually tested | Light/dark desktop/mobile workspace plus Issue list/form; internal support remains distinct |
| Website | Website | Website Manager/System Manager | Shared workspace/web layer | Visually tested | Light/dark desktop/mobile workspace plus Web Page list/form and existing portal evidence |

## Role verification groups

| Group | Representative roles | Stage 1 status | Required acceptance |
|---|---|---|---|
| Privileged operator | Administrator, System Manager | Identified; not retested | Recovery path, configuration access, no hidden broken controls |
| Finance | Accounts User, Accounts Manager, Auditor | Identified; not tested | Company restrictions, reports, approvals, financial reconciliation |
| Sales/customer operations | Sales User, Sales Manager, Sales Master Manager | Identified; not tested | CRM/selling routes, direct API permissions, lists/forms/reports |
| Procurement | Purchase User, Purchase Manager, Purchase Master Manager | Identified; not tested | Buying/supplier routes, approvals, direct API permissions |
| Inventory/delivery | Stock User, Stock Manager, Delivery User/Manager, Fulfillment User | Identified; not tested | Stock/fulfillment specialized views and ledger integrity |
| Manufacturing/projects/quality | Manufacturing, Projects, Quality roles | Identified; not tested | Module-specific layouts, reports, workflows, permissions |
| Portal | Customer, Supplier, Guest | Customer/Supplier fixtures exercised; Guest login exercised | Public/portal navigation, direct access, themes/mobile, branding |
| Website/support | Website Manager, Support Team | Identified; not tested | Website surfaces, support module distinction, communications |

## Evidence and limitations

- Visual references: `design/reference-dashboard.png`, `design/pridict-executive-home-preview.html`, and `design/pridict-executive-home.html`.
- Existing implementation: `pridict_app/pridict/public/scss/pridict.bundle.scss`, `pridict_app/pridict/public/js/pridict.bundle.js`, and `pridict_app/pridict/setup/install.py`.
- Prior test evidence and release details: `deployment/PRIDICT-HANDOFF.md`.
- Stage 1 UAT inspection was read-only and covered installed apps, visible workspaces, role definitions, selected branding settings, login HTML, and authentication configuration presence. It did not impersonate roles, inspect every route, or execute business transactions.
- Docker Desktop and Docker CLI `29.7.2` are installed and the isolated `development.localhost` bench is running. Local builds, migrations, API tests, and browser checks now execute in that environment.
- Repeated local migration and focused branding validation completed on 17 September 2026. The current clean candidate is `pridict-erpnext:0.1.0-20260917-review1` (`sha256:cb0381d58b8efcbae06f7ec7990bcb928e8773a3e44f68f926c083942029330b`); no prior or mutable tag was overwritten.

## Post-checkpoint evidence

| Surface | Route or identifier | Roles exercised | Implementation | Verification | Status |
|---|---|---|---|---|---|
| Executive home | `/app/pridict-home` | Administrator; restricted ordinary system user at API layer | Dedicated Frappe Page and permission-aware API | Light/dark desktop, dark 390px, no overflow, 5 API tests including direct P&L reconciliation | Tested representative slice |
| Workspace | `/app/accounting`, `/app/website` | Administrator | Shared shell/sidebar/cards | Dark desktop smoke and screenshots | Tested representative layouts |
| List | `/app/sales-invoice` | Administrator | Shared list/table/filter controls | Dark desktop smoke and screenshot | Tested representative layout |
| Form and child-table shell | New Sales Invoice | Administrator | Shared form/tabs/grid controls | Dark desktop smoke and screenshot | Tested representative layout; business transaction not submitted |
| Query report | `/app/query-report/Profit%20and%20Loss%20Statement`, `/app/query-report/General%20Ledger` | Administrator | Shared report/filter/table controls | Dark desktop smoke, P&L screenshot, no overflow | Tested representative layouts; financial reconciliation pending |
| Tree | `/app/account/view/tree` | Administrator | Purpose-specific tree preserved under shared shell | Desktop screenshot and no overflow | Tested representative layout |
| Calendar | `/app/event/view/calendar/default` | Administrator | Purpose-specific calendar with navy filter sidebar | Desktop screenshot; contrast defect fixed; no overflow | Tested representative layout |
| Kanban dialog | `/app/todo/view/kanban` | Administrator | Shared modal/form controls | New-board dialog screenshot and focus state | Tested dialog shell; board creation not submitted |
| Public portal shell | `/me`, `/invoices`, `/orders`, `/purchase-orders`, `/issues`, `/address` | Administrator session | Pridict wordmark, navy navbar/sidebar, shared list/empty-state styles | Desktop route smoke; Issues desktop and 390px screenshots; no overflow | Tested representative empty states; Customer/Supplier roles pending |
| Help menu | Navbar Help | Administrator | Standard upstream items hidden; About and Keyboard Shortcuts retained; custom Pridict support item added | Authenticated Desk HTML plus database record inspection; support mail destination verified | Tested |
| Customer portal | `/me`, `/quotations`, `/orders`, `/invoices`, `/shipments`, `/issues`, `/addresses`, `/timesheets`, `/material-requests` | Disposable Customer user linked to fixture customer | Shared public shell and permission-aware ERPNext portal pages | HTTP status/redirect/branding sweep; `/invoices` light/dark 390px screenshots; no overflow | Tested empty states; populated records pending |
| Supplier portal | `/me`, `/rfq`, `/supplier-quotations`, `/purchase-orders`, `/purchase-invoices` | Disposable Supplier user linked to fixture supplier | Shared public shell and permission-aware ERPNext portal pages | HTTP status/redirect/branding sweep; no upstream promotional strings | Tested empty states; visual role screenshot pending |
| Print preview | Customer Standard print | Administrator | Existing print format preserved inside styled preview | HTML preview screenshot, no upstream branding, no overflow | Tested non-transactional document |
| PDF generation | Customer Standard print | Administrator | Existing PDF renderer; no template replacement | Valid one-page `%PDF`; text extracted with `pypdf`; no upstream branding | Structurally and textually tested; visual output represented by the matching HTML print preview because Poppler is unavailable |
| Enabled workspaces | 22 database-enabled workspaces | Administrator | Shared workspace/shell styles; translated Pridict Settings/Integrations labels | Direct-route sweep | 21 loaded normally; Welcome Workspace accepted as fallback-only route exception |
| Review milestone | `/app/pridict-home`, `/app/buying`, Purchase Order list/form, Profit and Loss Statement | Administrator and disposable restricted Purchase User | Executive structural implementation plus shared workspace/list/form/report styling; responsive outer-sidebar and transaction-list mobile corrections | Existing Administrator milestone plus six restricted desktop and six restricted 390x844 light/dark screenshots; populated Purchase Order list/form; no document-level horizontal overflow or targeted upstream branding | Tested visual/rebranding milestone scope; functional workflow expansion remains outside this acceptance |

## Exact next step

Build and validate the final versioned image from the committed all-module visual/rebranding revision, then request explicit authorization before running the separate UAT release procedure.

## Completion checkpoint — 21 September 2026

- Completed the disposable restricted `Purchase User` Buying matrix for workspace, populated Purchase Order list and populated form in light/dark desktop and 390x844 mobile layouts.
- Captured six desktop and six mobile screenshots under `design/review-20260921/`; all manifest rows report no document-level horizontal overflow and no targeted upstream branding.
- Corrected the mobile transaction-list supplier/status overlap for Purchase Order, Purchase Invoice, Delivery Note and Stock Entry.
- Reconciled targeted ERPNext/Frappe contextual-help links without changing explanatory text or customer-modified metadata; seven rendered contextual-help screens report zero targeted links or tour descriptions.
- Confirmed the legacy Manufacturing `Onboarding` source is not installed in this runtime, so no runtime record requires modification.
- Removed the disposable user, its User Permission and all dedicated temporary Chrome review profiles.
- Focused tests pass: seven branding/install tests and five executive-home tests. Node syntax, `git diff --check` and screenshot-manifest validation also pass.
- Local-only candidate image: `pridict-erpnext:0.1.0-20260921-review2`, image ID `sha256:28ef3fb414c38abc80bda456b121d8faa0319f635465265ee7fd4c022e169fec`.
- No Azure/UAT deployment, live configuration change or customer-data change was performed.

## Full redesign verification — 21 September 2026

- Added automated capture coverage for all 21 routable enabled workspaces and 39 representative pages spanning lists, forms, child tables, reports, trees, calendars and Kanban.
- Captured 240 additional screenshots across light/dark desktop and 390x844 mobile. Combined with the restricted Buying and contextual-help evidence, the 21 September evidence set contains 259 screenshots.
- Every captured row reports zero document-level horizontal overflow and zero targeted upstream branding. All representative routes loaded without permission, server or not-found states.
- Visual inspection confirmed consistent Pridict shell, spacing, typography, controls, cards, tables, empty states and responsive behavior. The apparent first Assets light capture was a theme-transition race; the capture delay was strengthened and the rerun rendered correctly.
- No additional product CSS change was required by the full-module sweep. Business workflows and transactions remain intentionally unchanged.
