# Pridict Schema Intelligence Milestone 3 specification

## Status

Implementation started locally on 23 September 2026 using the approved governance defaults. The
backend, governance DocTypes, scheduler hook, protected APIs, Desk entry points, exports, and focused
unit coverage are present in the working tree. Frappe migration, full integration tests, and browser
verification remain pending because the local Docker/Frappe runtime was unavailable in the current
session. No Azure or UAT system was accessed or changed.

## Milestone objective

Turn the read-only extraction and browsing capabilities from Milestones 1 and 2 into a controlled
schema-change governance workflow.

Milestone 3 should help authorized operators answer:

- Which snapshot is the approved baseline?
- What changed since that baseline?
- Which changes are important or potentially breaking?
- Who reviewed a change and what was their decision?
- When should snapshots be captured and retained?

The milestone must preserve the existing extraction safety boundary. Schema governance data may be
created by Pridict, but extraction must remain read-only against source metadata and business data.

## Scope

### 1. Snapshot lifecycle

Add controlled lifecycle metadata for persisted snapshots:

- operator-defined label and optional note;
- pinned baseline designation;
- retained, archived, or deletion-eligible state;
- capture origin: manual or scheduled;
- creation actor and review status;
- safe deletion with explicit confirmation and audit evidence;
- configurable retention by count and age.

Deletion must never remove a pinned baseline, a snapshot referenced by an open review, or the only
complete snapshot unless the operator first resolves those dependencies.

Retention must be disabled by default. Enabling it requires an explicit System Manager action.

### 2. Scheduled capture

Provide a scheduler configuration that is disabled by default and supports:

- daily or weekly capture cadence;
- site-local execution time;
- complete-snapshot requirement;
- comparison against the pinned baseline or most recent complete snapshot;
- retention processing after a successful capture;
- structured success, incomplete, and failure status.

The scheduler must use the existing extraction service. It must not introduce a separate extraction
path or bypass completeness validation.

Concurrent capture attempts must be serialized with a site-scoped lock. A second attempt should exit
with an explicit already-running result rather than starting another extraction.

### 3. Change classification

Extend deterministic comparison with rule-based severity classification. No LLM or external AI
dependency is allowed.

Initial classifications:

- `critical`: removed DocType, removed field, changed field type, changed child-table target, or
  permission removal affecting create/read/write/submit/cancel;
- `warning`: newly required field, changed Link target, changed Dynamic Link selector, permission
  addition, or field-order change;
- `information`: added optional field, added DocType, label change, description change, or other
  non-breaking normalized property change.

Every classification must include a stable rule identifier, explanation, affected path, before value,
after value, and provenance when available. Operators may override review priority but must not alter
the deterministic underlying comparison result.

### 4. Review and acknowledgment

Add a review workflow for a comparison between a baseline and a later snapshot:

- statuses: `Open`, `Acknowledged`, `Approved`, and `Rejected`;
- reviewer, timestamps, and append-only comments;
- severity summary and unresolved finding count;
- links to affected DocTypes, fields, relationships, and permissions;
- protection against changing the referenced comparison inputs;
- explicit baseline promotion after approval.

Baseline promotion must be a separate confirmed action. Approving a review must not automatically
replace the current baseline.

Review records are Pridict governance records. They must not modify ERPNext transactions or metadata.

### 5. Notifications

Provide opt-in notification rules for completed scheduled comparisons:

- System Notification is the initial required channel;
- email may be supported only through the site's existing configured email account;
- recipients must be explicit users or roles;
- minimum severity threshold must be configurable;
- repeated unchanged captures must not generate change notifications;
- incomplete or failed captures must generate an operational warning without creating a successful
  comparison review.

No external webhook or third-party notification service is required in this milestone.

### 6. Scalable relationship exploration

Enhance the relationship view without loading or drawing the entire site graph at once:

- expand one or two relationship hops from a selected DocType;
- filter by Link, Dynamic Link, child table, and Table MultiSelect;
- direction filter for outgoing and incoming relationships;
- search within visible nodes;
- cap rendered nodes and edges with an explicit truncation message;
- provide a complete accessible list alongside the visual graph;
- export the selected subgraph as JSON and Mermaid text.

