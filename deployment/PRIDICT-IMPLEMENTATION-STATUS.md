# Pridict implementation status

Checkpoint date: 21 September 2026.

This is the durable implementation record for the customer-facing Pridict rebrand and product-wide UI redesign. The agreed visual/rebranding implementation and local all-module review are complete. No workflow redesign was performed, and no new UAT configuration, Azure resource, DNS, live permission, authentication-provider configuration, or live data was changed during this redesign cycle.

## Stage 1 checklist

- [x] Read the authoritative handoffs and editable executive-home design.
- [x] Visually inspect `design/reference-dashboard.png` and the rendered executive-home preview.
- [x] Record the Git branch and preserve all existing uncommitted work.
- [x] Inspect the existing `pridict_app` implementation and deployment tooling.
- [x] Check local toolchain and development-environment availability.
- [x] Verify the current UAT app versions and visible workspaces read-only.
- [x] Inventory initial UI coverage and remaining branding sources.
- [x] Define the implementation sequence, dependencies, exceptions, and acceptance criteria.
- [x] Begin product implementation after the user said `Proceed`.

## Baseline

### Source state

- Branch: `version-15`, tracking `origin/version-15` at `c8cd4b6e12`.
- Existing tracked modifications: `.github/workflows/deploy-azure.yml`, `.gitignore`, `docker-compose.dev.yml`, and `init-bench.sh`.
- Existing untracked work includes `.github/workflows/pridict-image-check.yml`, `deployment/`, `design/`, and the complete `pridict_app/` tree.
- The repository ownership warning is handled with a per-command Git `safe.directory` override. Global Git configuration was not changed.
- No reset, clean, stash, branch creation, commit, or overwrite was performed.

### Versions and runtime

- Read-only UAT verification on 17 September 2026: Frappe `15.120.1`, ERPNext `15.121.2`, Pridict `0.1.0`.
- Current recorded image: `pridict-erpnext:0.1.0-20260916-rc3`.
- UAT VM `erpnext-demo-vm` was running and provisioned successfully during inspection.
- Local Python: `3.13.5`; Node.js: `22.17.0`.
- Docker Desktop is installed at `C:\Users\tjm06\AppData\Local\Programs\DockerDesktop` with Docker CLI `29.7.2`. The sandboxed shell did not expose that user-level CLI path; an elevated check found it successfully.
- Docker Desktop and the isolated `development.localhost` bench are running. Docker CLI access requires the explicit user-level executable path and sandbox approval.
- Asset builds run successfully inside the development container; host `npm` remains unnecessary for this workflow.

### Installed and enabled UAT surfaces

- Installed applications: `frappe`, `erpnext`, and `pridict`.
- Visible public workspaces: Accounting, Financial Reports, Payables, Receivables, Assets, Tools, Buying, Build, Users, Welcome Workspace, CRM, ERPNext Integrations, Integrations, Manufacturing, Projects, Quality, Selling, ERPNext Settings, Home, Stock, Support, and Website.
- Enabled role definitions include customer-facing portal roles (`Customer`, `Supplier`), ordinary Desk roles across Accounts, Buying, Selling, Stock, Projects, Manufacturing, Quality, Support and Website, and privileged roles including `System Manager` and `Administrator`.
- Social Login Key records: none returned by the read-only query.
- Generic `OAuth Provider` DocType: not installed in this version/site.
- LDAP enabled value: empty/false in the inspected settings.
- UAT branding settings currently resolve to Pridict for System Settings app name, Website Settings app name/logo/favicon, and Navbar Settings logo.
- UAT language is `en-GB`.

## Existing implementation to reuse

- `pridict_app/pridict/hooks.py` registers the Pridict title, logo, favicon, splash image, Desk/web assets, and idempotent install/migrate branding hook.
- `pridict_app/pridict/setup/install.py` sets supported branding fields and preserves workspace identifiers after an earlier route-title regression.
- `pridict_app/pridict/public/scss/pridict.bundle.scss` is a substantial shared light/dark visual layer covering the shell, navigation, workspaces, forms, lists, tables, reports, dialogs, dropdowns, dashboards, Kanban, login, print preview, focus, reduced motion, and responsive containment.
- `pridict_app/pridict/public/js/pridict.bundle.js` scopes the UI, maintains the Pridict navbar logo, and provides a persistent theme toggle through Frappe's supported user-theme API.
- Existing wordmark/icon assets and compiled bundles are present and were included in the current versioned UAT image.
- Existing release, image validation, backup, and rollback scripts must be extended rather than replaced.

## Release boundaries and future QA

