# Automations: operator guide

How to set up, run and look after Automations (the Automation Builder) on a Pridict site.
For the design and the reasons behind it, see `Automation-Builder-Explainer.pdf` and
`AUTOMATION-BUILDER-TECHNICAL-DESIGN.md`.

## 1. Install or update

```bash
bench --site <site> migrate   # DocTypes, roles, automation user, settings, AI model configs
bench build --app pridict
```

`migrate` is safe to repeat. On each run it:

- creates the **Automation Manager** and **Automation Viewer** roles, and (once per site) gives
  Automation Manager to every enabled System Manager;
- creates the Run As user `automation@<site>` with **no roles**;
- creates the LLM Model Config `automation-architect` from `procurement-reasoning` (same
  deployment, medium reasoning) and sets it, and `procurement-reasoning` for AI steps, in
  Automation Settings if they are empty;
- **re-checks every active automation** against the updated site and pauses any whose steps no
  longer fit (for example a field an ERPNext update removed). The owner gets a notification with
  the reason.

### Workers and queues

Automation runs use the `automation` queue when it is configured, otherwise `long`:

```bash
bench set-config -gp workers '{"automation": {"timeout": 900}}'
bench worker --queue short,default,long,automation
```

`deployment/compose.yaml` already does both (one worker serves all queues). On a busy site,
run a separate worker with `--queue automation` so automations cannot delay other jobs.
The scheduler must be running: schedules, waits and approval timeouts are checked every minute,
and old runs are cleaned up daily.

## 2. Switch it on

Automations ship **switched off**. In **Automation Settings**:

| Setting | Meaning |
|---|---|
| Enable Automations | The feature switch. Off: nothing runs; the builder still works and shows a banner |
| Pause All Automations | Kill switch: stops starting new runs immediately (runs already going finish) |
| Default Run As | Who new automations run as (default `automation@<site>`) |
| AI Architect Model / AI Step Model | Models for building by chat and for AI steps |
| Max Chain Depth | How many automations may trigger each other in a row (default 3) |
| Pause After Consecutive Failures | Auto-pause threshold (default 5) |
| Site Max Emails per Day | Cap across all automations (default 1000) |
| Allowed hosts for HTTP steps | One host per line (`api.example.com`, `*.example.com`). Empty = HTTP steps cannot call anything |
| Keep completed / failed runs | Run history retention (30 / 90 days). Test runs are kept 7 days, except the ones that unlocked a version |

## 3. Give the automation user what it needs

Automations act **as their Run As user, with that user's permissions**. The builder lists what is
missing as **setup items** ("Run As user … has no read permission on Supplier"). Grant the
automation user only the roles its automations need, in **User > automation@<site> > Roles**.
An admin can only pick a Run As user whose roles they hold themselves.

Email steps need an outgoing **Email Account** (default, or chosen in the step). Inbound email
triggers need an Email Account with incoming enabled.

## 4. Building, testing, activating

1. **Automations > New Automation**: blank, or from a template (S1–S6).
2. Build in the **Build with AI** chat, on the canvas, or both. Each change is a new draft
   revision in **History**, with Restore.
3. **Test Run**. It does everything for real as the Run As user, then rolls it all back.
   Emails are shown, not sent; HTTP steps send only GETs marked *safe in tests* and otherwise show
   what they would send (or the sample response). At an Approval, Ask or Wait step the test stops
   and offers **Simulate** buttons; each choice replays the test from the start.
4. **Activate** appears once the current draft has passed a test. Any edit needs a new test.
   Activating freezes the draft as a numbered **Automation Version**; runs already going finish on
   the version they started with.
5. **Pause / Resume** from the builder or the list. **Run Now** runs an active automation by hand.

## 5. Triggers

| Trigger | Notes |
|---|---|
| Document event | `after_insert`, `on_update`, `on_submit`, `on_cancel`, `on_trash`, `on_change`, with an optional condition such as `doc.grand_total > 500000`. Starts after the save commits; a save that rolls back never starts a run |
| Schedule | Daily / weekly / monthly / hourly at a time, or a cron expression, in the site time zone. A missed slot after downtime fires once |
| Email received | Chosen Email Account; optional sender / subject filters. Steps see `trigger.email` (from, subject, body, attachments) |
| Webhook | Address and secret are created on activation and shown **once**. Callers POST JSON with header `X-Pridict-Signature: sha256=<HMAC-SHA256 of the body with the secret>`. Limits: 1 MB body, 120 calls a minute. **New address and secret** in the trigger panel replaces both |
| Manual | **Run Now**, optionally on a chosen document |

## 6. Waiting for people

- **Approval** steps create an **Agent Approval** for a role; anyone with that role may decide it.
  Optional expiry: the run then follows *expired*.
  **Known limit:** the Agent Approvals page and the Agent Approval document are only open to
  System, Purchase and Accounts Managers today. Use those roles for approvals, or give the
  approver role read/write on Agent Approval, until a dedicated approvals view for any role exists.
- **Ask** steps notify the people asked; they answer from the notification's Agent Run
  (**Answer** button) or from the builder.
- **Wait** steps resume by themselves at the set time.

A waiting run keeps its state in the database (it survives restarts and releases).

## 7. Outside systems and secrets

- Store API keys in **Automation Credential** (Bearer token, Basic, or a custom header). Secrets
  are encrypted, never shown to the AI and never written to run traces. A credential can be
  limited to certain hosts.
- HTTP steps only call allowed hosts, never private or local addresses, and do not follow
  redirects. Responses over 1 MB are refused.

## 8. Looking after it

- **Automations page**: active automations, runs and failure rate (24 h), runs waiting for people,
  paused automations, emails today, jobs queued.
- **Runs** tab in the builder (or **Agent Run** documents): every step with its output, the path on
  the canvas, errors.
- **Guardrails** notify the automation's owner: failed runs (with *stop and notify*), the hourly
  run limit being hit, automatic pause after repeated failures, pauses after system updates.
- Load (dev bench, 20 active automations): +0.01 ms on saves no automation watches, about +0.6 ms
  on saves that four automations watch; schedule dispatcher about 16 ms a minute.
  Re-measure with `bench --site <site> execute pridict.automation.loadtest.run`.

## 9. Troubleshooting

| Symptom | Check |
|---|---|
| Nothing runs | Automation Settings: enabled and not paused; automation Active; scheduler and worker running |
| "has no … permission" on a step | Give the Run As user the role (Section 3) |
| Emails not arriving | Outgoing Email Account; the daily caps; Email Queue |
| Webhook answers "Unknown webhook or bad signature" | Wrong address (rotated?) or the signature is not over the exact body bytes |
| Automation paused by itself | Its *Paused Reason*: repeated failures, or a system update broke a step |
| Architect replies "No AI model…" | AI Architect Model in Automation Settings, and the provider's API key |

## 10. Tests and evaluations

```bash
for m in test_spec test_engine test_triggers test_automation test_scenarios test_architect test_humans test_integrations; do
  bench --site <site> run-tests --module pridict.automation.$m
done
bench --site <site> execute pridict.automation.evals.run    # live AI architect eval (uses the model)
```

The live eval builds six scenarios with the real model inside a transaction that is rolled back.

## 11. Rebuilding the explainer PDF

```bash
python documentation/automation-builder/build/build_pdf.py
```
