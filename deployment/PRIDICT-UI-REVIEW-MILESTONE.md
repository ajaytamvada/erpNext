# Pridict UI review milestone

Review date: 17 September 2026.

This milestone uses the actual locally running Frappe/ERPNext application and database. The images are browser captures of rendered application routes, not mockups. No Azure, UAT, DNS, live authentication, or live customer data was changed.

## Local access

- Base URL: `http://127.0.0.1:8000`
- User: `Administrator`
- Password: `admin`
- Theme: use the moon/sun control in the upper-right navbar.
- Executive home: `http://127.0.0.1:8000/app/pridict-home`
- Buying workspace: `http://127.0.0.1:8000/app/buying`
- Purchase Order list: `http://127.0.0.1:8000/app/purchase-order?company=%5B%22%3D%22%2C%22_Test%20Company%22%5D&status=%5B%22in%22%2C%5B%22To%20Receive%22%2C%22To%20Receive%20and%20Bill%22%5D%5D`
- Purchase Order form: `http://127.0.0.1:8000/app/purchase-order/PUR-ORD-2026-00001`
- Accounting report: `http://127.0.0.1:8000/app/query-report/Profit%20and%20Loss%20Statement`

These credentials and records are for the isolated local development site only.

## Demonstration fixture

- Purchase Order: `PUR-ORD-2026-00001`
- Supplier: `Pridict QA Office Supplies`
- Company: `_Test Company`
- Status: `To Receive and Bill`
- Total: `INR 363,000.00`
- Items: Executive Laptop x2, 27-inch Business Monitor x4, Ergonomic Office Chair x6.
- Purpose: review-only local fixture. It was submitted locally so the standard `To Receive` workspace/list filter displays a realistic populated state. No live transaction or external message was created.

## Screenshot evidence

| Screen | Light | Dark | Width | Horizontal overflow |
|---|---|---|---:|---|
| Executive home | `design/review-20260917/executive-home-light.png` | `design/review-20260917/executive-home-dark.png` | 1440px | No |
| Buying workspace | `design/review-20260917/buying-workspace-light.png` | `design/review-20260917/buying-workspace-dark.png` | 1440px | No |
| Populated Purchase Order list | `design/review-20260917/purchase-order-list-light.png` | `design/review-20260917/purchase-order-list-dark.png` | 1440px | No |
| Purchase Order item grid | `design/review-20260917/purchase-order-form-light.png` | `design/review-20260917/purchase-order-form-dark.png` | 1440px | No |
| Profit and Loss Statement | `design/review-20260917/profit-and-loss-report-light.png` | `design/review-20260917/profit-and-loss-report-dark.png` | 1440px | No |

Machine-readable route, title, theme and overflow evidence is in `design/review-20260917/capture-manifest.json`. The captures can be regenerated with `deployment/capture-pridict-review.ps1` while the isolated local site and a Chrome debugging session are running.

Post-milestone continuation added matching 390x844 light/dark captures under `design/review-20260917/mobile/`. Its `capture-manifest.json` confirms no document-level horizontal overflow for all five screens.

## Comparison with the approved design

The captured application follows the approved visual direction through a persistent navy navigation rail, compact dark top bar, restrained blue selection state, high-contrast light and dark canvases, card-based groupings, strong page headings, compact controls, subdued borders, tabular financial figures, and consistent spacing.

### Structural layout change

- **Executive home:** purpose-built Frappe Page. The approved dashboard hierarchy was implemented as a real application screen with its own sidebar navigation, company and date controls, KPI row, attention queue, business-area links, activity panel and revenue/expense chart. The data API and permission model are also custom to this page.

### Existing structure with product-wide styling

- **Buying workspace:** retains the supported Frappe Workspace composition, chart, shortcuts and report/master links. The shell, sidebar, cards, spacing, type, controls and theme treatment were redesigned without inventing a replacement procurement workflow.
- **Purchase Order list:** retains Frappe list behavior, filters, sorting, pagination, bulk selection and document navigation. The navy filter rail, toolbar, table density, status treatment, typography, borders and theme states are Pridict styling.
- **Purchase Order form:** retains ERPNext document sections, tabs, item child table, totals, timeline and document actions. Pridict styling changes section hierarchy, grid density, monetary emphasis, controls, borders and dark-mode contrast. The milestone capture is intentionally scrolled to the real three-row item grid.
- **Profit and Loss Statement:** retains the ERPNext report engine, filters, calculations and export/actions. Pridict styling changes the report header, filter panel, summary cards, table/empty state and dark-mode presentation. The current fixture period has zero accounting activity, so this capture verifies the honest empty state rather than fabricated figures.

## Verification completed

- Ten actual application screenshots captured: five screens in light and dark mode.
- All ten captures report no horizontal overflow at 1440px.
- Ten additional application screenshots captured at 390x844 in light and dark mode; all report no document-level horizontal overflow.
- Mobile verification exposed and corrected an empty `.layout-side-section` column that occupied the viewport while Frappe's inner overlay sidebar was closed. The inner overlay remains available through the standard sidebar toggle.
- The Buying workspace was recaptured after persisting a valid local default company; the original `Company is mandatory` dialog is not present in final evidence.
- The Purchase Order list is populated through an explicit company/status route and displays the local submitted fixture.
- A disposable `Purchase User` with a `_Test Company` User Permission could list and directly read `PUR-ORD-2026-00001`; the user and permission were removed after the check.
- Existing Administrator access, theme switching, route navigation and document rendering remain functional.

## Implementation gaps

- The unresolved authentication-provider reference still cannot be reproduced because the inspected site has no Social Login Key records, no generic OAuth Provider DocType and LDAP disabled.
- Real Pridict learning content does not exist; optional upstream training links remain removed rather than redirected to invented pages.
- Remaining specialized screens may need narrowly scoped visual fixes as they are inspected; shared CSS alone is not treated as completion.
- The local demonstration fixture is test data and must not be migrated or copied to UAT.

## Testing gaps

- The Profit and Loss screenshot verifies an actual zero-data report state; a populated non-zero period and additional currency scenarios remain to be visually and numerically reconciled.
- The ten-screen milestone uses Administrator for visual capture. Purchase User data access was verified through authenticated APIs, but an ordinary-role visual capture is still outstanding.
- Mobile screenshots now cover these five exact screens, but complete touch interaction, orientation changes and long-data/table states remain outstanding.
- Full keyboard traversal, screen-reader labeling checks, session expiry, loading failures, validation errors and long-content states remain incomplete.
- Populated Customer and Supplier portal transactions and broader ordinary-role workflows remain incomplete.
- Independent PDF raster inspection remains unavailable; PDF structure/text and the matching HTML print preview are verified.

## Continued work after this milestone

Continue the ordinary-role and populated-state matrix, starting with purchasing-role visual coverage and mobile interaction checks. Then proceed through finance, sales, stock, manufacturing, projects, quality, support and website exceptions without treating uninspected routes as tested.