- The product-wide visual redesign is complete through shared components and was verified across every routable enabled workspace plus representative list, form, report, tree, calendar, Kanban, settings and portal surfaces.
- Module and role homepages beyond the executive home intentionally retain their existing workspace composition under the new shared visual system; no unnecessary replacement dashboards were invented.
- Exhaustive record-by-record, role-by-role business workflow testing is a separate functional QA activity and is not required for the approved visual/rebranding scope.
- The approved customer-support destination is `pavan@riditstack.com`; it is implemented as a visible `Contact Pridict Support` Help item and a public-footer mail link.
- No Pridict learning library exists, so optional upstream learning actions are removed rather than replaced with invented destinations.
- Print HTML and generated PDF text are verified. The application print preview is visually covered; tenant-specific document layout remains customer content rather than application-shell redesign scope.
- The reported authentication-provider reference was not reproduced. Current evidence shows no Social Login Key records, no generic OAuth Provider DocType, and LDAP disabled; the exact screen remains to be identified without changing authentication.
- Required open-source notices, provider identities, package names, DocTypes, routes, and customer-authored business content remain intentionally unchanged.

## Completed implementation sequence

1. **Foundation:** convert the approved design into reusable Pridict tokens and components while retaining the existing scoped theme and supported hooks.
2. **Executive vertical slice:** implement a real Frappe executive-home page with permission-aware server APIs, company/period controls, honest states, existing-route navigation, and no sample figures.
3. **Shared application shell:** reconcile navbar, sidebar, page header, search, notifications, theme behavior, responsive navigation, and recovery access without duplicate chrome.
4. **Core screen primitives:** finalize lists, forms, tabs, child tables, filters, sorting, pagination, bulk actions, dialogs, dropdowns, validation, loading, empty, and error states.
5. **Enabled module coverage:** apply and verify the shared components across the 22 visible workspaces and deliberate specialized views/reports recorded in `deployment/PRIDICT-UI-COVERAGE.md`.
6. **Customer branding:** implement the actions in `deployment/PRIDICT-BRANDING-INVENTORY.md`, using supported settings/hooks and idempotent patches while preserving provider identities and user-owned content.
7. **Portals, communications, and print:** verify enabled customer/supplier/website surfaces, capture system emails locally, and separately review print/PDF application branding versus tenant letterheads/legal content.
8. **Verification and candidate:** run role/permission, financial reconciliation, accessibility, light/dark, desktop/mobile, migration-repeat, restart, clean-image, and representative workflow checks; then prepare a versioned candidate, diff, evidence, backup, and rollback package.

## Implementation progress

- Implemented the standard Frappe Page at `/app/pridict-home` with the approved executive hierarchy, light/dark support, 390px responsive behavior, real company/date controls, permission-aware metrics, workflow-backed approvals, recent activity, and business-area navigation.
- Added direct API protection for Guest access, company allowlisting, and a one-year reporting limit. Restricted-user tests prove only the permitted company is returned and unauthorized company requests stop before any financial, pipeline, receivable, task, or activity loader runs.
- Reconciled supported branding settings, the website footer, exact upstream Help entries, the approved `Contact Pridict Support` mail link, Frappe School shortcuts, and unmodified standard onboarding records through the idempotent install/migrate hook.
- Added a supported welcome-email hook that preserves the tenant company name and falls back to `Pridict`; captured sendmail arguments prove the welcome subject contains no ERPNext or Frappe branding and no message is sent.
- Added a Pridict public-site wordmark hook and scoped portal shell, sidebar, list, empty-state, footer, dark-theme, and mobile styling.
- Corrected a calendar-filter contrast regression found during visual QA by scoping the inner filter panel to the navy sidebar palette.
- Rebuilt assets, cleared cache, and ran repeated local migrations successfully after the implementation changes.

## Current evidence

