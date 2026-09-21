#!/usr/bin/env bash
set -euo pipefail
cd /opt/erpnext
umask 077
SITE_NAME=riditstack-erpnext-demo.centralindia.cloudapp.azure.com
if [ ! -f .env ]; then
  printf 'SITE_NAME=%s\nDB_ROOT_PASSWORD=%s\nADMIN_PASSWORD=%s\n' "$SITE_NAME" "$(openssl rand -hex 24)" "$(openssl rand -hex 18)" > .env
fi
set -a
. ./.env
set +a
PUBLIC_HOSTNAME=${PUBLIC_HOSTNAME:-$SITE_NAME}
printf '%s {\n  reverse_proxy frontend:8080\n}\n' "$PUBLIC_HOSTNAME" > Caddyfile
docker compose config -q
docker compose pull
docker compose up -d db redis-cache redis-queue configurator
for attempt in $(seq 1 60); do
  if [ "$(docker inspect --format '{{.State.Health.Status}}' erpnext-demo-db-1)" = healthy ]; then break; fi
  sleep 5
done
docker compose run --rm configurator
if ! docker compose run --rm --entrypoint test backend -f "sites/$SITE_NAME/site_config.json"; then
  docker compose run --rm -e ADMIN_PASSWORD -e DB_ROOT_PASSWORD -e SITE_NAME --entrypoint bash backend -ec 'bench new-site "$SITE_NAME" --mariadb-user-host-login-scope="%" --admin-password "$ADMIN_PASSWORD" --db-root-password "$DB_ROOT_PASSWORD" --install-app erpnext --set-default'
fi
if docker compose run --rm --entrypoint test backend -f apps/pridict/pridict/hooks.py; then
  docker compose run --rm -e SITE_NAME --entrypoint bash backend -ec 'bench --site "$SITE_NAME" list-apps | grep -qx pridict || bench --site "$SITE_NAME" install-app pridict'
fi
docker compose run --rm --entrypoint bench backend --site "$SITE_NAME" set-config host_name "https://$PUBLIC_HOSTNAME"
docker compose run --rm --entrypoint bench backend --site "$SITE_NAME" migrate
docker compose run --rm --entrypoint bench backend --site "$SITE_NAME" enable-scheduler
docker compose up -d
echo 'ERPNext deployment completed; Pridict installed when present in the configured image'
