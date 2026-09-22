# Pridict Schema Intelligence — Milestone 1

## Status

Design recorded on 22 September 2026 before implementation. This milestone is a backend-only,
read-only metadata extraction foundation. It does not change the Pridict UI, ERPNext workflows,
business documents, permissions, or deployment configuration.

## Verified target

- Frappe `15.120.1`, source revision `9f8ae9cd25b6735be345da6cc12e9f5a96050c68`
- ERPNext `15.121.2`, source revision `df8b7f9648c2ec4da12db8c4022edc8dd1018c6b`
- Pridict `0.1.0`, repository revision `ee2072d20358b1f2287250f9e74b1a5e65f39f91`
- Local site: `development.localhost`, with tests enabled

## Verified Frappe metadata behavior

The implementation is based on the installed Frappe source, not public documentation or assumed
ERPNext schemas.

- `frappe.get_meta()` delegates to `frappe.model.meta.get_meta()` in
  `apps/frappe/frappe/__init__.py:1352`.
- `frappe.model.meta.get_meta()` reads and writes the Redis `doctype_meta` hash even when the caller
  passes `cached=False`; the flag bypasses the cache read but not the cache write. See
  `apps/frappe/frappe/model/meta.py:66`.
- `Meta.process()` merges Custom Fields, applies Property Setters, initializes field caches, sorts
  fields, resolves valid database columns, replaces standard permissions with Custom DocPerm rows
  when present, adds custom links/actions/states, and performs a large-table heuristic. See
  `apps/frappe/frappe/model/meta.py:138`.
- `Meta.add_custom_fields()` loads `Custom Field` rows ordered by `idx` and marks them with
  `is_custom_field=1`. See `apps/frappe/frappe/model/meta.py:357`.
- `Meta.apply_property_setters()` applies DocType, DocField, DocType Link, DocType Action, and
  DocType State overrides. See `apps/frappe/frappe/model/meta.py:376`.
- `Meta.set_custom_permissions()` replaces standard DocPerm rows with Custom DocPerm rows when any
  exist for the DocType. See `apps/frappe/frappe/model/meta.py:548`.
- `Meta.check_if_large_table()` can query each business table's approximate count and most recent
  `modified` value. The extractor overrides only this derived UI heuristic to prevent business-table
  reads. See `apps/frappe/frappe/model/meta.py:450`.
- Frappe validates Dynamic Link selectors as a `Link` to `DocType` or a `Select` field. See
  `apps/frappe/frappe/core/doctype/doctype/doctype.py:1335`.
- Frappe requires Table and Table MultiSelect options to identify child DocTypes; Table MultiSelect
  child DocTypes must contain at least one Link field. See
  `apps/frappe/frappe/core/doctype/doctype/doctype.py:1544`.

The extractor therefore uses a `Meta` subclass whose large-table check is disabled. It does not call
`frappe.get_meta()` for target DocTypes, does not load target documents, and does not import or invoke
their controllers. Metadata-table reads can still populate framework-level metadata caches needed by
Frappe's database query layer. Those cache entries are non-authoritative and are not included in a
snapshot or its hash.

## Module boundaries

- `models.py`: immutable canonical models, validation, and serialization.
- `normalization.py`: explicit conversion of Frappe values to canonical JSON values.
- `relationships.py`: Link, child-table, Dynamic Link, and Table MultiSelect resolution.
- `extraction.py`: source adapter contract, Frappe adapter, orchestration, and diagnostics.
- `snapshots.py`: snapshot assembly, stable ordering, semantic hashing, and completeness rules.
- `persistence.py`: repository contract plus memory and local-filesystem implementations.
- `comparison.py`: deterministic structural comparison.
- `service.py`: application service independent of transport.
- `api.py`: authorized Frappe endpoints and operator-callable functions.

Extraction and persistence are separate calls. Capturing a snapshot never persists it implicitly.

## Canonical model and provenance

Every normalized DocType, field, relationship, and permission contains one or more provenance
references. A reference identifies a preserved raw metadata section and a stable JSON-style path,
for example `doctypes/Sales Order/effective/fields/items` or
`doctypes/Sales Order/property_setters/<row-name>`.

The raw section preserves:

- the base DocType row and standard child metadata;
- Custom Field rows;
- Property Setter rows;
- Custom DocPerm rows;
- custom DocType Link, Action, and State rows;
- the effective metadata used by normalization.

Missing optional properties remain absent or `null`; false, zero, and empty values are not converted
to missing values.

## Relationship rules

- `LINK`: `options` is the static target DocType. Missing targets produce an error diagnostic.
- `CHILD_TABLE`: `Table` fields point to a child DocType. A missing or non-child target is an error.
- `DYNAMIC_LINK`: `options` is the selector field name. The relationship records the selector but no
  guessed static target. A `Link` selector must target `DocType`; a `Select` selector contributes only
  explicitly listed, installed DocType options as discoverable targets.
- `TABLE_MULTISELECT`: represented explicitly as a child-table relationship. Its child DocType and
  Link fields are recorded; missing Link fields or invalid targets produce diagnostics.

Single, child, virtual, and custom DocTypes remain in discovery and are identified by explicit flags.
Virtual DocTypes are metadata-only; their controllers and data providers are never loaded.

## Canonical serialization and hashing

Canonical JSON uses UTF-8, sorted object keys, compact separators, and stable list ordering where
order is not semantically meaningful. Field order remains the effective `idx` order.

Dates, times, decimals, bytes, UUIDs, paths, enums, tuples, and sets receive explicit tagged JSON
representations. Unknown non-JSON-native values cause a normalization diagnostic instead of being
silently discarded.

The semantic `metadata_hash` includes normalized DocTypes, fields, relationships, permissions,
provenance source classifications, and the schema-format version. It excludes `snapshot_id`,
`captured_at`, the site identifier hash, diagnostic timestamps, formatting, and raw audit columns such
as row creation/modification timestamps and owners. Framework/application versions remain snapshot
attributes but are not treated as schema changes by the comparison utility.

The site identifier is SHA-256 hashed only to avoid storing it in plain text. This is pseudonymization,
not secrecy; a known or guessable site name can still be matched to its hash.

## Completeness and failures

A snapshot is `complete` only when discovery succeeds and no error-severity diagnostic occurs during
raw capture, effective metadata construction, or normalization. Relationship defects found in fully
read metadata are warnings about the source schema rather than extraction failures. Warnings do not
make a snapshot incomplete. Incomplete snapshots may be persisted for diagnosis but cannot be marked
or treated as successful baselines by the service.

Each diagnostic includes severity, stable code, processing stage, message, and optional DocType,
field, and structured details.

## Persistence and API

The repository interface supports save, load, list, and baseline-safe save operations. The in-memory
repository is used by unit tests. The filesystem repository writes canonical JSON atomically beneath a
configured directory and validates snapshots when loading them. No database or external service is
introduced.

Frappe endpoints require the `System Manager` role and are not guest accessible. The service layer is
also callable with `bench --site <site> execute ...`. Endpoint authorization is not presented as a
substitute for filesystem permissions or operating-system access controls.

## Unsupported in Milestone 1

- Effective access decisions for a specific user, document, share, user permission, workflow state,
  or permission hook.
- Executing or interpreting Server Scripts, controller methods, client scripts, `depends_on`
  expressions, or arbitrary metadata-provided Python/JavaScript.
- Reading Dynamic Link target values from business tables.
- Database schema introspection beyond Frappe's metadata-column validation.
- UI pages, scheduled captures, remote storage, AI analysis, or Azure/UAT operation.
