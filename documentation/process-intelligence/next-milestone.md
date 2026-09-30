# Proposed Next Milestone: Validated Historical Reconstruction

This milestone is design-only and must not be implemented until approved.

## Objective

Validate transaction reconstruction against a purpose-built disposable purchasing history, then add metrics only where event semantics are explicit and auditable. Keep configured intent, observed behavior and analyst inference separate.

## Required Test History

- One source item feeding multiple target documents.
- Multiple source items and documents feeding one target document.
- Partial, full and over-allocation across item-level links.
- Purchase returns and return-against chains.
- Cancellation followed by amendment, preserving both identities.
- Purchase Invoice links through Purchase Order and Purchase Receipt rows.
- Payment Entry allocations across partial and multiple invoices.
- Workflow actions, rejection paths and resubmission where a configured Workflow exists.
- Missing, deleted and out-of-scope references.

Fixture creation must remain separate from extraction. The extractor must run only after the fixture transaction is committed, and before/after fingerprints must prove that reconstruction made no changes.

## Event Semantics

- Treat document creation only as a creation event.
- Treat Version creation as the audit timestamp for the recorded field change, not as proof of business completion.
- Treat Workflow Action creation as the record timestamp, not automatically as approval duration or completion.
- Use explicit submission, cancellation, return, amendment and allocation evidence where available.
- Do not use `modified` as approval, receipt, invoice or completion time.
- Record conflicting timestamps or state histories rather than selecting a convenient value.

## Correlation Validation

- Validate every edge against the installed child-table field contract.
- Preserve source and target row identities separately from parent document identities.
- Verify quantity and amount units before aggregation.
- Keep out-of-scope endpoints as pseudonymous graph nodes with gap records.
- Detect duplicate, conflicting and circular references.
- Confirm that connected components are useful analytical groupings without describing them as proven end-to-end business processes.

## Metrics Gate

Cycle time, waiting time, approval time, handoffs, rework, exception rates and bottleneck candidates remain `DATA_NOT_AVAILABLE` until each metric has:

- an explicit start event;
- an explicit end event;
- documented exclusions;
- a correlation-quality threshold;
- a confidence reason;
- tests covering cancellations, returns, amendments and partial fulfillment.

## Deferred Product Decisions

- Retention and deletion policy for reconstruction snapshots.
- Whether authorized analysts may opt into selected comments or SOP evidence.
- Whether process-instance grouping should remain connected-component based or use domain-specific correlation policies.
- Which roles, beyond System Manager, may run or view reconstructions.
- Whether validated metrics should be persisted or calculated on demand.

No recommendations, agent candidates, workflow changes or autonomous actions should be added in this milestone.
