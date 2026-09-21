# Pridict customer-facing rebrand implementation plan

Prepared: 17 September 2026. This document plans the work; it does not authorize a new live deployment by itself.

## 1. Outcome and scope

Deliver a consistent Pridict experience for customers: login, loading screens, workspaces, learning, help, notifications and support. Optional learning and promotional links must not unexpectedly send customers to Frappe or ERPNext websites. Preserve accounting, stock, purchasing, selling, permissions and existing business workflows.

Pridict is the product/service brand. Preserve applicable upstream licences, copyright notices and truthful third-party provider identification. Do not promise that the underlying framework is undetectable or claim exclusive authorship of upstream code. This project is customer-facing branding, not concealment of technical provenance.

Out of scope: framework upgrades, renaming Python packages/DocTypes/database tables, new accounting workflows, billing/subscriptions, tenant provisioning/isolation, full documentation authoring, and a production security certification. Those are separate SaaS-readiness projects.

## 2. Verified starting information — recheck before implementation

- Repository: `C:\Users\tjm06\Projects\ERPNext`.
- Custom app: `pridict_app/`; keep upstream ERPNext/Frappe modifications minimal.
- Read `deployment/PRIDICT-HANDOFF.md`, `deployment/README.md`, `deployment/ROLLBACK.md` and applicable `AGENTS.md` first.
- Last recorded UAT URL: https://pridict-demo.centralindia.cloudapp.azure.com.
- Last recorded image: `pridict-erpnext:0.1.0-20260916-rc3`.
- Last recorded versions: ERPNext 15.121.2, Frappe 15.120.1, Pridict 0.1.0.
- Azure VM: `erpnext-demo-vm`, resource group `rg-erpnext`; server directory `/opt/erpnext`.
- Public hostname and internal site identifier deliberately differ. Keep `PUBLIC_HOSTNAME` public and retain the existing `SITE_NAME` for database/site routing.
- Scheduled runtime: 07:00–23:00 India time. Check timing before any deployment.
- Pridict logo, splash, favicon, themes and selected display translations already exist. Do not rebuild these unnecessarily.
- Workspace titles participate in routing. Existing Pridict workspace names use translations while preserving underlying identifiers. Do not regress this fix.
- Local changes from earlier work may still be uncommitted. Preserve them and record the initial status/diff. Do not reset, clean, stash or overwrite unrelated changes.
- The image-validation workflow was prepared locally; GitHub publication/execution has not been verified. Do not assume CI/CD is active.
- The local Docker engine was unavailable during the latest read-only inspection. Check whether it is running before using the local bench; do not treat that as a product failure.
- Prior upstream test-suite runs were blocked by a missing development dependency and invalid upstream fixtures. Do not report them as passing.

Confirmed remaining branding sources:

| Source | Finding | Expected treatment |
|---|---|---|
| `erpnext/accounts/workspace/accounting/accounting.json` | Learn Accounting points to Frappe School | Remove optional shortcut until an actual Pridict guide exists, or link to a completed internal guide |
| `erpnext/setup/install.py` | Default help destinations include Frappe forum/school | Inspect installed database values and replace optional customer-facing help through supported customization |
| `erpnext/hooks.py` | ERPNext email-footer link | Trace final rendered emails and override the relevant footer mechanism |
| Authentication settings | User reported a Frappe reference; exact field/provider not yet identified | Inspect before deciding whether it is branding, a provider identity, documentation or a privileged configuration control |

## 3. Defaults and information needed

Proceed with these defaults without repeatedly asking for approval:

- Brand: Pridict; preserve the current approved visual design and light/dark themes.
- Initial language scope: English. Inventory other enabled languages and report their coverage separately.
- Until genuine Pridict learning content exists, remove optional external course shortcuts cleanly. Do not create fake articles, empty pages or redirect every help link to Home.
- Preserve existing working authentication and business integrations until their usage is understood.
- Keep infrastructure administration with operators; first audit existing customer roles before proposing permission changes.
- Keep notices and technical identifiers where they are necessary; explain intentional exceptions.

Information required only for dependent work:

| Information | Why it is needed | Work that can proceed meanwhile |
|---|---|---|
| Customer-support email or helpdesk URL | Working support destination | Inventory and remove optional promotional links; do not invent an address |
| Available Pridict guide content | Replacement learning destinations | Remove optional course links and record deferred guides |
| Authentication providers customers need | Decide provider visibility and configuration | Read-only provider audit; preserve existing login |
| Representative customer roles | Meaningful role and navigation testing | Inventory roles and prepare isolated test users |
| Additional customer languages | Translation coverage | Complete English and report other languages as untested |

Do not assume previously supplied budget-alert recipients are customer-support contacts. Do not send emails, support tickets or test messages externally without explicit authorization; use a local mail sink or rendered-message capture.

