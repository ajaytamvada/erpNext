# Pridict Product-Wide Redesign UAT Release

Date: September 28, 2026

Status: Deployed successfully to Azure UAT. Visual and functional acceptance remain pending.

## Release identity

- Public URL: `https://pridict-demo.centralindia.cloudapp.azure.com`
- Source branch: `version-15`
- Source commit: `dcae44511595609a563eb7c757a0cecd59c49f67`
- Image: `pridict-erpnext:0.1.0-20260928-redesign-uat1`
- Image ID: `sha256:6404c29396c351573f23f4a96f5bcf569efc3d39a12ee7f81508661c729d12a0`
- Image revision label: `dcae44511595609a563eb7c757a0cecd59c49f67`
- Release state: `/opt/erpnext/release-state/20260928T204935Z.env`
- Previous image: `pridict-erpnext:0.1.0-20260923-m3-rc1`

## Recovery evidence

- Backup blob: `predeploy/2026/09/28/pridict-precutover-20260928-redesign-uat1.tar.gz`
- Backup SHA-256: `9331a78c0b4fe25c0aee62eea9b3ca1648dccd26b828b83e44a08478497cf6e1`
- Backup size: 9,768,919 bytes
- OS-disk snapshot: `erpnext-demo-vm-osdisk-pridict-predeploy-20260928-redesign-uat1`
- Snapshot provisioning state: `Succeeded`
- Source archive: `release-candidates/2026/09/28/pridict-20260928-redesign-uat1-source.tar.gz`
- Source SHA-256: `d5fab9cf1d336530a09a6d3ef535b648fc7359b45788880b4d1dc07ffa18a6b1`

## Release execution

- Built the immutable image on the UAT VM from the pushed commit.
- Validated the Pridict app and compiled asset manifest inside the image before cutover.
- Enabled maintenance mode and disabled the scheduler before the fresh backup.
- Backed up the database, site configuration, public files, and private files.
- Uploaded the backup through the VM managed identity and downloaded it again for SHA-256 verification.
- Installed the release compose and verification scripts from the exact source revision.
- Recreated application services with the new image.
- Ran the Frappe migration and cleared site cache.
- Re-enabled the scheduler and disabled maintenance mode after successful verification.

## Verification result

- All nine services are running.
- MariaDB reported healthy during release verification.
- HTTPS login returned 200.
- Administrator authentication passed.
- Authenticated-session lookup passed.
- Pridict CSS and JavaScript asset requests passed.
- Frappe 15.120.1, ERPNext 15.121.2, and Pridict 0.1.0 are installed.
- Maintenance mode is `0`.
- Scheduler pause state is `0`.
- `bench doctor` reported one online worker.

## Acceptance boundary

Deployment proves that the exact source revision built, migrated, started, authenticated, and served its assets. It does not prove that every redesigned route is visually correct or that every business workflow remains functional.

The UAT team must complete `deployment/PRIDICT-REDESIGN-RUNTIME-VERIFICATION-MATRIX.md`. Record failures with the exact route, role, document state, theme, viewport, and action so corrections remain targeted.
