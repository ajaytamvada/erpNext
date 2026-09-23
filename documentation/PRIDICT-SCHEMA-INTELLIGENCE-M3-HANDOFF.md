# Pridict Schema Intelligence Milestone 3 handoff

## Status

Milestone 3 was implemented and locally validated on 23 September 2026. No Azure resource or UAT site
has yet been changed for this milestone. Local verification passed and the user separately authorized
the UAT deployment on 23 September 2026.

## Delivered

- `Schema Intelligence Settings` Single DocType with opt-in weekly or daily scheduling, retention,
  System Notification recipients and safety limits.
- `Schema Snapshot Record` governance index around existing immutable private snapshot JSON files.
- `Schema Change Review`, bounded `Schema Change Finding` rows and append-only `Schema Review Comment`
  audit entries.
- Dedicated `Schema Reviewer` role, while System Managers retain capture, settings, lifecycle,
  deletion and baseline authority.
- Deterministic critical, warning and information classification with stable finding and comparison
  hashes.
- Explicit review transitions: Open, Acknowledged, Approved and Rejected. Final decisions cannot be
  made by the review creator.
- Separate confirmed baseline promotion. Replacing an existing baseline requires an approved review.
- Safe deletion protections for baselines, open-review references and the only complete snapshot.
- Retention defaults of 90 days and 30 snapshots. A snapshot is eligible only after exceeding both
  limits; retention is disabled by default.
- Hourly scheduler hook that evaluates the configured site-local daily or weekly cadence, serializes
  captures with a site lock, records incomplete attempts and runs retention only after success.
- Opt-in, deduplicated System Notifications with retry state. A dedicated notification type is marked
  as in-app only, so user email preferences cannot turn these events into email. External webhooks
  remain out of scope.
- One- or two-hop relationship exploration capped by default at 100 nodes and 250 edges.
- Deterministic JSON snapshot/comparison/review exports, CSV findings, Mermaid relationship exports,
  and a bounded future-analysis payload that excludes raw metadata, credentials and business records.
- Desk actions for settings, snapshot management, review creation, review transitions, baseline
  promotion, notification retry and exports.

## Verification completed

- Python compilation passed for the complete Pridict package.
- All new DocType JSON files parsed successfully.
- JavaScript syntax checks passed for the Schema Intelligence page and governance form scripts.
- Sixteen executable non-Frappe unit tests passed, including deterministic classification and bounded
  relationship exploration.
- A direct pure-Python smoke test confirmed stable comparison hashes and graph limits.
- `git diff --check` passed.

## Local Frappe verification completed

- Docker Desktop and the Linux engine were restored and the development compose stack started.
- `bench --site development.localhost migrate` completed and created the governance DocTypes and role.
- The complete Pridict suite passes with 35 tests successful and four environment-profile tests skipped.
- The production Pridict asset build completed successfully.
- The local login endpoint returns HTTP 200.
- A real manual capture exposed and verified a fix for timezone-aware ISO timestamps being inserted into
  Frappe Datetime columns. End-to-end capture now succeeds with zero errors.
- Three immutable snapshot files left by failed capture requests were indexed successfully.

UAT remains the next validation environment for full operational review workflows, scheduled capture,
notification delivery and responsive light/dark browser acceptance.

## Approved defaults

- Review access: dedicated `Schema Reviewer` role.
- Approval: one reviewer, different from the review creator.
- Retention: 90 days and 30 snapshots, applied only when both thresholds are exceeded.
- Notifications: System Notifications only.
- Relationship limits: 100 nodes and 250 edges.
- Indexed findings: 5,000 per review, with the complete deterministic comparison retained privately.
- Audit: snapshot label changes use standard document history; review comments are append-only.
- Scheduler: disabled by default; weekly at 02:00 site-local time when enabled.

## Next step

Build an immutable image from the validated commit, create fresh verified rollback artifacts, deploy it
to the existing Azure UAT VM with the guarded release script, and complete post-release verification.
