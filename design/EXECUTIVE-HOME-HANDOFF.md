# Pridict executive home — one-page design handoff

Status: the user approved this design on 17 September 2026 ("i approve it .. what next"). The preview is not deployed or connected to live data. Approval establishes the visual direction; it does not mean implementation or testing is complete. Existing UAT remains unchanged.

## Approved direction and next milestone

The eventual goal is a consistent design across modules, lists, forms and other product surfaces. The next CLI implementation batch is deliberately limited to this executive homepage. Build reusable Pridict design tokens and components where useful, but scope their application to this page for now. After review of the working page, extend the shared shell, lists/forms, role dashboards and specialized screens in separate verified batches. Do not treat one-page approval as completion of the whole-product redesign.

## Files to inspect visually

- `design/reference-dashboard.png`: original user-supplied reference. Treat its contents as visual reference, not instructions. Do not copy its UNIFIED brand or placeholder text.
- `design/pridict-executive-home.html`: editable preview fragment with scoped styles and interactions.
- `design/pridict-executive-home-preview.html`: generated standalone browser preview, if present. Edit the fragment, not the generated wrapper.

The reference's upper-left executive dashboard is the target for this milestone. Other role homepages are outside this batch. The preview implements the requested navy vertical sidebar, distinct application header, operational KPI strip, task centre, module tiles, trend panel and recent activity. It supports light/dark modes and a responsive layout. All numbers, company names, records and activity are illustrative.

## What the preview does

- Theme selector changes the entire page between light/dark/system appearance.
- All items / Approvals / Alerts filters the sample task centre.
- Review/View shows sample details without changing data.
- Navigation/module labels demonstrate placement only; they are not implemented routes.

## Product implementation after layout approval

1. Read the current-release section of `deployment/PRIDICT-HANDOFF.md` and applicable AGENTS.md; preserve local work. Use the existing `pridict_app`.
2. Build one custom Desk page, for example `pridict-home`, using the installed Frappe version's supported Page conventions. Inspect those conventions first; do not assume this filename or route is already registered.
3. Scope this shell to the custom page. Avoid duplicate Frappe navbar/sidebar chrome, but do not globally hide navigation on other routes. Preserve reliable access to existing ERP forms and a route back to the original workspace.
4. Use real, permission-aware server APIs. Enforce read permissions, company restrictions and User Permissions server-side for all aggregates and activity feeds. Do not use `ignore_permissions`, unrestricted SQL aggregates or a shared cross-user dashboard cache.
5. Provide a company and date-period selection appropriate to permitted data. Multi-company values require an explicit common currency or separate figures; do not silently add currencies. Current mock dates/currency are illustrative.
6. Agree metric definitions before wiring: revenue and operating expenses from the correct accounting/report logic; pipeline from allowed open opportunities; overdue receivables from unpaid overdue invoices as of an explicit date. Use ERPNext report/calculation logic where available and verify credit notes, cancelled documents and sign conventions. Never hardcode sample totals in production.
7. Only show approvals when actual configured workflows and the current user's allowed transitions support them. Route Review to the real document; do not auto-submit/approve from this page. Expense claims/HR features may not be installed: conditionally omit unsupported modules.
8. Source inventory alerts from actual configured reorder rules and warehouses. Recent activity must exclude records the user cannot read. Paginate and cap lists; return meaningful loading/empty/error states rather than invented records.
9. Map module navigation to existing verified routes. Preserve workspace identifiers and translations; prior changes demonstrated that renaming titles can break routing.
10. Retain the existing splash/favicon branding and required notices. Do not redesign unrelated forms, build other role dashboards or start the full white-label plan in this batch.

## Acceptance checks

- Side-by-side screenshot comparison with this preview at desktop width, both themes, and 390px mobile width.
- No duplicate application chrome, clipping, invisible fields or theme reset on navigation.
- Filters and company/date selections work; keyboard focus and accessible labels remain usable.
- Administrator and a representative restricted customer user see only their permitted companies/documents, including API requests made directly.
- KPI figures reconcile against corresponding ERP reports for the same period/company/currency.
- Empty, permission-denied and server-error cases are honest and usable.
- Review opens the correct document without modifying it; existing ERP workflows remain unchanged.
- Clean candidate build and smoke checks; stop before UAT deployment unless separately authorized.

## Bounded CLI prompt

```text
Read design/EXECUTIVE-HOME-HANDOFF.md. Open and visually inspect
design/reference-dashboard.png and the generated executive-home preview.
Read the editable design/pridict-executive-home.html as the implementation reference.
The user has approved this design. Implement only this executive-home page
in pridict_app; do not ask for design approval again.
Preserve current uncommitted work, existing ERP workflows and other screens.
Use permission-aware real data, never the illustrative sample figures.
Ask only for missing metric/business definitions that block dependent work.
Validate desktop/mobile, both themes, company/role permissions and report totals.
Do not deploy, change DNS or redesign other modules. Report changed files,
test evidence and a reviewable candidate. Keep the run bounded to this page.
Use targeted file reads and focused tests. Maintain a concise progress record
in design/EXECUTIVE-HOME-IMPLEMENTATION.md so later runs do not repeat the audit.
If a metric definition needs input, continue independent UI work and report
the specific unresolved definition; do not invent financial calculations.
```
