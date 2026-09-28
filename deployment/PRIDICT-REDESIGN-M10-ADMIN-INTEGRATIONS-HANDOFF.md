# Pridict Redesign Milestone 10: Administration and Integrations Source Handoff

Date: September 28, 2026

Status: Implemented in source only. Not visually reviewed, functionally verified, built, migrated, deployed, or accepted.

## Scope decision

- HRMS and Payroll are not present in the local source tree, so no HRMS or Payroll screens were invented or marked complete.
- The core ERPNext Employee master remains available within Administration because it is used by assignments and transactions.
- This milestone covers the verified Administration and ERPNext Integrations workspaces and their principal linked DocTypes.

## Source scope

- Added role-restricted `Pridict Administration` and `Pridict Integrations` operating Pages for System Managers.
- Updated the persistent shell to open the structural Pridict Pages while retaining standard ERPNext Settings, Users, Tools, Integrations, and ERPNext Integrations routes as compatibility paths.
- Added administration navigation and adapters for users, roles, role profiles, user permissions, workflows, workflow states, notifications, email accounts and templates, scheduled reports, import/export, print formats and settings, system/global/website settings, and Employee.
- Added integration navigation and adapters for webhooks, social login, LDAP, OAuth, SMS, Slack, Google services, Dropbox, S3 backup, and Plaid settings.
- Added permission-aware counts and grouped entry points without retrieving or presenting passwords, client secrets, tokens, secret keys, webhook URLs, or protected authorization data.
- Added shared list introductions, safe form summaries, native grid treatment, module journeys, responsive Page layouts, and focused Page contract tests.

## Functional boundary

- Native user and role permissions, User Permissions, workflow transitions, notification evaluation, email account behavior, imports, exports, print rendering, and system settings remain unchanged.
- Native provider authentication, OAuth grants, LDAP behavior, callback handling, webhook delivery, backup execution, SMS delivery, Google synchronization, and banking integrations remain unchanged.
- Provider names remain truthful. Technical routes, DocType names, callback identifiers, package names, and integration-specific terminology are not rebranded.
- Sensitive values remain inside native protected fields and are intentionally excluded from Pridict summary cards.
- Page access is restricted to the System Manager role in both Page metadata and backend methods.

## Visible result

- System Managers receive dedicated Administration and Integrations landing Pages instead of being sent directly to the standard workspaces.
- Configuration is grouped into clear operational areas with concise descriptions, counts, and direct navigation.
- Lists and forms retain native controls but gain the shared Pridict navigation, hierarchy, spacing, summary framing, and responsive behavior.
- Existing workspaces remain available for compatibility and uncommon administrative tools.

## Validation

- JavaScript syntax checks passed for both Pages, the shared Administration/Integrations adapter, shell, and route context.
- Both Page JSON files parsed successfully and include the System Manager role.
- Read-only Python AST parsing passed for both Page backends, focused tests, and hooks.
- Local ERPNext source verification confirmed the Employee summary fields and every integration linked by the ERPNext Integrations workspace.
- SCSS brace validation and `git diff --check` passed.
- Focused Frappe tests were added but not run because a local Frappe test runtime is not available in this workspace.
- No asset build, migration, browser review, screenshots, provider connection, secret read, broad test suite, image build, or deployment was run.

## Next target

Continue with cross-product surfaces: search, notifications, dialogs, assignments, sharing, workflow actions, print and email dialogs, import/export states, loading and empty states, permission and server errors, and other system utilities. Handle trees, builders, recovery tools, and secret-bearing screens as named exceptions rather than forcing them into generic layouts.

Do not treat this handoff as runtime acceptance or deployment readiness.
