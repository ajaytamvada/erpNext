# Purchasing analysis UI

## Inspection findings (2 October 2026)

The September 30 release delivered backend modules, not an accepted usable product screen.
There was no `process-intelligence` Page, page role assignment, navigation entry, company/date
form, result renderer, graph, journey viewer, or permission-checked document-link resolver.
The existing manager-only APIs return pseudonymized artifacts. Their collector deliberately
bypasses document permissions and must not be exposed unchanged to ordinary purchasing users.
The prior disposable-site demonstration contained three unlinked documents and zero edges;
it did not demonstrate an end-to-end purchasing journey. Deployment/import checks do not
establish UI or functional acceptance.

## Scope

Reuse the existing schema capture, collection, reconstruction, graph and metric models.
Add a permission-aware, non-persisting screen adapter and a standard Frappe Desk Page.
Access requires System Manager or Process Analyst, plus existing company/document read
permissions. Process Analyst does not grant business-document access by itself.
Preserve pseudonymized exports; resolve names and links only in the authorized live response.
Dates mean document creation dates in the site's timezone, not posting dates or completion dates.
The screen must distinguish observed counts/links/states, missing or excluded evidence,
and unsupported duration/handoff metrics. No Decision Intelligence or workflow redesign.

## Verification and deployment

| Area | Status on 2 October 2026 |
| --- | --- |
| Backend | Existing reconstruction service reused. Added a permission-aware presentation adapter. Corrected cross-stage quantity double counting and payment references disappearing when their source invoice is outside scope. 19 regression tests passed. |
| UI | Standard Page, two navigation entries, company/creation-date inputs, loading/error/empty states, observed facts, directed graph with a table equivalent, searchable/paged journey selector, document timelines, supporting links, historical evidence, missing-evidence panel and unsupported-metric panel implemented. Thirty real-browser assertions passed with 22 screenshots. Renderer/escaping/pagination checks, eight route-classification cases, syntax checks for 62 application JavaScript files and the production asset build passed. Human visual acceptance remains pending. |
| Integration | Nine isolated-site checks passed in 296.480 seconds, including setup readiness, deterministic/read-only reconstruction and record-level permissions. Authenticated HTTP checks passed for an ordinary analyst, the Page script, CSS/navigation assets and all seven supporting documents. Guest, missing analysis role, missing business-document role, restricted company and restricted individual order were tested. See `evidence/integration-tests.txt`. |
| Deployment | Installed and running only on the local isolated site `process-intelligence.localhost`, using Frappe 15.120.1, ERPNext 15.121.2 and Pridict 0.1.0. No Azure commands or UAT business transactions were used. This change has not been committed, pushed, built as a release image or deployed to UAT. |

The local implementation now passes browser interaction checks, but remains **pending user
acceptance**, not UAT-released or production-certified. The resumed Windows computer-use tools
failed during kernel startup. A separately approved, isolated headless Chrome profile was used
for real local-page interaction and screenshot capture, not HTML mockups. Automated geometry,
DOM assertions and screenshots are not a substitute for human visual review; the screenshots
have not been visually signed off. No application screenshot or business result was fabricated.

## Resumed verification and fixes

Browser evidence is timestamped in UTC in `evidence/browser/verification.json` and
`evidence/browser/ui-verification.json`. The purchasing run has 30 passing assertions and
22 screenshots; the shared UI run has 66 passing assertions and 14 screenshots. Neither
run observed an uncaught JavaScript runtime exception.

- Repaired the isolated fixture's `Installed Application` setup flags and its leftover
  `desktop:home_page=setup-wizard` default. The old partial setup caused ordinary users to
  be redirected to an inaccessible wizard and hid the reviewer's native toolbar. This is
  local test-site preparation, not a production setup bypass or permission change.
- Removed native negative row gutters that clipped the analysis panel on mobile. At 390px,
  the panel now starts at x=10 and ends at x=380 instead of starting at x=-5. Tested in both
  themes; desktop and mobile page-width checks pass.
- Classified Process Intelligence as a Desk Page rather than a workspace, while retaining
  its own active navigation section.
- Corrected journey pagination so the detail belongs to a journey on the visible page,
  clamped out-of-range page indexes and preserved keyboard focus after selection/pagination.
  Multi-page cases use synthetic unit-test data only, not fabricated demonstration evidence.
- Verified both navigation entries, loading, real empty dates, invalid dates, search,
  graph/history disclosures, keyboard selection, all seven new-tab document links, denied
  access and recovery from a deliberately blocked analysis network request.
- Verified saved shared-UI fixes on Website, Workflow State, Sales Invoice, Purchase Order,
  Stock Entry and General Ledger in 1440px light and 390px dark layouts. Correct navigation,
  compact list filters, same-route preset application/clearing, workspace sidebar ownership,
  page-context deduplication and notification geometry pass. This is a targeted regression
  matrix, not a claim that every product route has been visually accepted.
- Made the temporary permission-test order independent of the run date: its transaction
  date matches its required-by date, and analysis includes its actual creation date. The
  test first verifies visibility before adding the temporary restriction. Both are rolled back.

## Exact access and navigation

Local URL: http://process-intelligence.localhost:8000/app/process-intelligence

1. Sign in to the isolated site as `pi.analyst@example.test`, password `Local-PI-Demo-2026!`.
   These are newly created local-only demonstration credentials, not UAT credentials.
2. Use **Pridict left navigation → Process Intelligence**. Alternatively use
   **Procurement → Process Intelligence** in the page toolbar.
3. Select **PI Demonstration**, **Created from: 2026-10-02**,
   **Created through: 2026-10-02**, then **Analyze purchasing**.