The graph remains a visualization of extracted metadata, not inferred business-process behavior.

### 7. Reports and exports

Provide authorized exports for:

- snapshot summary;
- full deterministic comparison;
- review summary;
- affected objects grouped by severity;
- selected relationship subgraph.

JSON is required. CSV is required for flat change findings. Mermaid text is required for relationship
subgraphs. Exported files must not include credentials or business records.

### 8. Future analysis contract

Define, but do not connect to an AI service, a bounded analysis payload containing:

- selected normalized schema objects;
- deterministic findings;
- provenance references;
- completeness and diagnostic state;
- explicit exclusions and size limits.

This contract exists only to prevent future AI work from receiving raw snapshots or business data by
default. No LLM calls, embeddings, vector database, or external transmission are included in
Milestone 3.

## Proposed data model

Use standard Pridict DocTypes for governance state and the existing private filesystem repository for
immutable snapshot payloads.

### Schema Intelligence Settings

Single DocType restricted to System Managers:

- scheduler enabled;
- cadence and local execution time;
- comparison target policy;
- retention enabled, maximum count, and maximum age;
- notification enabled, severity threshold, users, and roles;
- graph node and edge limits.

### Schema Snapshot Record

Governance index referencing an immutable snapshot file:

- snapshot ID and metadata hash;
- captured timestamp, versions, completeness, and counts;
- capture origin and actor;
- label, note, lifecycle state, and pinned-baseline flag;
- private file path or repository identifier;
- diagnostic summary.

The record must not duplicate preserved raw metadata into database fields.

### Schema Change Review

- baseline and candidate snapshot references;
- deterministic comparison hash;
- status, severity totals, reviewer, and timestamps;
- append-only review comments;
- baseline-promotion status;
- notification state.

### Schema Change Finding

Child rows or a bounded related representation containing:

- stable finding ID and rule ID;
- severity and category;
- affected DocType and field or relationship path;
- normalized before and after values;
- explanation and provenance references;
- acknowledgment state.

Large comparisons must not create unbounded database child tables without verified performance. If
the finding count exceeds the tested bound, persist the complete comparison privately and index only
the summary plus paginated findings needed by the UI.

## Module boundaries

Keep the existing Milestone 1 modules unchanged where possible. Add focused modules for:

- lifecycle policy and dependency checks;
- scheduler orchestration and locking;
- deterministic severity rules;
- review service and audit operations;
- notification selection and dispatch;
- relationship subgraph queries;
- export formatting;
- future analysis payload construction;
- API endpoints and tests.

UI code must call service APIs and must not implement retention, review transitions, or severity rules
in the browser.

## Authorization and safety

- All configuration, capture, deletion, review, baseline, and export operations require System
  Manager unless a narrower dedicated role is designed and explicitly approved.
- No endpoint may allow guest access.
- Snapshot payloads and exports remain private files.
- Deletion and baseline promotion require action-time confirmation in the UI.
- Review transitions must validate the current status server-side.
- Scheduled jobs must run under a clearly recorded system identity.
- Logs must contain snapshot IDs and diagnostic counts, not credentials, raw metadata, or business
  records.
- Extraction must continue to execute no discovered Server Script, controller method, or arbitrary
  metadata-provided code.
- No Azure or UAT deployment is part of implementation or verification unless separately approved.

## API outline

The exact method names may follow repository conventions, but the service contract should cover:

- get and update settings;
- list, label, pin, archive, and safely delete snapshot records;
- trigger manual capture;
- report scheduler status and last result;
- create or retrieve deterministic comparison reviews;
- list and filter findings;
- transition review status;
- promote an approved snapshot to baseline;
- export snapshots, comparisons, findings, and subgraphs;
- query bounded incoming and outgoing relationship neighborhoods.

Mutation endpoints must use POST and server-side authorization. Read endpoints must not reveal private
snapshot paths or raw metadata unnecessarily.

