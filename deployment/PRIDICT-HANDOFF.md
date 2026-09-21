# Pridict project handoff

## Approved direction
Rebrand ERPNext as Pridict with the approved Enterprise visual design in light and dark themes. Preserve current functionality, document behavior, permissions and workflows. No workflow redesign is authorized yet. Pridict 0.1.0 is now deployed to the Azure UAT site; see the current release record below.

The design preview is https://pridict-enterprise-preview.ajay-tamvada.chatgpt.site (owner-private). It is a mockup, not the running ERP system.

## Next work — customer-facing rebrand completion

See `deployment/PRIDICT-WHITE-LABEL-PLAN.md` (17 September 2026) for the detailed implementation plan and CLI handoff prompt. Remaining scope includes learning/help links, system communications and a reported authentication-provider reference. The plan distinguishes customer branding from functional provider identities, internal identifiers and required notices. Only planning documents were changed when this plan was prepared; no new product changes or deployment were performed.

## Current UAT release and public hostname — 16 September 2026

The current public URL is **https://pridict-demo.centralindia.cloudapp.azure.com**. The existing Azure public IP `erpnext-demo-ip` retains address `20.198.2.1` and now has DNS label `pridict-demo`. The previous public hostname is retired. No new Azure resource was created. `PUBLIC_HOSTNAME` in `/opt/erpnext/.env`, Caddy's HTTPS configuration and the site's `host_name` now use the new address; the internal `SITE_NAME` and database were preserved. Configuration copies are in `/opt/erpnext/release-state/20260916-hostname-before`. Hostname verification reported `HOSTNAME_CHANGE_PASS` and exit code 0.

Current image: `pridict-erpnext:0.1.0-20260916-rc3`, ID `sha256:921c2fd7d70956ff5bed02e8fc80bed4d2fbb09afb6e38659dd42d2424313798`. This release adds Pridict's square symbol for the server-rendered splash screen and favicon through `website_context` and Website Settings. Local and live checks assert that the actual Desk splash markup points to the Pridict icon, that the icon is served, and that login/Desk assets and authentication work. HTTPS/login/assets and worker checks passed again at the new hostname.

Release state: `/opt/erpnext/release-state/20260916T160013Z.env`. Fresh verified backup blob: `predeploy/2026/09/16/pridict-precutover-20260916-rc3.tar.gz`. Exact source blob: `release-candidates/2026/09/16/pridict-rc3-source.tar.gz`, SHA-256 `f69598fe393c5182e7d6768ef75140bdc55d16313a870ace266dbdfbfb1affa2`. Logs are in `/opt/erpnext/release-sources/20260916-rc3/`. The rc2 record below is historical.

## Initial UAT release (rc2) — 16 September 2026

The authorized cutover completed successfully with `UAT_CUTOVER_PASS` and exit code 0. Live URL: https://riditstack-erpnext-demo.centralindia.cloudapp.azure.com. Application services run `pridict-erpnext:0.1.0-20260916-rc2`, image ID `sha256:13a2995acf76845bb610104a19faa2cc50c86743702e702cd909ed4dcfcab3cb`. Installed versions are Frappe 15.120.1, ERPNext 15.121.2 and Pridict 0.1.0. Maintenance mode is off, scheduler enabled, and one worker was online at verification.

Release state: `/opt/erpnext/release-state/20260916T153624Z.env`. Full private cutover log: `/opt/erpnext/release-sources/20260916-rc2/cutover.log`. The fresh database, site-configuration, public-files and private-files backup is archived at `predeploy/2026/09/16/pridict-precutover-20260916-rc2.tar.gz` in the existing private backup container. Upload was downloaded again and SHA-256 verified before installing Pridict. The earlier disk snapshot remains available; the fresh file/database backup is the latest recovery point.

Fresh backup SHA-256: `a85fd5b5fbefdc7472c3443b12f259382e442de73c85dd144f6df124d59eb777`.

Exact candidate source archive: `release-candidates/2026/09/16/pridict-rc2-source.tar.gz`, SHA-256 `1ae70cfcf7a068370066ba7cd704acb19073516b95993c08473c35ba83134f82`. The image revision label records this source hash. No Git commit or push was performed; local changes remain in the working tree, and the PR validation workflow is not yet published to GitHub.

Corrections made before release: build assets inside the pinned base image instead of copying ignored local build output; include the Pridict asset links and manifest entries in every application container; parse the first column of `list-apps`; stop workers/scheduler during migration; verify both authenticated Desk and login assets; allow startup time before HTTPS checks. UI fixes keep the theme toggle outside breadcrumbs, improve navigation/input contrast, and use English translations for workspace names so existing routes remain intact. Home onboarding uses Pridict branding.

