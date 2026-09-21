# Pridict rollback runbook

Release state files are stored root-only in `/opt/erpnext/release-state`. Each
file records the previous and target image plus the verified Azure snapshot and
off-VM backup identifiers used for that release.

## Failed before Pridict installation

If `bench --site "$SITE_NAME" list-apps` does not include `pridict`, set
`ERPNEXT_IMAGE` in `/opt/erpnext/.env` to the recorded `PREVIOUS_IMAGE`, then run:

```bash
cd /opt/erpnext
docker compose up -d
docker compose exec -T backend bench --site "$SITE_NAME" enable-scheduler
docker compose exec -T backend bench --site "$SITE_NAME" set-maintenance-mode off
./verify.sh
```

## Failed after Pridict installation

Do not switch back to the stock image while `pridict` remains in the site's
installed-app list. That would leave the database referencing an app absent from
the image. Keep maintenance mode enabled and use one of these reviewed paths:

1. Fix forward with another versioned Pridict image, then rerun migration and
   verification.
2. Restore the recorded Frappe database/files backup to a clean pre-release
   site and verify it before routing traffic.
3. Restore the recorded Azure OS-disk snapshot as a replacement VM/disk after
   confirming the snapshot name and target resource IDs.

Never run `docker compose down -v`; the named volumes contain the live database
and site files. Never overwrite the current OS disk without a second-person
review of the snapshot and target IDs.
