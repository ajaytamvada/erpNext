# Pridict Redesign Runtime Verification Matrix

Date: September 28, 2026

This is the required user-led verification matrix. Source implementation is not visual review, functional verification, deployment, or acceptance.

## Evidence required for every row

- Exact route and document name where applicable.
- User role, company, and User Permission context.
- Source revision and environment.
- Desktop light, desktop dark, narrow light, and narrow dark evidence where the surface is customer-facing or operationally important.
- Realistic populated state plus relevant empty, loading, validation, permission, and error states.
- Primary, secondary, overflow, keyboard, and linked-document actions exercised where available.
- Explicit result for Implemented, Visually reviewed, Functionally verified, and Deployed.

Use `Pending`, `Pass`, `Fail`, `Blocked`, or `Not applicable`. Never convert `Blocked` or `Not tested` to completion.

## Structural Pages

| Screen | Implemented | Visual | Functional | Deployed |
|---|---|---|---|---|
| Pridict Home | Source | Pending | Pending | Pending |
| Pridict Procurement | Source | Pending | Pending | Pending |
| Pridict Finance | Source | Pending | Pending | Pending |
| Pridict Sales | Source | Pending | Pending | Pending |
| Pridict Inventory | Source | Pending | Pending | Pending |
| Pridict Assets | Source | Pending | Pending | Pending |
| Pridict Manufacturing | Source | Pending | Pending | Pending |
| Pridict Projects | Source | Pending | Pending | Pending |
| Pridict Quality | Source | Pending | Pending | Pending |
| Pridict Support | Source | Pending | Pending | Pending |
| Pridict Administration | Source | Pending | Pending | Pending |
| Pridict Integrations | Source | Pending | Pending | Pending |
| Schema Intelligence | Existing source | Pending new review | Pending new review | Pending |

## Primary Operational Screens

For each row, review the List and Form independently. For submittable documents, exercise draft, submitted, cancelled, amended, and returned states when supported.

| Module | DocType | List visual | List functional | Form visual | Form functional | Deployed |
|---|---|---|---|---|---|---|
| Procurement | Material Request | Pending | Pending | Pending | Pending | Pending |
| Procurement | Purchase Order | Pending | Pending | Pending | Pending | Pending |
| Procurement | Purchase Receipt | Pending | Pending | Pending | Pending | Pending |
| Procurement | Purchase Invoice | Pending | Pending | Pending | Pending | Pending |
| Finance | Payment Entry | Pending | Pending | Pending | Pending | Pending |
| Finance | Journal Entry | Pending | Pending | Pending | Pending | Pending |
| Finance | Account | Pending | Pending | Pending | Pending | Pending |
| Finance | Cost Center | Pending | Pending | Pending | Pending | Pending |
| Sales | Lead | Pending | Pending | Pending | Pending | Pending |
| Sales | Opportunity | Pending | Pending | Pending | Pending | Pending |
| Sales | Quotation | Pending | Pending | Pending | Pending | Pending |
| Sales | Sales Order | Pending | Pending | Pending | Pending | Pending |
| Sales | Delivery Note | Pending | Pending | Pending | Pending | Pending |
| Sales | Sales Invoice | Pending | Pending | Pending | Pending | Pending |
| Inventory | Item | Pending | Pending | Pending | Pending | Pending |
| Inventory | Warehouse | Pending | Pending | Pending | Pending | Pending |
| Inventory | Stock Entry | Pending | Pending | Pending | Pending | Pending |
| Inventory | Pick List | Pending | Pending | Pending | Pending | Pending |
| Inventory | Stock Reconciliation | Pending | Pending | Pending | Pending | Pending |
| Inventory | Serial No | Pending | Pending | Pending | Pending | Pending |
| Inventory | Batch | Pending | Pending | Pending | Pending | Pending |
| Assets | Asset | Pending | Pending | Pending | Pending | Pending |
| Assets | Asset Category | Pending | Pending | Pending | Pending | Pending |
| Assets | Asset Movement | Pending | Pending | Pending | Pending | Pending |
| Assets | Asset Repair | Pending | Pending | Pending | Pending | Pending |
| Assets | Asset Maintenance | Pending | Pending | Pending | Pending | Pending |
| Assets | Asset Depreciation Schedule | Pending | Pending | Pending | Pending | Pending |
| Manufacturing | BOM | Pending | Pending | Pending | Pending | Pending |
| Manufacturing | Production Plan | Pending | Pending | Pending | Pending | Pending |
| Manufacturing | Work Order | Pending | Pending | Pending | Pending | Pending |
| Manufacturing | Job Card | Pending | Pending | Pending | Pending | Pending |
| Manufacturing | Operation | Pending | Pending | Pending | Pending | Pending |
| Manufacturing | Workstation | Pending | Pending | Pending | Pending | Pending |
| Projects | Project | Pending | Pending | Pending | Pending | Pending |
| Projects | Task | Pending | Pending | Pending | Pending | Pending |
| Projects | Timesheet | Pending | Pending | Pending | Pending | Pending |
| Projects | Activity Type | Pending | Pending | Pending | Pending | Pending |
| Quality | Quality Inspection | Pending | Pending | Pending | Pending | Pending |
| Quality | Quality Goal | Pending | Pending | Pending | Pending | Pending |
| Quality | Quality Review | Pending | Pending | Pending | Pending | Pending |
| Quality | Quality Action | Pending | Pending | Pending | Pending | Pending |
| Quality | Non Conformance | Pending | Pending | Pending | Pending | Pending |
| Support | Issue | Pending | Pending | Pending | Pending | Pending |
| Support | Service Level Agreement | Pending | Pending | Pending | Pending | Pending |
| Support | Warranty Claim | Pending | Pending | Pending | Pending | Pending |

