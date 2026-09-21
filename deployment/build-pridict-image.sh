#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <versioned-image-tag>" >&2
  echo "Example: $0 pridict-erpnext:20260916-rc1" >&2
  exit 2
fi

image="$1"
case "$image" in
  *:latest)
    echo "Refusing mutable :latest tag; use a versioned tag." >&2
    exit 2
    ;;
esac

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
revision=$(git -C "$repo_root" rev-parse --verify HEAD)

docker build \
  --file "$repo_root/deployment/Dockerfile.pridict" \
  --build-arg ERPNEXT_BASE_IMAGE=frappe/erpnext:v15.121.2 \
  --build-arg BUILD_REVISION="$revision" \
  --tag "$image" \
  "$repo_root"

docker run --rm --entrypoint bash "$image" -lc \
  'test -f apps/pridict/pridict/hooks.py && test -n "$(find apps/pridict/pridict/public/dist/css -type f -name "pridict.bundle.*.css" -print -quit)" && ./env/bin/python -c "import pridict; print(pridict.__version__)"'

echo "Built and validated $image"
