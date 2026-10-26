# Pridict Automation Builder UAT Release

Date: October 26, 2026

Status: Deployed successfully to Azure UAT. Automations are **switched off** on the site
(Automation Settings > Enable Automations) until the client walkthrough.

## Release identity

- Public URL: `https://pridict-demo.centralindia.cloudapp.azure.com`
- Automations: `https://pridict-demo.centralindia.cloudapp.azure.com/app/automations`
- Source branch: `version-15`
- Source commit: `86b22d54affd2d6b435d6eb928221f6fb5285492`
- Image: `pridict-erpnext:0.1.0-20261026-automation-builder-uat4`
- Image ID: `sha256:947314a5989cd6e9eec9330c12213cbecdf74fd690920a0040330e22e4fd90a8`
- Image revision label: `86b22d54affd2d6b435d6eb928221f6fb5285492`
- Release state: `/opt/erpnext/release-state/20261026T171117Z.env`
- Previous image: `pridict-erpnext:0.1.0-20261024-nginx-resolver-uat3`

## Recovery evidence

- Backup blob: `predeploy/2026/10/26/pridict-precutover-20261026-automation-builder-uat4.tar.gz`
- Backup SHA-256: `79b4ae34fbe25c74fa6d8bb6fcf8424712a63e38eb8729497ca76a54b5108098`
- Backup size: 14,397,347 bytes
- OS-disk snapshot: `erpnext-demo-vm-osdisk-pridict-predeploy-20261026-automation-builder-uat4` (Central India, incremental)
- Snapshot provisioning state: `Succeeded` (created 2026-10-26 17:00 UTC)
- Source archive: `release-candidates/2026/10/26/pridict-20261026-automation-builder-uat4-source.tar.gz`
- Source SHA-256: `a3945c3f8f8eeded6141c0b11c64f5e485710889f4ac02673337afb729716fd5`

## Contents

First UAT release of Automations (the Automation Builder), phases 0–5 of
`documentation/automation-builder/AUTOMATION-BUILDER-TECHNICAL-DESIGN.md`:

- Automations built by chat (AI architect) or on an editable canvas, with versions, history and
  restore; Automations list page with health figures and starter templates S1–S6.
- Triggers: document events, schedules, inbound email, signed webhooks, manual.
- Steps: data, logic (If, Switch, Loop, Wait, Stop), document actions (create, update, submit,
  cancel), comment, assign, notify, email (addresses or a role), approvals and questions, HTTP
  requests (allowlist, credentials), AI step.
- Test runs (rolled back, with Simulate buttons) and the activation gate; guardrails (run and email
  limits, chain depth, auto-pause, kill switch); daily run retention; re-validation of active
  automations after every migrate.
- `deployment/compose.yaml`: the `automation` queue is registered (`workers`) and the existing
  worker also serves it.

## Verification result

- Cutover: `UAT_CUTOVER_PASS`; HTTPS login page, Administrator authentication, authenticated
  session and page assets OK; one worker online.
- Image checks during the build: `NGINX_TEMPLATE_PATCHED`, `AUTOMATION_BUILDER_IN_IMAGE`
  (architect module, `croniter` and `langgraph.types` import, canvas bundle present).
- On the site:
  - DocTypes Automation, Automation Version, Automation Change, Automation Settings, Automation
    Credential and pages `automations`, `automation-builder` exist; Agent Run has the new fields.
  - Automation Settings: enabled 0, pause_all 0, default Run As
    `automation@riditstack-erpnext-demo.centralindia.cloudapp.azure.com`, architect model
    `automation-architect` (gpt-5.4-mini, medium reasoning, fallback `procurement-reasoning`), AI
    step model `procurement-reasoning`.
  - Roles Automation Manager and Automation Viewer exist; Automation Manager granted to
    `pavan@riditstack.com` (the site's System Manager).
  - All six starter templates validate (S5 leaves the inbox to choose, as designed).
  - Worker command `bench worker --queue long,default,short,automation`, listening on all four.
- Public checks: `/api/method/ping` 200, `/login` 200.

## Operations notes

- The VM's DevTestLab auto-shutdown (17:30 UTC) was disabled for the release at 17:02 UTC and
  re-enabled at 17:15 UTC.
- Before the walkthrough: switch automations on, give the automation user the roles its
  automations need, and set up an outgoing Email Account (email steps cannot be activated
  without one). See `documentation/automation-builder/OPERATIONS.md`.
- Known limits are listed in the design document, Sections 22 and 23.

## Rollback

Restore the OS-disk snapshot above, or redeploy the previous image
`pridict-erpnext:0.1.0-20261024-nginx-resolver-uat3` and restore the verified pre-cutover backup.
The new DocTypes are additive; the previous image ignores them.