## 4. Phase A — establish a baseline and inventory

1. Record working-tree state, branch, installed app versions and current image. Use a `codex/` branch if creating one, preserving all current files.
2. Verify local development access. Read-only UAT inspection is acceptable when available; do not start branding edits directly on the live VM.
3. Search upstream source, the custom app and installed database records for visible branding and links. Use targeted `rg` searches and bounded queries, not repeated dumps of entire repositories or databases.
4. Search for `frappe`, `erpnext`, `school.frappe.io`, `docs.frappe.io`, `discuss.frappe.io`, `frappecloud.com`, `erpnext.com`, `Powered by`, `Learn`, `Help`, `Support`, and the retired public hostname. Expand the domain list from actual findings.
5. Inspect database-backed workspaces, shortcuts, onboarding steps, Navbar Settings, Website Settings, email templates, notifications, Web Pages, print formats and authentication-provider settings. Record field names and record identifiers; never export secrets.
6. Trace final rendered pages and email bodies. Source matches alone cannot prove visibility, and zero source matches cannot prove a complete rebrand.
7. Classify each finding: customer branding; operator-only configuration; functional provider/integration; required legal notice; internal code identifier; or user-owned business content.

Deliver `deployment/PRIDICT-BRANDING-INVENTORY.md` with a row for each actionable finding:

`ID | screen/route | role | visible text/destination | source/DB record | classification | proposed action | test | status`

Maintain an intentional-exceptions list with reasons. Do not bulk-replace customer documents, attachments, transaction descriptions or existing user-authored templates just because they contain a search term.

Exit criterion: an evidence-backed inventory, exact identification of the reported authentication reference, and explicit unanswered dependencies. Report when a screen could not be inspected.

## 5. Phase B — durable customization design

Use this order of preference:

1. Supported settings and documented framework/app hooks, verified against the installed version.
2. Scoped Pridict-owned templates and display translations.
3. Targeted, idempotent data patches for known upstream defaults.
4. Minimal upstream changes only if there is no supported alternative; document the reason, patch and upgrade test.

Avoid global DOM text replacement, hiding arbitrary elements with broad CSS, monkey-patching authentication internals, and renaming every occurrence of `frappe` or `erpnext`.

Proposed structure, to adapt after inspecting current conventions:

| File/area | Responsibility |
|---|---|
| `pridict_app/pridict/branding/` | Small helpers and branding/link configuration |
| `pridict_app/pridict/hooks.py` | Supported hook registration |
| `pridict_app/pridict/patches/` and app patch registry | Versioned, narrowly scoped database changes |
| `pridict_app/pridict/templates/` and `www/` | Pridict-owned help, support and notices surfaces where needed |
| `pridict_app/pridict/translations/` | Display text while retaining routing identifiers |
| `pridict_app/pridict/tests/` | Behavioural tests for migration, links and branding |
| `deployment/check-pridict-branding.*` | Focused release-time checks |

Database-change rules:

- Change a value only when it still matches the known upstream default or a previous Pridict-managed value. Preserve tenant/operator customizations.
- Record original values needed for rollback in a private migration record or backup. Never publish configuration secrets in audit artifacts.
- When removing a workspace shortcut, update both its child record and its layout/content reference. Preserve all unrelated blocks and ordering.
- Preserve workspace names, route slugs, DocType names, provider keys and database relationships.
- Migration must be idempotent: a second run produces no duplicates, additional deletions or drift.
- Verify that upstream migration does not restore removed links. If recurring reconciliation is needed, make it narrowly conditional and test it twice.

Exit criterion: a small customization design mapped to inventory findings, with upgrade and rollback behaviour described.

## 6. Phase C — customer navigation, learning and help

Implement the highest-visibility surfaces first:

1. Accounting's Learn Accounting shortcut and equivalent training links in other workspaces.
2. Home and module onboarding: headings, descriptions, videos, documentation links, tooltips and completion actions.
3. Navbar Help menu: docs, courses, forum, support, issue reporting and keyboard-shortcut/help dialogs.
4. Welcome screens, empty states, footer links, error pages and session-expiry messages.
5. Website/customer/supplier portal surfaces that are actually enabled on this site.

Use a specific useful Pridict destination for a specific task. If there is no guide, remove only the optional learning action; preserve functional ERP actions. Do not copy or relabel Frappe School course content without appropriate rights.

A Pridict help page, if implemented, must contain real useful content and working destinations. Do not advertise live chat, response SLAs or integrations that do not exist.

Exit criterion: every in-scope customer navigation link either opens the intended internal page, an approved Pridict support destination, or a documented necessary third-party service. No broken or misleading replacement links.

## 7. Phase D — authentication and operator controls

