# Pridict branding QA

Checkpoint date: 21 September 2026.

This file consolidates recorded customer-facing branding evidence. A result is marked current only when it was checked during the named session. Historical evidence remains useful but is not presented as a new test run.

## Candidate under review

- Recorded image: `pridict-erpnext:0.1.0-20260921-review2`.
- Recorded image ID: `sha256:28ef3fb414c38abc80bda456b121d8faa0319f635465265ee7fd4c022e169fec`.
- Recorded source revision label: `c8cd4b6e12a7c45ab19a072ba310cca7575ac9de`.
- Environment: isolated local Frappe/ERPNext development site; no UAT deployment.

## Recorded passing evidence — 17 September 2026

| Area | Roles/environment | Evidence | Result |
|---|---|---|---|
| Focused automated tests | Isolated local site | 5 executive-home tests and 6 branding/install tests | Passed; 11 total |
| Administrator visual milestone | Desktop 1440px and mobile 390x844; light and dark | 20 screenshots and two capture manifests in `design/review-20260917/` | Passed recorded scope; no document-level horizontal overflow |
| Buying workflow fixture | Administrator plus disposable restricted Purchase User API check | Buying workspace, populated Purchase Order list/form and direct read of `PUR-ORD-2026-00001` | Administrator visuals passed; restricted-user API access passed |
| Shared specialized views | Administrator | Tree, calendar, Kanban dialog and financial reports | Representative layout checks passed; calendar contrast defect fixed |
| Portal routes | Disposable Customer and Supplier users | Enabled route sweeps; Customer invoices mobile/light/dark evidence | Empty-state and permission checks passed; populated portal records remain pending |
| Email branding | Captured locally; no real recipients | Welcome, password-reset, invitation and notification templates | Recorded without upstream promotional branding |
| Print/PDF | Isolated local Customer fixture | HTML print preview and valid one-page PDF text extraction | No upstream application branding; tenant content preserved |
| Persistence/build | Isolated local containers | Repeated migration, restart, clean versioned image and packaged asset checks | Passed for the recorded candidate |

## Current checks — 21 September 2026

| Check | Result |
|---|---|
| Saved review assets | Historical 20-screen Administrator set retained; 12 current restricted Buying screenshots and 7 contextual-help screenshots added under `design/review-20260921/` |
| Capture tooling | Existing PowerShell tool retained; focused Node CDP capture added for reliable headless desktop/mobile evidence |
| Workspace learning links | All six Frappe School URLs match the existing idempotent removal list |
| Module workspace inventory | Buying, finance, sales/CRM, stock/assets, manufacturing, projects/quality, support and website queues recorded in `deployment/PRIDICT-UI-COVERAGE.md` |
| Restricted Buying UI | Purchase User workspace, populated Purchase Order list and form captured at 1440px and 390px in light/dark; no page overflow or visible upstream branding |
| Mobile transaction list | Supplier/status overlap found and corrected for Purchase Order, Purchase Invoice, Delivery Note and Stock Entry lists |
| Additional upstream documentation links | Exact-source DocField and Form Tour reconciliation applied twice; targeted database counts are zero and seven rendered Administrator surfaces expose zero matching links/tour descriptions |
| Legacy Manufacturing onboarding | Source record exists, but the legacy `Onboarding` DocType/table is not installed; no runtime change required |
| Focused automated tests | 7 branding/install tests and 5 executive-home tests passed; 12 total |
| Candidate image | `pridict-erpnext:0.1.0-20260921-review2` built with compiled Pridict CSS/JavaScript and app version `0.1.0` |
| Local runtime | Docker Desktop and isolated `development.localhost` Bench restored and verified; no UAT access or change |

## Deferred QA outside the current visual/rebranding acceptance

- Populated Customer and Supplier portal transaction views.
- Non-zero accounting periods/currencies reconciled between executive KPIs and standard reports.
- Complete keyboard traversal, validation/error states, session expiry and remaining login/password states.
- Broader transaction print/PDF samples and visual PDF rasterization when a renderer is available.

These are useful production-readiness checks but are not required to claim completion of the current visual redesign and customer-facing rebrand. No functional or workflow redesign is included.

## Current status and next action

No local visual/rebranding blocker remains in the agreed scope. Review the `20260921-review2` screenshots and candidate details. If approved, prepare a fresh UAT backup and a versioned release candidate; do not deploy without explicit authorization.

No Azure resource, UAT configuration, live authentication provider, customer data or production setting was changed during the 21 September 2026 continuation.

## Pause point — 21 September 2026

The focused visual redesign and customer-facing rebrand are locally reviewable. The next decision is whether to promote `20260921-review2` into a formal release candidate and begin the guarded UAT release process. Do not deploy or modify UAT without explicit authorization.
