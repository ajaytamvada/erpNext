# Pridict Schema Intelligence Milestone 1 handoff

## Completion status

Milestone 1 was implemented and verified locally on 22 September 2026. No Azure resources or UAT
site were accessed or changed. The existing Pridict UI and business workflows were not modified.

## Implementation

The backend feature is located at `pridict_app/pridict/schema_intelligence` and is divided into:

- canonical models and validation;
- explicit non-JSON value normalization;
- Frappe metadata extraction;
- relationship resolution;
- deterministic snapshot construction and hashing;
- in-memory and atomic filesystem persistence;
- structural snapshot comparison;
- authorized API, service, and trusted operator entry points;
- unit and disposable-site integration tests.

The architecture and verified Frappe source behavior are recorded in
`documentation/PRIDICT-SCHEMA-INTELLIGENCE-M1.md`.

## Verified environment

- Frappe `15.120.1`, revision `9f8ae9cd25b6735be345da6cc12e9f5a96050c68`
- ERPNext `15.121.2`, revision `df8b7f9648c2ec4da12db8c4022edc8dd1018c6b`
- Pridict `0.1.0`, starting revision `ee2072d20358b1f2287250f9e74b1a5e65f39f91`
- Docker Desktop `4.90.0`, Engine `29.7.2`
- Disposable sites: `schema-clean.localhost` and `schema-custom.localhost`

Frappe emitted its existing warning that MariaDB `11.8` is newer than its currently tested `10.8`
range. The feature and its integration tests passed on the installed version.

## Verified metadata behavior

- Effective metadata is built by Frappe's `Meta.process()` pipeline.
- Custom Fields are appended and marked with `is_custom_field`.
- Property Setters override effective DocType and field values.
- Custom DocPerm rows replace standard DocPerm rows when present.
- `frappe.get_meta()` writes the resulting Meta object to Redis even with `cached=False`.
- The extractor instantiates a dedicated `Meta` subclass instead and disables only the
  `check_if_large_table()` heuristic, preventing business-table count and latest-modified reads.
- Target document controllers, Server Scripts, and metadata-provided code are not executed.

## Test results

Focused unit suite:

```text
14 tests passed
```

Clean disposable-site integration suite:

```text
3 applicable tests passed; 1 customized-profile test skipped
```

Customized disposable-site integration suite:

```text
1 applicable customization test passed; 3 clean-profile tests skipped
```

Full Pridict application suite on `development.localhost`:

```text
30 tests passed; 4 profile-specific tests skipped
```

The existing HTML/CSS parser emitted two CSS Level 2.1 compatibility messages for existing UI CSS;
they did not fail tests and are unrelated to Schema Intelligence.

## Read-only evidence

The clean-site integration test wraps the active Frappe database connection with a write guard that
rejects SQL beginning with insert, update, delete, replace, alter, create, drop, truncate, rename,
grant, revoke, or call. A complete 776-DocType extraction succeeded while the guard was active.

The test also hashes complete rows from DocType, DocField, DocPerm, Custom Field, Property Setter, and
Custom DocPerm before and after extraction. The fingerprints were identical. Target document
controllers are not loaded, and the disabled large-table heuristic prevents reads from business
tables. Framework metadata-cache activity is documented separately and is not persisted as source
metadata or included in snapshot hashes.

## Generated evidence

The finalized clean scan contained 776 DocTypes and 2,795 relationships. It completed successfully
with three warnings for installed metadata that references unavailable or non-DocType options:

- `Payment Gateway Account.payment_gateway` references the unavailable `Payment Gateway` DocType.
- `Journal Entry Account.reference_name` has Select values for modules not installed on this site.
- `Workspace Shortcut.link_to` has the non-DocType Select value `URL`.

Generated files:

- `documentation/schema-intelligence/examples/sales-order-schema.json`
- `documentation/schema-intelligence/examples/sales-order-relationships.mmd`
- `documentation/schema-intelligence/examples/controlled-customization-diff.json`

The Sales Order example contains 159 effective fields and 39 outbound relationships. The controlled
customization added `Customer.custom_pridict_schema_tier`, changed the effective label of
`Customer.customer_name`, changed field ordering, and changed the semantic metadata hash. Repeating
an unchanged extraction produced the same hash.

## Operator invocation

Capture without persistence:

```bash
bench --site <site> execute pridict.schema_intelligence.api.capture_summary
```

Capture and persist a complete snapshot:

```bash
bench --site <site> execute pridict.schema_intelligence.api.capture_and_persist
```

Retrieve or compare persisted snapshots:

```bash
bench --site <site> execute pridict.schema_intelligence.api.get_snapshot \
  --kwargs "{'snapshot_id': '<snapshot-id>'}"

bench --site <site> execute pridict.schema_intelligence.api.compare_snapshots \
  --kwargs "{'before_snapshot_id': '<before-id>', 'after_snapshot_id': '<after-id>'}"
```

Snapshots are stored under
`sites/<site>/private/files/pridict-schema-intelligence`. Incomplete snapshots are rejected by default
when persistence is requested. Callers must explicitly opt into diagnostic persistence of incomplete
snapshots.

## Limitations

- Permission rows are metadata only, not an effective-user access calculation.
- Dynamic Link targets are not inferred from business records.
- Server Scripts, controller methods, hooks, and client expressions are not evaluated.
- Metadata quality warnings do not make a fully completed scan incomplete.
- Snapshot files contain detailed schema metadata and must remain protected as private operational
  artifacts.
- No frontend has been added; a Schema Intelligence workspace is a separate milestone.

## Remaining blockers

There are no known blockers for Milestone 1. Deployment remains intentionally out of scope and still
requires separate authorization under the existing Pridict release handoff.
