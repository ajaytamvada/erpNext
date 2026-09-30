# Pridict Process Intelligence Milestone 2 UAT Release

Date: September 30, 2026

Status: Deployed successfully to Azure UAT.

## Release identity

- Public URL: `https://pridict-demo.centralindia.cloudapp.azure.com`
- Source branch: `version-15`
- Source commit: `e1b937a86be754fd551c2927e756775b89a9ecea`
- Image: `pridict-erpnext:0.1.0-20260930-process-intelligence-uat1`
- Image ID: `sha256:3c29766cfea38a5d53c5259161618f97ea1ef681e80c7b906840e4e031615e0a`
- Image revision label: `e1b937a86be754fd551c2927e756775b89a9ecea`
- Release state: `/opt/erpnext/release-state/20260930T170136Z.env`
- Previous image: `pridict-erpnext:0.1.0-20260928-redesign-uat1`

## Recovery evidence

- Backup blob: `predeploy/2026/09/30/pridict-precutover-20260930-process-intelligence-uat1.tar.gz`
- Backup SHA-256: `d3ae778517adb270bdc746032c8cdb9d5b34582c50f880ab68df561ab2b61d19`
- Backup size: 9,796,216 bytes
- OS-disk snapshot: `erpnext-demo-vm-osdisk-pridict-predeploy-20260930-process-intelligence-uat1`
- Snapshot provisioning state: `Succeeded`
- Snapshot encryption: `EncryptionAtRestWithPlatformKey`
- Source archive: `release-candidates/2026/09/30/pridict-20260930-process-intelligence-uat1-source.tar.gz`
- Source SHA-256: `29012f8a670d90154fefeec7d9050e9f82c1acb6d5979fd01209821d0e3aa7cf`

## Release execution

- Retrieved the exact pushed commit through its immutable GitHub commit archive.
- Uploaded the source archive to private Blob Storage and downloaded it again for SHA-256 verification.
- Built and validated the immutable image on the UAT VM before cutover.
- Created an encrypted OS-disk snapshot before the application cutover.
- Enabled maintenance mode and disabled the scheduler before the fresh backup.
- Backed up the database, site configuration, public files, and private files.
- Uploaded the backup through the VM managed identity and downloaded it again for SHA-256 verification.
- Recreated application services with the new image, migrated the site, and cleared the cache.
- Re-enabled the scheduler and disabled maintenance mode after successful verification.

## Verification result

- All nine long-running services are running.
- All application containers use the target image.
- MariaDB is healthy.
- HTTPS login returned 200.
- Administrator authentication passed.
- Authenticated-session lookup passed.
- Pridict CSS and JavaScript asset requests passed.
- Frappe 15.120.1, ERPNext 15.121.2, and Pridict 0.1.0 are installed.
- Maintenance mode is off.
- The scheduler is enabled and `bench doctor` reported one online worker.
- The Process Intelligence API and service modules import successfully in the deployed backend.

## Acceptance boundary

Deployment verifies that the exact source revision built, migrated, started, authenticated, and loaded the Process Intelligence modules. Functional UAT of reconstruction against representative purchasing histories remains a separate acceptance activity.