4. Review observed results and the graph, choose **Journey 1**, and open a document-number
   link to inspect the original document in a new tab. Expand the connection table and
   available historical evidence. Review the separate missing/unsupported panels.

The navigation entries, analysis action and supporting-link click-through sequence were
verified in the real browser. The server was started with
an explicit `--site process-intelligence.localhost` binding. It uses the existing local Docker
stack and a newly created site/database, not a copy of UAT. The scheduler remains disabled.

## Real linked fixture and observed result

All seven documents were created with standard ERPNext mappings, validated and submitted.
No fabricated lifecycle timestamps or manually inserted correlation records were used.

| Stage | Document |
| --- | --- |
| Material Request | MAT-MR-2026-00001 |
| Request for Quotation | PUR-RFQ-2026-00001 |
| Supplier Quotation | PUR-SQTN-2026-00001 |
| Purchase Order | PUR-ORD-2026-00001 |
| Purchase Receipt | MAT-PRE-2026-00001 |
| Purchase Invoice | ACC-PINV-2026-00001 |
| Payment Entry | ACC-PAY-2026-00001 |

The fixture purchases ten units at INR 100 each. The INR 1,000 invoice has zero outstanding
amount after the submitted payment. Reconstruction observes **7 documents, 10 explicit links,
1 connected journey, 0 unlinked documents and 0 over-allocation warnings**. This is a linked,
paid purchasing fixture, not evidence for a measured process-completion timestamp.
Cycle time, approval time, waiting time and handoff count remain `DATA_NOT_AVAILABLE`.
No approval-workflow history was manufactured. The integration test's temporary extra order
and permission restriction were rolled back, leaving the seven-document fixture intact.

Before/after SHA-256 fingerprints matched for purchasing headers, child rows, GL, Stock Ledger,
Payment Ledger, Version, Workflow Action, Workflow and User Permission records. Repeat
reconstructions matched after excluding observation timestamps. The local HTTP analysis took
44.27 seconds on the latest authenticated HTTP check. This local latency remains a known
limitation, not a production performance claim; large-volume and production-latency validation
have not been performed. The screen's loading and failure/retry states were browser-tested.

## Evidence and reproduction

- `evidence/fixture.json`: actual local document identifiers and scope.
- `evidence/analysis.json`: real API result, including local synthetic document links.
- `evidence/read-only.json`: matching fingerprints and deterministic result.
- `evidence/integration-tests.txt`: eight successful real-site tests.
- `evidence/http-verification.json`: authenticated transport and document-loading checks.
- `evidence/browser/verification.json`: 30 real-browser purchasing assertions and screenshot list.
- `evidence/browser/ui-verification.json`: 66 shared-UI assertions and screenshot list.
- `evidence/browser/*.png`: 36 screenshots from the successful runs; use the JSON manifests,
  not the diagnostic `failure.png` from earlier test iterations.

From `/workspace/development/frappe-bench` in the local bench container:

```sh
env/bin/python /workspace/development/apps/erpnext/deployment/verify-process-intelligence.py
env/bin/python /workspace/development/apps/erpnext/deployment/verify-process-intelligence-http.py
env/bin/python -m unittest pridict.process_intelligence.test_process_intelligence pridict.process_intelligence.test_process_reconstruction
bench build --app pridict
```

From the repository root: `node deployment/test-process-intelligence-rendering.cjs`.
Also run `node deployment/test-pridict-ui-routing.cjs` and JavaScript syntax checks.
The fixture script requires the exact isolated site name and `allow_process_intelligence_demo=1`;
it creates fixtures only with `--seed`, is idempotent after the manifest is written, and is not
a whitelisted product endpoint. Business permissions are assigned to local test users only.
Process Analyst itself grants no purchasing, accounting or company permissions.

For an existing fixture created before the setup repair, run the verification script once with
`--prepare-browser`. It is guarded to this exact isolated site, does not recreate purchasing
documents, completes local setup metadata and creates `pi.reviewer@example.test` for shared-UI
testing with local System/Accounts/Stock/Purchase/Sales/Website Manager roles. It uses the same
local-only demonstration password as the analyst. No UAT user or permissions are changed.

Start the existing local server with `bench --site process-intelligence.localhost serve --port 8000
--noreload`. For browser reproduction, launch a separate Chrome profile with
`--headless=new --remote-debugging-port=9225 --user-data-dir=<absolute-repo-path>/output/pi-browser-profile`
and the local login URL, then run `node deployment/verify-process-intelligence-browser.mjs`.
Set `PI_MODE=ui` for the shared-UI matrix. The harness only selects the exact local site on
port 9225; `PI_DEMO_PASSWORD` can override the local demonstration password. The browser profile
is ignored by Git because it holds local session data. Do not publish it or point this harness at UAT.

The temporary headless Chrome session was closed after validation; the Docker web server remains
available for review. Final login health returned HTTP 200 inside the container and over Windows
IPv6 loopback. On this machine, a different service answers IPv4 `127.0.0.1:8000` with HTTP 404,
and PowerShell does not resolve the `.localhost` subdomain itself. Do not stop that unrelated
service or mistake its response for the demo. Chrome used the working IPv6 route. For a Windows
CLI health check, use `curl.exe --noproxy "*" --resolve "process-intelligence.localhost:8000:[::1]"
http://process-intelligence.localhost:8000/login`.

Remaining acceptance work: human review of the captured light/dark/mobile screenshots and the
local experience, broader accessibility/production-volume testing and a performance decision
about the observed local latency. UAT release preparation and deployment remain separate,
explicitly authorized steps after review. Nothing in this checkpoint grants deployment approval.
