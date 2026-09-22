# Pridict Schema Intelligence Milestone 2

## Scope

Milestone 2 adds a read-only Schema Intelligence frontend to the existing Pridict Desk experience.
It does not change ERPNext business records, workflows, accounting, inventory, permissions, or the
Milestone 1 extraction safety model. No Azure or UAT environment was accessed.

The protected route is `/app/schema-intelligence`. The Page document and every whitelisted endpoint
require the `System Manager` role; guest access is rejected.

## Architecture

The frontend is implemented as a standard Frappe Page:

- `pridict/pridict/page/schema_intelligence/schema_intelligence.json` defines the protected Page.
- `pridict/pridict/page/schema_intelligence/schema_intelligence.js` owns page state, rendering, and
  user interactions.
- `pridict/public/scss/pridict.bundle.scss` provides responsive light and dark theme styles.
- `pridict/schema_intelligence/service.py` exposes compact presentation-oriented service functions.
- `pridict/schema_intelligence/api.py` exposes authorized whitelisted API methods.

The UI does not receive the complete persisted snapshot during normal browsing. It loads snapshot
summaries, a compact DocType catalog, and one selected DocType at a time. Raw metadata remains in the
private snapshot file and normalized provenance is retained in the detail response.

## API contract

All HTTP endpoints require an authenticated System Manager:

- `list_snapshots()` returns newest-first compact snapshot summaries.
- `get_snapshot_overview(snapshot_id)` returns the summary, DocType catalog, and diagnostics.
- `get_doctype_schema(snapshot_id, doctype)` returns normalized fields, relationships, permissions,
  properties, flags, and provenance for one DocType.
- `capture_and_persist(allow_incomplete=0)` captures and persists a complete snapshot and returns its
  compact summary.
- `compare_snapshots(before_snapshot_id, after_snapshot_id)` returns a deterministic structural diff.

Incomplete captures are rejected by default and do not silently become baseline snapshots.

## User experience

The page provides:

- explicit snapshot capture and selection;
- completeness, version, count, hash, and diagnostic summaries;
- DocType search and standard/custom/child/single/virtual filters;
- field metadata with flags and provenance sources;
- relationship graph and complete relationship list;
- permission metadata clearly presented as metadata, not effective-user authorization;
- normalized DocType properties and provenance;
- deterministic before/after comparison.

The relationship graph renders the first 16 relationships for readability while the adjacent list
retains every extracted relationship.

## Verified environment

Verification was completed locally on 22 September 2026 with:

- Frappe `15.120.1`;
- ERPNext `15.121.2`;
- Pridict `0.1.0`;
- Docker Desktop with the local `erpnext_frappe_bench` container;
- site `development.localhost`;
- disposable Milestone 1 sites `schema-clean.localhost` and `schema-custom.localhost`.

The development site contained two complete unchanged snapshots. Both produced metadata hash
`73ae6f9dc9e8b0f07ef1b8d4b63cd967baa23a9c838a64bf3851f94f4a9a110d`, demonstrating equivalent
unchanged content in the comparison UI.

The live compact API verification returned:

- 776 DocTypes;
- 12,685 fields;
- 2,795 relationships;
- 1,048 permission rows;
- 160 Sales Order fields;
- 39 Sales Order relationships;
- 6 Sales Order permission rows;
- no raw metadata in overview or DocType detail responses.

## Verification results

Static and build checks:

```text
node --check schema_intelligence.js: passed
Python compile checks: passed
bench migrate: passed
bench build --app pridict: passed
```

Automated tests:

```text
Schema Intelligence focused unit suite: 15 passed
Schema Intelligence Page role test: 1 passed
Protected API authorization test: 1 passed
Full Pridict regression suite: 32 passed, 4 expected skips
```

The full suite emitted two existing CSS Level 2.1 parser warnings for `1rem` and `fit-content`; they
did not fail tests or originate from the Schema Intelligence assertions.

Browser verification used a temporary local headless Chrome session against the running Frappe site:

- desktop viewport at 1440 by 1000;
- mobile viewport at 390 by 844;
- light and dark themes;
- no document-level horizontal overflow at mobile width;
- snapshot selector, search, DocType selection, all detail tabs, relationship graph, permission view,
  metadata view, and comparison dialog exercised successfully;
- guest route access redirected to login.

Observed local timings for the large development snapshots were approximately 8.1 seconds for the
two-snapshot list, 3.9 seconds for overview, 4.0 to 4.7 seconds for Sales Order detail, and 11.7
seconds for comparison. These timings are local development measurements, not production targets.

## Operator workflow

1. Sign in as a user with the `System Manager` role.
2. Open `/app/schema-intelligence` or use the Schema Intelligence link on the Pridict home page.
3. Select **Capture Snapshot** to create a complete private snapshot.
4. Select a snapshot to browse its DocTypes and diagnostics.
5. Select **Compare Snapshots** after at least two snapshots exist.

The existing trusted bench commands remain available for non-browser operation:

```bash
bench --site development.localhost execute pridict.schema_intelligence.api.capture_and_persist
bench --site development.localhost execute pridict.schema_intelligence.api.list_snapshots
```

## Limitations

- Snapshot capture is explicit; no scheduler is introduced.
- Snapshot deletion and retention policy are not part of this milestone.
- The UI does not evaluate effective access for a specific user.
- The graph is intentionally bounded to 16 visible edges and does not provide pan, zoom, or layout
  editing.
- Initial response time scales with the size and number of private snapshot files.
- Raw metadata is intentionally not rendered in the browser.
