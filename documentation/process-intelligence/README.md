# Purchasing Process Intelligence — Milestones 1 and 2

Milestone 1 describes configured purchasing capabilities. Milestone 2 adds bounded, read-only reconstruction of explicit purchasing transaction evidence on an authorized disposable site. Neither milestone redesigns purchasing, changes workflows, recommends actions, creates agents, or deploys application changes.

## Architecture

- `schema_adapter.py` validates and narrows a real Schema Intelligence `SchemaSnapshot` to purchasing candidates and their structural relationships.
- `collection.py` reads Workflow, Assignment Rule, Notification, Client Script and Server Script configuration. Script bodies are replaced with SHA-256 hashes.
- `models.py`, `modeling.py`, `graph.py` and `reporting.py` define and render the configured/intended purchasing model.
- `transaction_models.py` defines the versioned transaction scope, events, evidence, correlations, instances and reconstruction result.
- `transaction_collection.py` performs bounded company/date extraction and reads only installed fields.
- `reconstruction.py` pseudonymizes identifiers, creates explicit-link correlations, preserves state evidence and identifies gaps.
- `reconstruction_graph.py` emits the directed actual-evidence graph, including referenced out-of-scope nodes.
- `reconstruction_reporting.py` renders the requested headings without inventing triggers, decisions or exception handling.
- `persistence.py` and `reconstruction_persistence.py` provide atomic, integrity-checked site-private storage.
- `service.py` is the application entry point; `api.py` exposes System Manager-only read APIs.

## Configured Process Usage

```python
from pridict.process_intelligence.service import analyze_purchasing, process_artifacts

model = analyze_purchasing()
artifacts = process_artifacts(model)
```

To reuse a persisted Schema Intelligence snapshot, pass `snapshot_id` to `analyze_purchasing`. To persist the process model, call `analyze_and_persist_purchasing`.

## Reconstruction Usage

```python
from pridict.process_intelligence.service import reconstruct_purchasing_transactions
from pridict.process_intelligence.transaction_models import TransactionScope

scope = TransactionScope("_Test Company", "2026-09-01", "2026-09-29")
result = reconstruct_purchasing_transactions(scope)
```

The company and inclusive ISO date range are mandatory. The per-DocType limit defaults to 5,000 and cannot exceed 5,000.

Whitelisted API methods require the `System Manager` role:

- `pridict.process_intelligence.api.discover_purchasing`
- `pridict.process_intelligence.api.get_process_model`
- `pridict.process_intelligence.api.list_process_models`
- `pridict.process_intelligence.api.reconstruct_purchasing`
- `pridict.process_intelligence.api.get_reconstruction`
- `pridict.process_intelligence.api.list_reconstructions`

## Evidence Semantics

- Permissions establish capability only; they do not establish actual responsibility or participation.
- Schema relationships remain structural references, not proven process sequence.
- Workflow conditions are recorded but not executed.
- Client and Server Scripts are hashed, not exposed or executed.
- Native document states remain separate; no fabricated cross-document lifecycle is created.
- Document `creation` is recorded only as `DOCUMENT_CREATED`.
- A current status is an observation; its transition time is not inferred.
- `modified` is never treated as an approval or completion timestamp.
- Version evidence is limited to changes in `docstatus`, `status` and `workflow_state`.
- Workflow Action creation time is retained but not treated as approval completion time.
- Only explicit parent, item-row, amendment, return and payment-allocation links create correlation edges.
- Duplicate, conflicting and circular explicit correlations are reported as quality gaps.
- Missing and out-of-scope references become gaps rather than fabricated transitions.
- Transaction document, row, company, user and evidence identifiers are pseudonymized with the SchemaSnapshot site hash.

## Outputs

Generated evidence is stored under `documentation/process-intelligence/artifacts/`:

- `purchasing-process-model.json`
- `purchasing-process-graph.json`
- `purchasing-process-report.txt`
- `purchasing-actual-reconstruction.json`
- `purchasing-actual-graph.json`
- `purchasing-actual-report.txt`

## Verified Local Result

On September 29, 2026, the disposable `development.localhost` scope used `_Test Company` and September 1–29, 2026. It found two Material Requests and one Purchase Order, producing three separate instances and no explicit cross-document edges. This is an honest finding from the available fixture data, not evidence that the installed product lacks those relationships.

The local unit suites contain 17 passing tests. The real-site integration suite contains three passing tests and verifies Frappe `15.120.1`, ERPNext `15.121.2`, repeated deterministic extraction, before/after read-only fingerprints and access restrictions.

## Current Limitations

- Full historical process mining, bottleneck metrics, approval duration and waiting time remain deferred.
- Free-text comments, SOP text and arbitrary scripts are not collected or interpreted.
- Explicit links prove correlation, not business purpose, responsibility or an obligatory sequence.
- The disposable site has too little linked purchasing history to validate real partial fulfillment, returns, amendments or payment allocation end to end; those cases are covered by focused unit fixtures.
- This is Process Intelligence Milestone 2, not completion of all Process Intelligence capabilities.
