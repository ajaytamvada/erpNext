# Pridict Agent Studio and Procurement Assistant UAT Release

Date: October 19, 2026

Status: Deployed successfully to Azure UAT.

## Release identity

- Public URL: `https://pridict-demo.centralindia.cloudapp.azure.com`
- Assistant: `https://pridict-demo.centralindia.cloudapp.azure.com/app/procurement-assistant`
- Source branch: `version-15`
- Source commit: `58ca8b8921dc44eacda4e995a9e40a922aa29346`
- Image: `pridict-erpnext:0.1.0-20261019-agent-studio-uat1`
- Image ID: `sha256:af383c887d3bac66e74ecc6d4843d203edfd0366381fa99bf193fdb78d47b8e1`
- Image revision label: `58ca8b8921dc44eacda4e995a9e40a922aa29346`
- Release state: `/opt/erpnext/release-state/20261019T151146Z.env`
- Previous image: `pridict-erpnext:0.1.0-20261012-decision-intelligence-fix2`

## Recovery evidence

- Backup blob: `predeploy/2026/10/19/pridict-precutover-20261019-agent-studio-uat1.tar.gz`
- Backup SHA-256: `38404dcd79dc96a3e470f0f53f32bbc1f081237e64dde3501d1384b79854f05b`
- Backup size: 9,793,563 bytes
- OS-disk snapshot: `erpnext-demo-vm-osdisk-pridict-predeploy-20261019-agent-studio-uat1` (Central India)
- Snapshot provisioning state: `Succeeded`
- Snapshot encryption: `EncryptionAtRestWithPlatformKey`
- Source archive: `release-candidates/2026/10/19/pridict-20261019-agent-studio-uat1-source.tar.gz`
- Source SHA-256: `4d08c47cd29d9613697c8ab40ff848b9ba2243be27fe337bbb03e079997b1136`

## Contents

First UAT release of Agent Studio: model gateway, read and write tools under user
permissions, the LangGraph procurement-sourcing workflow with approvals and draft
RFQs, the evaluation suite, and the conversational Procurement Assistant (questions
about buying and stock, sourcing from chat, draft Material Requests, creating missing
items and suppliers after confirmation). The image now installs LangGraph explicitly
(`Dockerfile.pridict`), constrained to the versions already in the base image.

## Verification result

- All nine long-running services are running; all application containers use the target image.
- Agent Studio modules and LangGraph import in the deployed backend.
- Both agents are seeded (Procurement Assistant, Procurement Sourcing Agent; status Draft).
- The Assistant Conversation table exists.
- Maintenance mode is off; the scheduler is enabled and one worker is online
  (queues `long,default,short`, which the assistant uses).
- Public HTTPS returned 200.

## Before users can use the assistant

- Create the LLM Provider and LLM Model Config on UAT and enter the API key there
  (keys are encrypted per site and do not carry over from development).
- Set that model on both agents. Agents are Draft, so only administrators can use them
  until activated; activating the sourcing agent requires a passing Live evaluation.

## Notes

- The resource group is in West US 2 but the VM, disk and snapshots are in Central
  India: create snapshots with `-l centralindia`.
