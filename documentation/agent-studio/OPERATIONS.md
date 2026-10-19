# Agent Studio: operator guide

How to set up, run and look after the Procurement Sourcing Agent on a Pridict site.
For the design and the reasons behind it, see `Agent-Studio-Explainer.pdf`.

## 1. Install or update

```bash
bench get-app ...            # or pull the latest pridict_app
bench setup requirements --python pridict   # installs langgraph
bench --site <site> migrate  # creates the DocTypes and seeds tools, policies and the agent
bench build --app pridict
```

`migrate` is safe to repeat. It updates the tool registry from code, never
overwrites policy settings an administrator changed, and always keeps
`submit_purchase_order` blocked for agents.

Runs and evaluations execute in background jobs, so a worker must be running
(`bench worker`, or the `worker` process in production supervisors). After a
migrate the worker first processes search-index jobs; the first agent run may
wait about a minute.

## 2. Connect the model

1. **Agent Studio > Models & Providers > Azure OpenAI > Edit.**
   Paste the API key into **API Key** and save. The key is stored encrypted and
   is never sent to the browser or written to run traces.
2. Click **Test connection**. The card should turn *Connected* with a latency.
3. On the `procurement-reasoning` configuration click **Send test prompt**.
4. Optional: set **Reasoning Effort** to `low` for faster, cheaper answers.
   gpt-5.x models reject custom temperatures; the gateway detects this and
   stops sending it automatically.
5. Add a second configuration and set it as **Fallback** if you want automatic
   failover to another deployment or provider.

## 3. Evaluate, then activate

The agent is seeded as **Draft**: administrators can test it, buyers cannot use it yet.

1. **Runs & Traces > Evaluation suite > Run with live model.** Eight scenarios run
   against temporary data that is rolled back afterwards (no site data changes).
   *Run offline check* does the same with a scripted model and needs no key.
2. When the live suite passes 8/8 for the current version, open
   **Agents > Edit agent** and set **Status** to *Active*. Activation is refused
   until the latest live evaluation of that version passes every scenario.
3. After changing instructions, tools or the model, raise **Version** and
   re-run the live suite. An active agent cannot change version without a new
   passing evaluation.

## 4. Who can do what

| Role | Can |
|---|---|
| System Manager | Everything, including providers, keys, evaluations and Draft agents |
| Purchase Manager | Use Active agents, view all runs, approve single- and dual-approval proposals |
| Purchase User | Start runs with Active agents and follow their own runs at `/app/agent-runs` (they see only their own) |
| Accounts Manager | Open the Approval Inbox and give the second approval for ₹5–25 lakh proposals |

The person who started a run cannot approve it (policy *Self-approval*).
Agents read data with the requester's own ERPNext permissions, and the draft RFQ
is created as the requester, so they never see or do more than that person can.

One exception, by design: when an item or supplier is missing, the assistant
creates it for the buyer after they confirm in chat, even if the buyer has no
right to create Items or Suppliers. Each such record gets a comment naming the
buyer and the conversation. Switch this off with the policy *Create missing
items and suppliers*; the agent then asks the buyer to add them by hand.

## 5. Policies

**Policies & Guardrails** lists every rule; click a rule to change it. Values are
in the **Parameters** JSON, for example:

| Policy | Parameters |
|---|---|
| Single approver limit | `{"max_value": 500000, "roles": ["Purchase Manager"]}` |
| Dual approval | `{"min_value": 500000, "max_value": 2500000, "roles": ["Purchase Manager", "Accounts Manager"]}` |
| Hard ceiling | `{"max_value": 2500000}` |
| Permitted warehouses | `{"warehouses": ["Stores - PRD"]}` (empty list = any the user may access) |
| Price variance tolerance | `{"tolerance_pct": 10, "days": 90}` |

Changes apply to the next run. The agent only quotes suppliers listed on the
item's **Supplier** table. If there are none, it asks the buyer which supplier to
use and adds it (creating the supplier first if it is new).

## 6. Day-to-day

- Buyers use the **Procurement Assistant** (`/app/procurement-assistant`, or *Ask the
  assistant* on the Procurement page). It is a chat: they see questions, cards and
  results, never steps or tools. Each conversation is one run, so administrators
  still see the full trace in **Runs & Traces**.
- **Waiting for buyer**: the agent asked a question; the requester answers in the
  assistant (or on the Runs page).
- **Awaiting approval**: approvers get an ERPNext notification; decide in the Approval Inbox
  or on the Agent Approval form. Rejection needs a reason.
- **Cancel run** is available on paused runs.
- Hourly housekeeping marks runs left *Running* by a crashed worker as *Failed*
  (after 2 hours) and closes questions and approvals nobody answered within 14 days.
- Each user can have at most 3 runs queued or running at once.

## 7. Troubleshooting

| Symptom | Check |
|---|---|
| Run stays *Queued* | Is a worker running? `bench doctor`, or look at `logs/worker.log` |
| "has no API key" | Enter the key on the LLM Provider record |
| "All model configurations failed" | Test connection on the provider; check the deployment name and API version |
| Page does not update live | Is `bench socketio` running? In Docker the container must resolve the site name |
| "You started this run, so you cannot approve it" | Approve as another user with the required role |
| Agent asks for a supplier | The item has no usable supplier; the buyer names one in chat, or add it to the item's Supplier table |
| "limit of N LLM calls" mid-conversation | Raise **Max Steps** on the agent (16 suits conversations that create an item and a supplier) |
| Run *Failed* with a step error | Open the run: the failed step and the error are shown in the trace |

## 8. Tests

```bash
bench --site <test-site> set-config allow_tests true
for m in test_graph test_agent_studio test_gateway test_tools test_runtime test_approvals test_evals test_assistant; do
  bench --site <test-site> run-tests --module pridict.agent_studio.$m
done
```

`test_tools`, `test_runtime` and `test_approvals` use ERPNext's standard test
records (`_Test Company`, `_Test Warehouse - _TC`), so run them on a test site.

## 9. Rebuilding the explainer PDF

```bash
cd documentation/agent-studio/build
python build_pdf.py --screens http://<site>:<port> <user> <password>   # recapture screenshots, then build
python build_pdf.py                                                     # rebuild from existing screenshots
```

Needs Chrome, `pip install playwright pillow`, and a running site with some runs to show.