- Automated tests: `pridict.pridict.page.pridict_home.test_pridict_home` passes 5 tests, including restricted-company denial and direct Profit and Loss reconciliation; `pridict.setup.test_install` passes 7 tests, including rendered password-reset, invitation and notification templates plus idempotent support/footer and contextual-help branding.
- Authenticated Desk HTML and database records contain exactly one visible custom `Contact Pridict Support` item targeting `mailto:pavan@riditstack.com`. The five upstream links remain hidden standard records; About and Keyboard Shortcuts remain visible.
- Rendered `/login` returned HTTP 200 with the Pridict support mail link and `Contact support`, and contained no `Powered by ERPNext` footer text.
- Portal database inventory contains 14 enabled menu routes and 6 published Web Forms. Disposable Customer and Supplier users verified the enabled transactional routes with real portal permissions; all tested pages contained Pridict branding and no upstream promotional branding. `/project` returned a permission-safe 403 for the empty Customer fixture rather than exposing data.
- All 22 database-enabled workspace records were inventoried. Twenty-one routable workspaces were captured in light/dark desktop and 390x844 mobile without errors, horizontal overflow or targeted upstream branding; `Welcome Workspace` is a fallback-only record without a direct route.
- Thirty-nine representative page routes were captured in light/dark desktop and 390x844 mobile, covering lists, saved/new/submitted forms, child tables, reports, Chart of Accounts tree, Event calendar, Kanban dialog, settings and Website surfaces.
- The 21 September evidence set contains 259 screenshots across restricted Buying, contextual help, all-module workspaces and representative page types. Visual inspection found no additional product CSS defect after the existing mobile transaction-list correction.
- Print preview for a disposable Customer master rendered without upstream branding or overflow. A valid one-page `%PDF` was generated through the real download endpoint after adding a temporary container-only hostname mapping; text extraction confirms no upstream branding and the document preserves business fields without injecting Pridict into customer-authored content.
- A new clean versioned image, `pridict-erpnext:0.1.0-20260917-review1`, built successfully after the responsive sidebar correction from `deployment/Dockerfile.pridict` and passed the packaged app/CSS/JS validation command. Prior candidates were not overwritten and the mutable `latest` tag was not used.
- Final isolated restart validation succeeded: the Frappe container restarted, `bench start` recovered, migration completed, both focused test modules passed, installed app versions remained Frappe `15.120.1`, ERPNext `15.121.2`, and Pridict `0.1.0`, and `/login` returned HTTP 200.
- Current candidate image evidence: ID `sha256:cb0381d58b8efcbae06f7ec7990bcb928e8773a3e44f68f926c083942029330b`, created `2026-09-17T18:14:45Z`, revision label `c8cd4b6e12a7c45ab19a072ba310cca7575ac9de`.
- Visual evidence includes `design/qa-portal-issues-rebranded.png`, `design/qa-portal-issues-mobile.png`, `design/qa-tree-account.png`, `design/qa-calendar-event-fixed.png`, and `design/qa-kanban-dialog.png` in addition to the executive, workspace, list, form, and report captures already recorded.
- Review milestone evidence in `deployment/PRIDICT-UI-REVIEW-MILESTONE.md` adds ten current 1440px captures of the executive home, Buying workspace, populated Purchase Order list, Purchase Order item grid and Profit and Loss Statement in both themes. All ten report no horizontal overflow.
- Continued verification adds ten matching 390x844 light/dark captures. It found and fixed the narrow-screen outer sidebar column that covered workspace/list/form content while the supported overlay sidebar was closed.
- Local fixture `PUR-ORD-2026-00001` contains three item rows and is submitted as `To Receive and Bill` solely in the isolated site. A disposable `Purchase User` restricted to `_Test Company` successfully listed and directly read the order, then was removed.
- Current testing is representative, not exhaustive. Populated portal transaction lists, visual PDF rasterization, full keyboard traversal, multi-role module workflows, and financial reconciliation against populated accounting data remain outstanding.

## Dependencies and blockers

- Real Pridict guide URLs/content are required before replacing learning links; until then optional course actions should be removed cleanly.
- Populated accounting fixtures are required to extend the completed direct Profit and Loss reconciliation into representative non-zero business periods and currencies.
- Representative ordinary customer roles/test users are required for final permission and navigation acceptance.
- The exact reported authentication screen/reference is still needed if it cannot be reproduced from configured UAT login methods.

## Proposed exceptions

- Preserve internal package names, DocTypes, database tables, routes, asset paths, API identifiers, and source metadata where changing them would be unsafe or misleading.
- Preserve truthful third-party provider names and callback/protocol identifiers when the provider is actually used.
- Preserve required licence, copyright, attribution, and open-source notices; provide a customer-appropriate notices surface rather than deleting provenance.
- Preserve customer-authored templates, links, records, letterheads, business names, document contents, and existing customizations.
- Specialized views may retain purpose-specific layouts when forcing the dashboard structure would reduce usability; each exception must be recorded and tested.

## Acceptance criteria

- Every inventory item has an implemented, tested, blocked, or explicitly accepted-exception status with evidence.
- The executive home visually corresponds to the approved design in light/dark desktop and approximately 390px mobile layouts and contains only real permission-aware data.
- Shared shell and primitives have no duplicate chrome, clipping, unreadable controls, broken navigation, inaccessible labels, or keyboard traps.
- Administrator and representative ordinary roles are tested, including direct route/API access and company/User Permission restrictions.
- Financial values reconcile with the corresponding ERP reports for the same company, period, and currency.
- Changed links reach the recorded destination; optional learning actions without real content are absent rather than misleading.
- Captured system emails and notifications use correct branding without sending to real recipients.
- Repeated migration, cache clear, restart, and clean image build succeed without overwriting customer customizations or relying on ignored compiled assets.
- Representative accounting, buying, selling, stock, portal, and print flows pass in an isolated environment.
- No live deployment occurs until a versioned candidate, reviewable diff, QA evidence, backup procedure, and rollback instructions are approved.