Validation: clean-context image builds passed locally and on the VM; compiled asset files and manifest entries passed; Bash syntax checks passed. Local browser checks covered light/dark Home, Sales Invoice list and unsaved form, 390px mobile form layout, theme switching across navigation, and the translated settings workspace route. Live HTTPS, administrator authentication, authenticated session, login/Desk CSS and JavaScript retrieval, installed versions and worker checks passed. The in-app browser blocked the Azure URL, so live visual review remains for the user; local visual checks and live HTTP/application checks are distinct. The broader upstream ERPNext test-suite limitations recorded below remain unresolved. Treat this as a UAT release, not completed production certification.

The audit and rc1 preparation entries below are historical and are superseded by this release record where they describe the live site as unchanged.

## Implementation sequence
1. Audit the installed ERPNext/Frappe versions, source state, customizations and deployment scripts; verify backups and recovery.
2. Build a separate Frappe customization app for branding and styles, preserving required license notices and minimizing core changes.
3. Implement the shell, navigation and Sales Invoice list/form in both themes as the first review milestone.
4. Extend consistent styling across workspaces, forms, reports, dialogs and other modules after review.
5. Validate representative accounting, selling, buying and stock operations and responsive/keyboard behavior.
6. Build versioned images and establish CI/CD and rollback, including database/file backups before migrations.
7. Obtain review of the completed UI before releasing to UAT.

## Audit and recovery status
The read-only deployment audit was completed on 16 September 2026. The live VM is healthy and runs ERPNext 15.121.2 with Frappe 15.120.1. It still uses the pinned official `frappe/erpnext:v15.121.2` image and does not have the Pridict app installed.

The deferred release-readiness backup work was completed on 16 September 2026. A full Frappe database, site configuration, public-files and private-files backup was created with prefix `20260916_194111-riditstack-erpnext-demo_centralindia_cloudapp_azure_com`, checksummed, packaged as `pridict-predeploy-20260916T141113Z.tar.gz`, and uploaded through the VM managed identity to the private blob `predeploy/2026/09/16/pridict-predeploy-20260916T141113Z.tar.gz` in storage account `pridictbkp260916`, container `erpnext-backups`. The bundle SHA-256 is `38223409ad9e1eb70f076e4e88d51a06ec7cc6c1f829abf2e9983bd5c4f192f7`. Blob and container soft deletion are 90 days and blob versioning is enabled.

The encrypted OS-disk snapshot `erpnext-demo-vm-osdisk-pridict-predeploy-20260916` completed successfully. The sanitized server manifest is `/opt/erpnext/release-manifests/pridict-predeploy-20260916T141113Z.txt`.

An isolated restore drill created `pridict-restore-validation.localhost`, restored database/public/private data, migrated it, listed the expected Frappe and ERPNext apps, and validated representative counts: 3 Users, 2 Companies, 776 DocTypes, 9 Custom Fields and 96 Property Setters. Its log reported `RESTORE_DRILL=PASS`, dropped the temporary database/user and moved the temporary site to the archive; a subsequent check confirmed the active temporary site directory was absent. The separate numeric return-code marker expected by the launcher was not present, so retain the successful restore log with the release evidence.

Step 2 began on 16 September 2026 with a standalone app scaffold in `pridict_app/`. The approved Site preview was subsequently accessed through the owner-authorized Sites connection, and its Enterprise shell, navigation, controls, list styling, status treatments and wordmark were transferred into scoped light/dark assets. Global source styling now also covers workspaces, forms, child tables, reports, dashboards, Kanban boards, dialogs, dropdowns and login surfaces. The first-review Sales Invoice layer adds scoped list density, monetary alignment, form section hierarchy, item/tax/payment grids, totals emphasis and responsive containment without changing document behavior. The workspace/dashboard layer adds section hierarchy, shortcut and metric cards, chart containers, quick lists, onboarding states and responsive single-column behavior. Customer, Supplier, Item and Employee forms share a scoped master-data treatment for tabs, sections, image controls, address/contact cards, child tables, dashboards, attachments and mobile containment. Purchase Order, Purchase Invoice, Delivery Note and Stock Entry share transaction-focused list and form styling for status rows, item and tax tables, totals, warehouse controls, addresses and responsive containment. Reports, filter popovers, dialogs and desk print previews now use the same visual system, with visible keyboard focus and reduced-motion support; generated print/PDF document content remains unchanged. The app was installed and built successfully in the disposable Docker site `development.localhost`; login and authenticated checks for all styled routes, query reports, report views, print preview and server-rendered print output passed, and the compiled Pridict CSS/JavaScript assets are served. Browser automation permission was unavailable, so final responsive, keyboard and visual QA remains a manual review item. The app is not installed on the Azure VM.

## Workflow validation status