1. Identify the exact reported screen, label, provider and current enabled state. Record whether customer roles can access it.
2. Distinguish optional Frappe login from Google/Microsoft or other providers, OAuth configuration help, and generic framework text.
3. Verify which providers are actually in use. Keep current working login and an operator recovery path.
4. Where a label describes an actual Frappe service, retain truthful provider naming if used. If unused, propose disabling/removing that optional choice rather than falsely relabeling its endpoint as Pridict.
5. Branding-only labels/help text can be customized without changing protocol identifiers, callback URLs or security semantics.
6. Audit server-side permissions for customer roles. Hiding a menu is not authorization; verify direct route and API access as the same user.
7. Apply only reviewed role changes required for customer/operator separation. Do not revoke necessary customer business administration or broadly rewrite permissions.
8. If SSO settings or callback URLs must change, document the provider-console work and obtain the missing owner input before that dependent step. Do not invent credentials.

Exit criterion: accurate customer login branding, working required authentication, no customer access to operator-only secrets/configuration, and no misleading provider identity.

## 8. Phase E — emails, printed output and notices

Inspect rendered examples of:

- User invitation, welcome, password reset and email verification.
- Assignment/share messages, workflow notifications, reminders and system notifications.
- Website contact acknowledgements and portal emails, if enabled.
- Default print/PDF footers and customer-facing exports where application branding appears.
- About/version information and third-party/open-source notices.

Use Pridict application identity in system communications. Preserve tenant/company identity on invoices, quotes and other business documents; do not replace a customer's letterhead or legal business name with Pridict.

Keep sender display name, reply-to address and mail-domain authentication separate. Changing a display name is not evidence that SPF/DKIM/DMARC or delivery is configured. Capture emails locally; do not send to real customers during tests.

Preserve applicable licence and copyright notices and modification notices. Provide an accessible Open-source notices surface where appropriate; do not assume that relocating a notice satisfies every applicable licence condition. Record any unresolved licence review separately, especially if later distributing client bundles, containers or on-premise packages. No claim that all code is proprietary or originally authored by Pridict.

Reference material for that review:

- https://www.gnu.org/licenses/gpl-faq.html.en
- https://www.gnu.org/licenses/gpl-3.0.html
- https://docs.frappe.io/legal/others/license-and-trademark

Exit criterion: captured system messages use correct branding, links and sender information; tenant documents retain their identity; required notices are preserved and accessible.

## 9. Phase F — verification matrix

Test actual rendered behaviour rather than only string counts. Use an isolated site with representative data, and an ordinary customer-role user as well as Administrator.

| Area | Required checks |
|---|---|
| Authentication | Login/logout, invalid login, reset flow through mail capture, session expiry; required SSO provider if configured |
| Initial render | Server-rendered splash/favicon before JavaScript and after cache clearing |
| Navigation | Home, Accounting, Selling, Buying, Stock and all workspaces changed in this release |
| Help/learning | Click every changed action; validate destination and redirects, not merely its label |
| Forms | Sales Invoice plus at least one buying and stock form; existing routes, actions and permissions retained |
| Branding | Both themes; desktop and approximately 390px mobile width; logo contrast, focus, keyboard navigation and usable links |
| Email | Render/capture invitations, resets and notifications; verify public hostname in links |
| Permissions | Operator and representative customer; direct URL/API checks for restricted configuration |
| Persistence | Apply changes twice, migrate twice, restart containers, clear caches and recheck |
| Build | Build without local ignored `dist/` assets; verify manifest entries and asset serving from the candidate image |
| Existing site | Upgrade an isolated copy/restore of the current Pridict site without overwriting user customizations |
| New site | Install on an isolated fresh site to ensure install and upgrade paths agree |

Add a focused automated check that:

- Scans in-scope rendered pages and captured emails for unapproved upstream promotional/training/support links and the retired public hostname.
- Allows necessary technical/legal/provider references through a documented allowlist; does not fail on every `frappe` token in JavaScript or internal routes.
- Asserts that key business shortcuts remain when optional learning shortcuts are removed.
- Verifies repeated patches do not alter user-customized links.
- Verifies splash/favicon assets, public-hostname links and authenticated Desk assets.

Use representative workflow regression checks appropriate to the changed surfaces. Never submit/cancel test financial transactions in UAT. Reuse or reproduce isolated transaction-rollback tests where reliable. Record blocked upstream tests honestly rather than silently replacing them with an HTTP-200 check.

Deliver `deployment/PRIDICT-BRANDING-QA.md` with test environment, image/source revision, roles, results, screenshots or evidence references, intentional exceptions and unresolved failures. Do not include real customer data, passwords, session cookies or tokens.

Exit criterion: all changed surfaces pass; remaining gaps are explicit. A passing branding audit does not establish full SaaS production readiness.

