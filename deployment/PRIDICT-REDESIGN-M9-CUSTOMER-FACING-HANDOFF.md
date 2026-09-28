# Pridict Redesign Milestone 9: Customer-Facing Source Handoff

Date: September 28, 2026

Status: Implemented in source only. Not visually reviewed, functionally verified, built, migrated, deployed, or accepted.

## Source scope

- Added a route-aware customer-facing JavaScript layer for login and account flows, ERPNext customer and supplier portal routes, Web Forms, public error states, and Pridict information pages.
- Added a shared customer-facing visual layer for website navigation, content width, portal context, portal sidebars, transaction lists, document cards, order details, form controls, authentication cards, public information pages, footers, and responsive layouts.
- Added an idempotent portal context panel without replacing native portal navigation, document rendering, permissions, or actions.
- Added `/pridict-notices` as an accessible product and open-source notices surface.
- Added `/pridict-release-notes` as an installed-version and release-evidence boundary surface.
- Added Notices and Release notes links to the managed Pridict website footer while preserving the approved support destination.
- Added backward-compatible reconciliation so installations using the previous managed Pridict footer receive the new links without overwriting unrelated customer-authored footer content.
- Added focused context and footer tests.

## Supported architecture

- Uses `web_include_js`, the existing web CSS bundle, Website Settings reconciliation, and standard app `www` routes.
- Does not override Frappe or ERPNext base templates.
- Does not rename framework packages, routes, DocTypes, providers, licences, or technical identifiers.
- Does not publish or link the guides under `documentation/pridict`; help-center publication remains a separate content decision.

## Functional boundary

- Native portal permissions, party filtering, website-list queries, transaction detail rendering, Web Form submission, authentication, password reset, signup, document actions, and attachments remain unchanged.
- Customer company names, legal identities, tax data, letterheads, print formats, attachments, and authored content remain unchanged.
- Existing email branding safeguards remain in place. This milestone does not replace native transactional email templates or misrepresent delivery providers.
- Public notices identify Frappe Framework and ERPNext truthfully as underlying open-source software.

## Visible result

- Public and authenticated website surfaces receive the Pridict background, navigation treatment, typography, controls, spacing, cards, and responsive behavior.
- Customer and supplier portal journeys receive a consistent Pridict context panel while retaining native navigation and available actions.
- Portal transaction rows and document detail surfaces present as structured enterprise cards rather than isolated default rows.
- Login and account cards use the shared Pridict visual system.
- Customers can reach dedicated product notices and release-notice pages from the website footer.

## Validation

- JavaScript syntax validation passed for the customer-facing adapter.
- Read-only Python AST parsing passed for hooks, website contexts, setup reconciliation, route controllers, and focused tests.
- Targeted Jinja block and expression-balance checks passed for both information pages and the footer include.
- Hook, asset, route-file, and SCSS-import presence checks passed.
- `git diff --check` passed.
- Full Jinja rendering was not run because the host Python environment does not include Jinja/Frappe.
- Focused Frappe tests were added but not run because a local Frappe test runtime is not available in this workspace.
- No asset build, migration, browser review, screenshots, email delivery, broad test suite, image build, or deployment was run.

## Next target

Continue with the remaining enabled administrative and people-facing modules and genuine exceptions, beginning with Human Resources and Payroll if those applications are enabled in the target runtime. Then cover Setup, Integrations, Users and Permissions, printing, import/export, notifications, communication dialogs, and system utilities through reusable shared adapters rather than isolated CSS patches.

Do not treat this handoff as runtime acceptance or deployment readiness.
