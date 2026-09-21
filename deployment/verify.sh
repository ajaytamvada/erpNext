#!/usr/bin/env bash
set -euo pipefail
cd /opt/erpnext
set -a
. ./.env
set +a
docker compose ps
python3 - <<'PY'
import http.cookiejar
import json
import os
import time
import urllib.parse
import urllib.request

base = 'https://' + os.environ.get('PUBLIC_HOSTNAME', os.environ['SITE_NAME'])
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
for attempt in range(12):
    try:
        with client.open(base + '/login', timeout=10) as response:
            page = response.read().decode()
            assert response.status == 200
        break
    except (OSError, AssertionError):
        if attempt == 11:
            raise
        time.sleep(3)
print('HTTPS login page: OK')
data = urllib.parse.urlencode({'usr': 'Administrator', 'pwd': os.environ['ADMIN_PASSWORD']}).encode()
with client.open(base + '/api/method/login', data=data, timeout=30) as response:
    result = json.load(response)
    assert result.get('message') == 'Logged In', result
    print('Administrator authentication: OK')
with client.open(base + '/api/method/frappe.auth.get_logged_user', timeout=30) as response:
    assert json.load(response)['message'] == 'Administrator'
    print('Authenticated session: OK')
import re
if os.environ.get('EXPECT_PRIDICT') == '1':
    with client.open(base + '/app', timeout=30) as response:
        desk = response.read().decode()
        assert response.status == 200
    splash = re.search(r'<div class="centered splash">(.*?)</div>', desk, re.S)
    assert splash and '/assets/pridict/images/pridict-icon.svg' in splash.group(1), 'Pridict loader missing'
    with client.open(base + '/assets/pridict/images/pridict-icon.svg', timeout=30) as response:
        assert response.status == 200 and '<svg' in response.read().decode()
    for surface in (page, desk):
        assert '/assets/pridict/images/pridict-icon.svg' in surface, 'Pridict icon missing'
        assert '/assets/pridict/dist/css/pridict.bundle.' in surface, 'Pridict CSS missing'
        assert '/assets/pridict/dist/js/pridict.bundle.' in surface, 'Pridict JS missing'
    page += desk
assets = re.findall(r'(?:src|href)="([^"?]+\.(?:css|js))(?:\?[^"]*)?"', page)
assert assets, 'No login assets found'
for asset in set(assets):
    if asset.startswith('/assets/'):
        with client.open(base + asset, timeout=30) as response:
            assert response.status == 200
print('Page CSS/JS assets: OK')
client.open(base + '/api/method/logout', timeout=30).close()
PY
docker compose exec -T backend bench --site "$SITE_NAME" list-apps
if [ "${EXPECT_PRIDICT:-0}" = 1 ]; then
  docker compose exec -T backend bench --site "$SITE_NAME" list-apps | awk '{print $1}' | grep -qx pridict
  docker compose exec -T backend test -f apps/pridict/pridict/hooks.py
  docker compose exec -T backend sh -lc 'ls sites/assets/pridict/dist/css/pridict.bundle.*.css >/dev/null'
fi
doctor_output=$(docker compose exec -T backend bench doctor)
printf '%s\n' "$doctor_output"
printf '%s\n' "$doctor_output" | grep -Eq 'Workers online: [1-9][0-9]*'