## 10. Phase G — reviewable release and UAT deployment

1. Finish the code, inventory and QA evidence before requesting a release decision. Present unresolved dependencies and concrete changes together.
2. Create a new unique versioned image tag. Do not overwrite rc3 or deploy `latest`.
3. Reuse and review the existing Dockerfile/build/release/verification scripts. Include new splash/link checks and retain `PUBLIC_HOSTNAME` support.
4. Validate the candidate against an isolated restored site. Record exact source/image hashes and prepare a reviewable diff; preserve unrelated working-tree changes.
5. Archive exact source in the existing private storage location. Commit/push or publish CI changes only within the user's authorized scope; report what remains local.
6. Before an authorized UAT release, take a fresh database/site configuration/public/private files backup; upload and verify it. Retain the previous image and configuration records. Historical backup existence is not a substitute for a fresh recovery point.
7. Record how to reverse this release's database/settings patches. Reverting the image alone does not necessarily revert removed shortcuts or changed settings. Restoring a whole database would discard newer data; do not do so automatically.
8. Check the 23:00 shutdown schedule and enough remaining deployment time. Do not silently change the user's schedule.
9. Use the guarded release path: maintenance, worker/scheduler handling, installation/migration, cache clearing, restart and verification. On failure, follow the documented recovery path and report the actual state.
10. Verify HTTPS, authenticated login, splash/favicon, assets, changed help destinations and workers at the current public hostname. User review covers real customer-facing screens.
11. Update handoff with deployed image, hashes, recovery references, QA results and any exceptions. Distinguish files committed locally, pushed to GitHub, CI run and deployed to UAT.

Exit criterion: verified UAT release with rollback evidence and no unsupported claims of completed production readiness.

## 11. Definition of done

- The inventory covers all enabled customer-facing modules and reported authentication surfaces.
- Optional Frappe/ERPNext training, promotional and support destinations are removed or replaced by approved working Pridict destinations.
- Necessary provider names, legal notices and internal technical identifiers are deliberately retained and documented.
- No fake support destinations, copied unlicensed training content, hidden broken links or altered business records.
- Customer and operator role checks pass without losing required workflows or authentication.
- English UI, system emails, splash/favicon and both themes meet the documented checks; any additional language limitations are explicit.
- Repeated migration and restart do not restore the unwanted links or overwrite tenant customizations.
- Image builds from source; no dependency on untracked compiled assets.
- Release evidence and recovery instructions are current. If deployment is deferred, state that clearly.

## 12. CLI execution strategy and handoff prompt

Work in bounded phases to avoid repeated context and unnecessary token use. Keep an implementation checklist and concise findings in the inventory/QA files. After each phase, record changed files, tests/results, remaining decisions and the exact next step. Do not repeatedly read the entire handoff, dump all source matches or rerun all tests without a relevant change.

Suggested milestones:

1. A–B: baseline, complete inventory and implementation design.
2. C: navigation/help/learning changes and targeted tests.
3. D–E: authentication review, communications and notices; pause only dependent changes that lack necessary information.
4. F: candidate build, migration and role/browser QA.
5. G: concrete release review, then deployment when instructed.

Paste this into the existing CLI session from the repository root:

```text
Read deployment/PRIDICT-WHITE-LABEL-PLAN.md and the current-release section of
deployment/PRIDICT-HANDOFF.md. Follow applicable AGENTS.md instructions.

Implement the remaining Pridict customer-facing rebrand using this plan.
Preserve the approved light/dark UI and all existing business workflows.
Preserve existing uncommitted changes. Prefer the standalone pridict_app and
supported hooks/settings over upstream edits. Do not globally replace Frappe
identifiers, falsify provider identities, remove required notices or overwrite
customer-authored content.

Start with phases A and B: verify the local baseline, inventory source and
database-backed references, and identify the exact third-party-authentication
reference. Write the inventory and proposed implementation approach. Continue
with independent local implementation and tests for confirmed defaults; ask
only for missing information needed by dependent work. Remove optional external
learning shortcuts when no real Pridict guide exists. Do not invent support
addresses or send messages/emails to real recipients.

Do not modify UAT, DNS, authentication-provider configuration or live permissions
during this local implementation run. Read-only UAT inspection is allowed.
Prepare a versioned candidate, meaningful QA evidence and rollback instructions.
Stop before live deployment and summarize the concrete release for review.

Keep progress in deployment/PRIDICT-BRANDING-INVENTORY.md and
deployment/PRIDICT-BRANDING-QA.md. Report each milestone concisely; do not claim
tests or screens passed without evidence. Avoid repeated full-repository reads,
unnecessary rebuilds or unrelated upgrades. Never print credentials.
```

This prompt scopes a future implementation session. Writing this plan has not changed the product or deployed another image.
