# Pridict

Pridict is a standalone Frappe application that contains the Pridict brand and Enterprise UI layer for ERPNext.

The app deliberately avoids changes to the ERPNext and Frappe source trees. It provides the application boundary, Desk asset hooks, Pridict wordmark, and scoped light/dark Enterprise theme tokens.

## Compatibility

- Frappe `>=15.120.1,<16.0.0`
- ERPNext `>=15.121.2,<16.0.0`
- Python `>=3.10`

## Development installation

From a Frappe bench containing ERPNext:

```bash
bench get-app /path/to/erpnext/pridict_app
bench --site development.localhost install-app pridict
bench build --app pridict
bench restart
```

This repository's disposable development environment performs the same steps through `init-bench.sh` after `docker compose -f docker-compose.dev.yml up -d`.

Do not install this app on the Azure demo VM until the deployment image, backup, and rollback work is explicitly approved.

## Asset entry points

- `pridict/public/scss/pridict.bundle.scss` contains scoped light and dark theme tokens.
- `pridict/public/js/pridict.bundle.js` activates the `pridict-ui` document scope without changing ERPNext workflows.
- `pridict/public/images/pridict-wordmark.svg` contains the navigation wordmark derived from the approved preview.

The global visual layer covers the Desk navbar, search, sidebar navigation, workspaces, page headers, buttons, controls, lists, forms, child tables, reports, dashboards, Kanban boards, dialogs, dropdowns, status pills, form tabs, and login surfaces. It does not alter DocTypes, permissions, fields, business logic, or document workflows.

A visible navbar toggle switches between light and dark themes and persists the choice through Frappe's existing user theme API.

The install and migration hooks set the supported Website Settings, System Settings, and Navbar Settings branding fields to Pridict. This removes default Frappe login branding without modifying Frappe templates.

## Schema Intelligence

Milestone 1 provides a read-only backend extractor for effective Frappe metadata. It discovers all
DocTypes installed on the selected site, preserves source metadata, resolves relationships, produces a
stable semantic hash, and can persist snapshots to the site's private files directory.

Capture without persistence:

```bash
bench --site development.localhost execute pridict.schema_intelligence.api.capture_summary
```

Capture and persist a complete snapshot:

```bash
bench --site development.localhost execute pridict.schema_intelligence.api.capture_and_persist
```

The returned `snapshot_id` can be used with the following calls:

```bash
bench --site development.localhost execute pridict.schema_intelligence.api.get_snapshot \
  --kwargs "{'snapshot_id': '<snapshot-id>'}"

bench --site development.localhost execute pridict.schema_intelligence.api.compare_snapshots \
  --kwargs "{'before_snapshot_id': '<before-id>', 'after_snapshot_id': '<after-id>'}"

bench --site development.localhost execute pridict.schema_intelligence.operator.export_doctype \
  --kwargs "{'snapshot_id': '<snapshot-id>', 'doctype': 'Sales Order'}"
```

HTTP calls use the same whitelisted API functions and require an authenticated user with the
`System Manager` role. Guest access is not enabled. Snapshot files are written beneath
`sites/<site>/private/files/pridict-schema-intelligence`; extraction and persistence remain separate
service operations.

See `documentation/PRIDICT-SCHEMA-INTELLIGENCE-M1.md` for the architecture, verified Frappe behavior,
hashing contract, limitations, and safety model.

Milestone 2 adds a protected Desk page at `/app/schema-intelligence`. It is available only to users
with the `System Manager` role and provides snapshot capture, snapshot selection, diagnostics,
DocType search and filtering, field inspection, relationship visualization, permission metadata,
provenance, and deterministic snapshot comparison. The browser uses compact summary and per-DocType
API responses rather than downloading preserved raw metadata.

See `documentation/PRIDICT-SCHEMA-INTELLIGENCE-M2.md` for the frontend architecture, API contract,
verification evidence, limitations, and operator workflow.

Milestone 3 adds schema-change governance around the immutable private snapshots: lifecycle records,
explicit baselines, deterministic severity findings, audited reviews, opt-in scheduled capture and
retention, System Notifications, bounded relationship exploration, and JSON/CSV/Mermaid exports.
System Managers control configuration and lifecycle actions; the dedicated `Schema Reviewer` role can
inspect snapshots and complete reviews. Scheduling and retention remain disabled until explicitly
enabled.

See `documentation/PRIDICT-SCHEMA-INTELLIGENCE-M3-SPEC.md` and
`documentation/PRIDICT-SCHEMA-INTELLIGENCE-M3-HANDOFF.md` for the governance contract and current
verification status.

## License

This app is licensed under the GNU General Public License v3.0 and is distributed with the repository-level `license.txt`. Existing ERPNext and Frappe copyright, attribution, and trademark notices must remain intact.