## Administration and Integrations

Each form must be checked for secret leakage in the Pridict summary as well as preservation of native protected-field behavior.

| Surface | List visual | List functional | Form visual | Form functional | Secret-safe | Deployed |
|---|---|---|---|---|---|---|
| User, Role, Role Profile, User Permission | Pending | Pending | Pending | Pending | Pending | Pending |
| Workflow, Workflow State, Workflow Action | Pending | Pending | Pending | Pending | Pending | Pending |
| Notification, Email Account, Email Template, Auto Email Report | Pending | Pending | Pending | Pending | Pending | Pending |
| Data Import, Data Export, Bulk Update, Deleted Document | Pending | Pending | Pending | Pending | Pending | Pending |
| Print Format, Print Settings, Print Style, Letter Head | Pending | Pending | Pending | Pending | Pending | Pending |
| System, Global, Domain, Website, module settings | Pending | Pending | Pending | Pending | Pending | Pending |
| Webhook, OAuth Client, OAuth Provider Settings | Pending | Pending | Pending | Pending | Pending | Pending |
| Social Login Key, LDAP Settings | Pending | Pending | Pending | Pending | Pending | Pending |
| SMS Settings, Slack Webhook URL | Pending | Pending | Pending | Pending | Pending | Pending |
| Google Settings, Contacts, Calendar, Drive | Pending | Pending | Pending | Pending | Pending | Pending |
| Dropbox Settings, S3 Backup Settings, Plaid Settings | Pending | Pending | Pending | Pending | Pending | Pending |

## Reports and Specialist Views

Each named report registered in `route_context.js` must receive its own evidence row in the environment test record. At minimum verify:

