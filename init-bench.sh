#!/bin/bash
set -e

echo "=== Initializing Frappe Bench for ERPNext Development ==="

BENCH_DIR="/workspace/development/frappe-bench"

if [ ! -d "$BENCH_DIR" ]; then
    echo "Creating Frappe Bench in $BENCH_DIR..."
    bench init --skip-redis-config-generation --frappe-branch version-15 "$BENCH_DIR"
fi

cd "$BENCH_DIR"

echo "Configuring DB and Redis connections..."
bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379

echo "Linking node_modules..."
rm -rf node_modules
ln -s apps/frappe/node_modules node_modules

if [ ! -d "$BENCH_DIR/apps/erpnext" ]; then
    echo "Linking local ERPNext source code..."
    bench get-app --skip-assets erpnext /workspace/development/apps/erpnext
fi

if [ ! -d "$BENCH_DIR/apps/pridict" ]; then
    echo "Linking local Pridict source code..."
    ln -s /workspace/development/apps/erpnext/pridict_app "$BENCH_DIR/apps/pridict"
    bench setup requirements --python pridict
fi

grep -qxF pridict sites/apps.txt || printf '\npridict\n' >> sites/apps.txt

SITE_NAME="development.localhost"

if [ ! -d "$BENCH_DIR/sites/$SITE_NAME" ]; then
    echo "Creating new Frappe site ($SITE_NAME)..."
    bench new-site "$SITE_NAME" --db-root-password 123 --admin-password admin --mariadb-user-host-login-scope=%
    echo "Installing ERPNext onto $SITE_NAME..."
    bench --site "$SITE_NAME" install-app erpnext
    bench --site "$SITE_NAME" set-config developer_mode 1
fi

if ! bench --site "$SITE_NAME" list-apps | awk '{print $1}' | grep -qx pridict; then
    echo "Installing Pridict onto $SITE_NAME..."
    bench --site "$SITE_NAME" install-app pridict
fi

echo "Building Pridict assets..."
bench build --app pridict

bench use "$SITE_NAME"

echo "=== Initialization Complete! ==="
echo "You can now run: cd /workspace/development/frappe-bench && bench start"
