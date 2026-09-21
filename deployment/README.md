# Pridict Azure UAT demo

This deployment runs ERPNext 15.121.2 on an Ubuntu 24.04 VM. The current live
deployment uses the versioned Pridict image. The Pridict release path builds a
versioned derivative with `deployment/Dockerfile.pridict`; it does not replace
ERPNext application code or use a mutable `latest` tag.

- Resource group: `rg-erpnext`
- VM: `erpnext-demo-vm`
- Region: Central India
- Size: `Standard_B2als_v2` (2 vCPU, 4 GiB RAM)
- Disk: 32 GiB Standard SSD; Docker named volumes hold site files and database
- URL: https://pridict-demo.centralindia.cloudapp.azure.com
- Daily startup: 07:00 India time (01:30 UTC), using `erpnext-demo-auto-start`
- Daily shutdown: 23:00 India time (17:30 UTC)
- Server files: `/opt/erpnext`
- Only HTTP/HTTPS are allowed inbound; administration uses Azure Run Command

`PUBLIC_HOSTNAME` in the server `.env` is the public address used for HTTPS and
verification. `SITE_NAME` remains the original internal Frappe site identifier;
do not rename the site directory or database to change the public URL. Caddy
serves the public hostname, Nginx routes to `SITE_NAME`, and the site's
`host_name` setting contains the public HTTPS URL. The Azure public IP DNS label
is `pridict-demo`; the old public hostname is no longer the supported address.

## Start and stop

Use the Azure portal's Start action on the VM, or:

```powershell
az vm start --resource-group rg-erpnext --name erpnext-demo-vm
az vm deallocate --resource-group rg-erpnext --name erpnext-demo-vm
```

Deallocation stops VM compute billing. The disk and public IP remain billable.
The daily schedule starts the VM again at 07:00, even after a manual stop.
To keep it off for several days, disable the `erpnext-demo-auto-start` Logic App
in Azure as well. `auto-start.json` records the workflow definition in a disabled
state for safe provisioning; the deployed workflow is enabled after its managed
identity receives the VM-scoped Desktop Virtualization Power On Contributor role.
At deployment time, the public Linux compute rate was USD 0.0246/hour, excluding
disk, public IP, bandwidth, taxes and account-specific credits/discounts.

## Operations

From Azure portal > VM > Run command > RunShellScript:

```bash
cd /opt/erpnext
docker compose ps
docker compose logs --tail 50 backend frontend worker scheduler proxy
```

`bootstrap.sh` installs Docker and 2 GiB swap. `install.sh` generates credentials
on first run and initializes the site. Compose uses Caddy for HTTPS and separate
ERPNext backend, frontend, worker, scheduler and websocket services, plus
MariaDB and Redis. Credentials live in root-readable `/opt/erpnext/.env`.
Local credential and SSH key files belong in `.deployment-private/`, ignored
by Git. Do not commit credentials or publish `.env`.

Named volumes survive container recreation and VM shutdown. Deleting the VM's
disk or running `docker compose down -v` destroys the stored demo data.
This is a single-VM demo without high availability. Before the Pridict release,
a full Frappe backup was copied to private Azure Blob Storage and an encrypted
OS-disk snapshot was created. See `PRIDICT-HANDOFF.md` for the audited identifiers.

## Pridict release

Build a versioned image from the repository root:

```bash
./deployment/build-pridict-image.sh pridict-erpnext:20260916-rc1
```

Copy the image to the VM through an approved image distribution method. During
the scheduled cutover, set the required approval, backup and snapshot variables,
then run `release-pridict.sh` with that exact immutable tag. The script records
release state, enables maintenance mode, installs/migrates Pridict idempotently,
recreates application services and runs post-release verification. It refuses
`latest` tags and leaves maintenance mode enabled on failure.

Review `ROLLBACK.md` before cutover. A pre-Pridict rollback after app installation
requires the verified database/files backup or OS-disk snapshot; switching only
the container image is not a safe rollback.

The old Azure Container Apps workflow must remain disabled after migration.
The VM uses the pinned official image; repository pushes do not redeploy it.

## Verification performed

The live deployment passed public HTTPS access, Administrator login,
authenticated-session lookup, and login CSS/JavaScript asset checks. All nine
long-running containers were running, MariaDB was healthy, and `bench doctor`
reported one online worker with no queued jobs at verification time.
`verify.sh` repeats these checks without printing credentials.

On first login, complete ERPNext's setup wizard with your demo company details.
The installation does not invent company, accounting, or personal information.