| Screen type | Required examples | Visual | Functional | Deployed |
|---|---|---|---|---|
| Financial statements | Profit and Loss, Balance Sheet, Cash Flow, Trial Balance | Pending | Pending | Pending |
| Ledgers and aging | General Ledger, Accounts Receivable, Accounts Payable, Stock Ledger | Pending | Pending | Pending |
| Procurement reports | Purchase Analytics, Procurement Tracker, Supplier Quotation Comparison | Pending | Pending | Pending |
| Sales reports | Sales Analytics, Sales Pipeline Analytics, Sales Order Analysis | Pending | Pending | Pending |
| Inventory reports | Stock Balance, Stock Ageing, Stock Projected Qty, Stock Analytics | Pending | Pending | Pending |
| Asset reports | Fixed Asset Register, Asset Activity, depreciation reports | Pending | Pending | Pending |
| Manufacturing reports | Production Analytics, Work Order Summary, Job Card Summary, BOM reports | Pending | Pending | Pending |
| Project reports | Project Summary, Billing Summary, Delayed Tasks, Timesheet Summary | Pending | Pending | Pending |
| Support reports | Issue Analytics, Issue Summary, response-time and hour distribution | Pending | Pending | Pending |
| Trees | Account, Cost Center, Warehouse, BOM where available | Pending | Pending | Pending |
| Planning views | Task Gantt, Task Kanban, calendars | Pending | Pending | Pending |
| Specialist Pages | Sales Funnel, BOM Comparison, Stock Balance, Backups, Print Format Builder | Pending | Pending | Pending |

## Customer-Facing Screens

| Screen | Visual | Functional | Deployed |
|---|---|---|---|
| Login | Pending | Pending | Pending |
| Password reset/update | Pending | Pending | Pending |
| Signup when enabled | Pending | Pending | Pending |
| Customer portal navigation | Pending | Pending | Pending |
| Supplier portal navigation | Pending | Pending | Pending |
| Orders list/detail | Pending | Pending | Pending |
| Invoices list/detail | Pending | Pending | Pending |
| Shipments list/detail | Pending | Pending | Pending |
| Quotations list/detail | Pending | Pending | Pending |
| Purchase Orders list/detail | Pending | Pending | Pending |
| Purchase Invoices list/detail | Pending | Pending | Pending |
| Supplier Quotations list/detail | Pending | Pending | Pending |
| Request for Quotations list/detail | Pending | Pending | Pending |
| Projects and Tasks | Pending | Pending | Pending |
| Issues list/new/detail | Pending | Pending | Pending |
| Material Requests list/detail | Pending | Pending | Pending |
| Web Forms | Pending | Pending | Pending |
| Public permission/not-found/server errors | Pending | Pending | Pending |
| Pridict notices | Pending | Pending | Pending |
| Pridict release notices | Pending | Pending | Pending |
| Website footer links | Pending | Pending | Pending |

## Cross-Product Surfaces

| Surface | Visual | Functional | Keyboard | Deployed |
|---|---|---|---|---|
| Global search and autocomplete | Pending | Pending | Pending | Pending |
| Notifications dropdown | Pending | Pending | Pending | Pending |
| Assignment dialog | Pending | Pending | Pending | Pending |
| Sharing dialog | Pending | Pending | Pending | Pending |
| Workflow action dialog | Pending | Pending | Pending | Pending |
| Email dialog/editor | Pending | Pending | Pending | Pending |
| Print/PDF dialog and preview | Pending | Pending | Pending | Pending |
| Import and export dialogs | Pending | Pending | Pending | Pending |
| File upload and attachments | Pending | Pending | Pending | Pending |
| Filter dialogs | Pending | Pending | Pending | Pending |
| Confirmation/destructive dialogs | Pending | Pending | Pending | Pending |
| Toasts, alerts, and message dialogs | Pending | Pending | Pending | Pending |
| Empty, loading, and failure states | Pending | Pending | Pending | Pending |

## Secondary Route Protocol

The source registry contains 214 unique workspace-linked DocTypes and 111 unique report routes. Before acceptance, export the actual permitted routes for each tested role and create one evidence record per rendered route. A generic adapter, successful route load, or shared shell is not sufficient proof that the individual screen is complete.
