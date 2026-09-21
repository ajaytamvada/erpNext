#!/usr/bin/env bash
set -euo pipefail

cd /opt/erpnext
umask 077

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <versioned-pridict-image>" >&2
  exit 2
fi

target_image="$1"
case "$target_image" in
  *:latest)
    echo "Refusing mutable :latest tag; use a versioned image." >&2
    exit 2
    ;;
esac

: "${PRIDICT_RELEASE_APPROVED:?Set PRIDICT_RELEASE_APPROVED=YES for the scheduled cutover}"
: "${PREDEPLOY_BACKUP_BLOB:?Set PREDEPLOY_BACKUP_BLOB to the verified off-VM backup blob path}"
: "${PREDEPLOY_SNAPSHOT:?Set PREDEPLOY_SNAPSHOT to the successful Azure snapshot name}"

if [ "$PRIDICT_RELEASE_APPROVED" != "YES" ]; then
  echo "PRIDICT_RELEASE_APPROVED must equal YES." >&2
  exit 2
fi

set -a
. ./.env
set +a
: "${SITE_NAME:?SITE_NAME is required in /opt/erpnext/.env}"

if ! docker image inspect "$target_image" >/dev/null 2>&1; then
  docker pull "$target_image"
fi

docker run --rm --entrypoint bash "$target_image" -lc \
  'test -f apps/pridict/pridict/hooks.py && ./env/bin/python -c "import pridict,json; from pathlib import Path; a=json.loads(Path(\"assets/assets.json\").read_text()); assert all(Path(\"assets\"+a[k][7:]).is_file() for k in (\"pridict.bundle.css\",\"pridict.bundle.js\",\"desk.bundle.css\"))"'

current_image=$(docker inspect --format '{{.Config.Image}}' erpnext-demo-backend-1)
release_id=$(date -u +%Y%m%dT%H%M%SZ)
state_dir=/opt/erpnext/release-state
state_file="$state_dir/$release_id.env"
install -d -m 700 "$state_dir"
cat > "$state_file" <<EOF
RELEASE_ID=$release_id
SITE_NAME=$SITE_NAME
PREVIOUS_IMAGE=$current_image
TARGET_IMAGE=$target_image
PREDEPLOY_BACKUP_BLOB=$PREDEPLOY_BACKUP_BLOB
PREDEPLOY_SNAPSHOT=$PREDEPLOY_SNAPSHOT
EOF
chmod 600 "$state_file"

docker compose exec -T backend bench --site "$SITE_NAME" set-maintenance-mode on
docker compose exec -T backend bench --site "$SITE_NAME" disable-scheduler
docker compose stop scheduler worker

env_tmp=$(mktemp)
awk -v image="$target_image" '
  BEGIN { updated = 0 }
  /^ERPNEXT_IMAGE=/ { print "ERPNEXT_IMAGE=" image; updated = 1; next }
  { print }
  END { if (!updated) print "ERPNEXT_IMAGE=" image }
' .env > "$env_tmp"
chmod 600 "$env_tmp"
mv "$env_tmp" .env
export ERPNEXT_IMAGE="$target_image"

if ! docker compose config -q \
  || ! docker compose run --rm configurator \
  || ! docker compose up -d backend websocket frontend \
  || ! docker compose exec -T backend bash -ec 'apps=$(bench --site "$1" list-apps); if ! printf "%s\n" "$apps" | awk "{print \$1}" | grep -qx pridict; then bench --site "$1" install-app pridict; fi' -- "$SITE_NAME" \
  || ! docker compose exec -T backend bench --site "$SITE_NAME" migrate \
  || ! docker compose exec -T backend bench --site "$SITE_NAME" clear-cache \
  || ! docker compose up -d; then
  echo "Release failed. Maintenance mode remains enabled." >&2
  echo "State: $state_file" >&2
  echo "Use the recorded snapshot/database backup for a pre-Pridict rollback." >&2
  exit 1
fi

docker compose exec -T backend bench --site "$SITE_NAME" enable-scheduler
docker compose exec -T backend bench --site "$SITE_NAME" set-maintenance-mode off
if ! EXPECT_PRIDICT=1 ./verify.sh; then
  docker compose exec -T backend bench --site "$SITE_NAME" set-maintenance-mode on || true
  docker compose exec -T backend bench --site "$SITE_NAME" disable-scheduler || true
  echo "Post-release verification failed. Maintenance mode was restored." >&2
  echo "State: $state_file" >&2
  exit 1
fi

echo "Pridict release completed with image $target_image"
echo "Release state: $state_file"
