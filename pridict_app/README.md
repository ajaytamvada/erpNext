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

## License

This app is licensed under the GNU General Public License v3.0 and is distributed with the repository-level `license.txt`. Existing ERPNext and Frappe copyright, attribution, and trademark notices must remain intact.