## Exact next step

Review the local `pridict-erpnext:0.1.0-20260921-review2` candidate and its captured visual/rebranding evidence. If approved, proceed separately with the documented UAT release procedure; do not introduce workflow or functional changes as part of this acceptance.

## Session boundary — 17 September 2026

- Review milestone completed and documented in `deployment/PRIDICT-UI-REVIEW-MILESTONE.md`.
- Desktop and 390x844 evidence contains 20 actual application screenshots under `design/review-20260917/`.
- Local demonstration record remains available as `PUR-ORD-2026-00001`; it is test-only and must not be promoted to UAT.
- The responsive outer-sidebar defect found during mobile inspection was corrected in `pridict_app/pridict/public/scss/pridict.bundle.scss`.
- Focused tests pass: 5 executive-home tests and 6 branding/install tests.
- Current local candidate: `pridict-erpnext:0.1.0-20260917-review1`, image ID `sha256:cb0381d58b8efcbae06f7ec7990bcb928e8773a3e44f68f926c083942029330b`.
- No source commit was created and no Azure/UAT deployment or live configuration change was performed.

## Continuation — 20 September 2026

- Confirmed the saved review milestone, 20 desktop/mobile screenshots, capture script, candidate image record and 11 previously passing focused tests remain documented.
- The isolated local review site is currently offline. Port 8000 has no active listener, the Windows Docker CLI/service is unavailable, and the Docker Desktop WSL distribution cannot run the CLI directly. Restricted `Purchase User` visual capture was not falsely recorded as completed.
- Continued the independent source inventory while runtime testing is blocked. All six optional Frappe School workspace shortcuts are already covered by the exact, idempotent removal list.
- Identified nine ERPNext/Frappe documentation references in Accounts, Selling and Stock DocField help/Form Tours that sit outside the current standard-onboarding reconciliation. These require role-based rendered inspection before removal or replacement.
- Identified a legacy Manufacturing `Onboarding` record with an upstream documentation URL outside the current `module_onboarding` scan pattern. Its installed/reachable state remains unverified.
- No product code, Azure resource, UAT configuration, live authentication or customer data was changed during this continuation.

The next executable step is to restore the isolated local container environment and perform the restricted `Purchase User` visual matrix. The first follow-on implementation decision is the treatment of the newly inventoried settings/Form Tour links after their actual visibility is verified.

## Pause point — 20 September 2026

- All continuation findings and QA status are saved in the repository documentation.
- Resume by restoring the isolated local Docker/Bench environment; do not touch Azure or UAT.
- Then capture the disposable restricted `Purchase User` Buying workspace and populated Purchase Order list/form in light/dark desktop and 390px layouts.
- Record the screenshots and interaction results in `deployment/PRIDICT-BRANDING-QA.md`, remove the disposable user/permission, and continue the prioritized module queue in `deployment/PRIDICT-UI-COVERAGE.md`.

## Completion checkpoint — 21 September 2026

- Restored the isolated local Docker/Bench environment and completed the restricted `Purchase User` Buying visual matrix.
- Captured six desktop and six 390x844 mobile screenshots for the Buying workspace and populated Purchase Order list/form in both themes, with zero document-level horizontal overflow and zero targeted upstream branding.
- Fixed the mobile supplier/status overlap in shared transaction lists without changing document behavior or workflow.
- Implemented exact-source, idempotent contextual-help rebranding for targeted DocField and Form Tour content while preserving explanatory text and customer-modified metadata.
- Verified seven contextual-help screens with zero targeted upstream links and zero upstream tour descriptions. The legacy Manufacturing `Onboarding` source is not installed in this runtime.
- Removed the disposable review user, its User Permission and all dedicated temporary Chrome profiles.
- Focused tests pass: seven branding/install tests and five executive-home tests. Node syntax, `git diff --check` and all 19 current capture-manifest rows pass.
- Built and validated local-only image `pridict-erpnext:0.1.0-20260921-review2`, image ID `sha256:28ef3fb414c38abc80bda456b121d8faa0319f635465265ee7fd4c022e169fec`.
- No source commit, Azure/UAT deployment, live authentication change, live permission change or customer-data change was performed.