Rollback-only workflow checks were completed on 16 September 2026 in `development.localhost`. Sales Invoice submit/cancel produced two GL entries; Purchase Order submit/cancel passed; Purchase Invoice submit/cancel produced two GL entries; Delivery Note submit/cancel produced one Stock Ledger Entry; and a Stock Entry material transfer submit/cancel produced two Stock Ledger Entries. The checks ran inside one database transaction, and tracked document and ledger counts were unchanged after rollback. The local scheduler is enabled and one worker is online.

The standard ERPNext automated test runner is not yet usable in this container without additional test-environment repair: a broad invocation stops on the missing development-only Python package `responses`, while a correctly targeted Sales Invoice test stops during upstream fixture creation because `_T-Opportunity-00001` has no company. No package installation or fixture/product change was made. These are test-environment prerequisites, not failures in the Pridict app. Manual responsive, keyboard and visual validation also remains outstanding because Chrome automation permission was unavailable.

## Release preparation status

`deployment/Dockerfile.pridict` builds a versioned derivative of the pinned ERPNext image and compiles the Pridict assets. `deployment/build-pridict-image.sh` rejects mutable `latest` tags and validates the app inside the image. `deployment/compose.yaml` now accepts `ERPNEXT_IMAGE` while retaining the official image as its default, so copying the compose file alone cannot change the live image.

`deployment/release-pridict.sh` is a deliberately guarded cutover script. It requires explicit release approval plus the verified backup-blob and snapshot identifiers, records release state, enables maintenance mode, installs/migrates Pridict idempotently, recreates application services and runs Pridict-aware verification. It leaves maintenance mode enabled if a release step fails. `deployment/ROLLBACK.md` documents why a post-install rollback to the stock image requires the verified backup or snapshot rather than an image-only switch.

A release candidate was built and validated locally on the Azure VM without changing any running container: `pridict-erpnext:0.1.0-20260916-rc1`, image ID `sha256:fbc4db6b9641dcfb25fa3d7eec510c74f362a64652b8e1774372452bf127ae12`, size 850,759,486 bytes, revision label `c8cd4b6e12-releaseprep`. Its source bundle SHA-256 is `6e85dc79a03f1dcefaa901fe2b8cd51ba3dceaa425f62b72f6c70f72faa68b92`; the exact bundle is archived privately at `release-candidates/2026/09/16/pridict-release-source-20260916T-releaseprep.tar.gz` in the existing `erpnext-backups` container. The running backend was rechecked after the build and remains on `frappe/erpnext:v15.121.2`.

The rc1 candidate was not deployed; rc2 was deployed as recorded above. The obsolete Azure Container Apps workflow is now manual-only and performs no deployment. A separate local pull-request workflow builds and validates the Pridict image without publishing or deploying it.

## Existing deployment context — verify before changes
Azure VM erpnext-demo-vm in rg-erpnext; Ubuntu, Central India. Prior recorded application versions: ERPNext 15.121.2, Frappe 15.120.1. URL: https://riditstack-erpnext-demo.centralindia.cloudapp.azure.com.
Scheduled start 07:00 and shutdown 23:00 India time. Repository: ajaytamvada/erpNext, version-15 branch. Old Container Apps workflow was disabled; do not assume current CI/CD works without auditing it.
Credentials are in the ignored .deployment-private directory. Never print, commit or copy them into prompts or documentation. Do not modify unrelated Azure resources.

## Azure coding fallback
Subscription ab14cf7b-0ed0-4736-bbed-369540c08251. Existing resource ridcode in rg-codex, East US. Deployment pridict-gpt56-sol uses gpt-5.6-sol version 2026-07-09, GlobalStandard (pay per token), capacity 30. Existing gpt-5-codex deployment is separate and preserved.
Launch with deployment/start-azure-codex.ps1. It obtains the existing Azure resource key in process memory and supplies session-only CLI overrides; no key is saved by the script and desktop configuration is unchanged.
User's AI budget is up to INR 5,000 per month. Azure budget alerts are not a hard cap. Two CLI connection tests succeeded on 2026-09-16, including the launcher using the desktop-bundled 0.154.0-alpha.6.2 executable. Azure's model catalog format produces startup metadata warnings for the custom deployment name, but the Responses calls succeed.
Budget pridict-ai-monthly is configured at rg-codex scope for INR 4,000 monthly. INR currency verified by budget GET on 16 September 2026. Actual-spend notifications are enabled at 50%, 80%, and 100% (INR 2,000 / 3,200 / 4,000) to pavan@riditstack.com and suman@riditstack.com. Scope includes the existing gpt-5-codex deployment. Alerts are not an exact spending cap and can be delayed; taxes may add charges. No continuous paid agent is running.
