# Run Pridict with Azure Codex

Open PowerShell and run:

```powershell
cd C:\Users\tjm06\Projects\ERPNext
.\deployment\start-azure-codex.ps1
```

If Azure sign-in expired, run `az login` first. Exit Codex with Ctrl+C. Each invocation starts a new conversation and reads the project handoff. This does not automatically import the desktop conversation.

The launcher uses GPT-5.6 Sol on Azure with medium reasoning and asks for user approval for actions requiring it. Azure charges for token usage independently of the ChatGPT subscription. Keys are obtained at startup and kept in process memory, not saved in this repository.

Connection tests passed on 16 September 2026. Startup model-metadata warnings are currently nonfatal. The installed executable is pinned to the tested desktop binary; if that file disappears after an update, the launcher falls back to Codex on PATH, which may be older.

## Spending alerts configured

Target: at most INR 5,000 monthly. Billing currency was verified as INR on 16 September 2026. The rg-codex budget is INR 4,000 to provide some headroom; actual-spend emails are enabled at INR 2,000, 3,200 and 4,000 for pavan@riditstack.com and suman@riditstack.com. This covers all deployments in rg-codex, including the existing GPT-5-Codex deployment. Alerts are delayed billing notifications, NOT a hard cutoff or a guarantee that total charges including taxes stay under INR 5,000.

The connection tests are complete and no paid session has been left running. The product implementation has not started.