## Partial failure behavior

- Incomplete captures remain visible as failed operational attempts but cannot become baselines.
- A failed scheduled capture does not run retention or create a successful review.
- Notification failure does not invalidate a completed snapshot or comparison; it is recorded for
  retry.
- Export failure does not change review state.
- Baseline promotion is atomic and retains the previous baseline until the new assignment succeeds.
- Deletion failure leaves lifecycle references unchanged and reports the exact repository error.

## Testing requirements

### Unit tests

- lifecycle dependency rules and retention boundaries;
- scheduler configuration and site-scoped locking;
- deterministic severity classification;
- review state transitions and immutable comparison references;
- baseline promotion;
- notification deduplication and recipient selection;
- relationship neighborhood limits and filters;
- export stability and escaping;
- future analysis payload exclusions and size bounds;
- authorization for every endpoint;
- partial failures and retry behavior.

### Integration tests

Use disposable local Frappe/ERPNext sites to demonstrate:

- manual and scheduled capture use the same extraction path;
- unchanged snapshots do not create change notifications;
- a controlled Custom Field and Property Setter change creates classified findings;
- an approved candidate can be promoted to baseline;
- protected snapshots cannot be deleted;
- eligible snapshots are removed by an enabled retention policy;
- source metadata and business data remain unchanged by extraction;
- private files and governance records remain internally consistent after failures.

### Browser tests

Verify desktop and 390 by 844 mobile layouts in light and dark themes for:

- settings;
- lifecycle actions and confirmations;
- history timeline;
- review detail and finding filters;
- baseline promotion;
- relationship exploration;
- exports;
- loading, empty, incomplete, failure, and authorization states.

## Acceptance criteria

Milestone 3 is complete only when:

1. A System Manager can configure an opt-in schedule and retention policy.
2. Scheduled and manual captures produce the same normalized result and hash for unchanged metadata.
3. A deterministic comparison creates correctly classified findings.
4. Reviews preserve immutable snapshot references and valid audited state transitions.
5. Approved snapshots can be explicitly promoted to baseline.
6. Protected snapshots cannot be deleted and eligible snapshots can be removed safely.
7. Notifications are opt-in, deduplicated, authorized, and tested without external services.
8. Large relationship sets are explored through bounded, filtered subgraphs.
9. JSON, CSV, and Mermaid exports are deterministic and contain no business records or credentials.
10. Full unit, disposable-site integration, browser, and regression suites pass.
11. Read-only extraction evidence remains valid.
12. No Azure or UAT system is accessed or modified.

## Explicit non-goals

- No LLM, embedding, vector database, or external AI integration.
- No automatic ERPNext customization or schema repair.
- No execution of Server Scripts, controllers, workflows, or discovered code.
- No business transaction extraction or analytics.
- No automatic production deployment.
- No public or guest-accessible schema endpoint.
- No replacement for Frappe's permission engine or effective-user access evaluation.

## Recommended implementation order

1. Add governance DocTypes and migration-safe validation.
2. Index existing private snapshots without changing their payloads.
3. Implement lifecycle rules and explicit baseline management.
4. Add deterministic severity classification and review services.
5. Add scheduler locking, capture orchestration, and retention.
6. Add opt-in notifications and retry state.
7. Add bounded relationship exploration and exports.
8. Build the Milestone 3 frontend workflows.
9. Run disposable-site, browser, and full regression verification.
10. Save implementation documentation and handoff before deployment planning.

## Approved implementation decisions

The following product decisions were approved on 23 September 2026:

- use a dedicated `Schema Reviewer` role while retaining System Manager configuration authority;
- default retention to 90 days and 30 snapshots, deleting only when both limits are exceeded;
- require one reviewer, with final approval or rejection performed by someone other than the review creator;
- use System Notifications only for the initial release;
- cap relationship views at 100 nodes and 250 edges and indexed findings at 5,000 per review;
- audit snapshot label changes and keep review comments append-only;
- leave scheduled capture and retention disabled by default, with weekly capture as the recommended cadence.
