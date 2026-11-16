#!/bin/sh
# Smoke check for a running stack: the page, health endpoint, and generated data must load.
# Usage: docker/smoke.sh [base-url] [github-user-slug]
set -eu
BASE="${1:-http://127.0.0.1:8086}"
SLUG="${2:-$(printf '%s' "${SPARK_USER:-makeboldsolutions}" | tr '[:upper:]' '[:lower:]')}"

check() { # $1=path $2=pattern
    body="$(curl -fsS "$BASE$1")" || { echo "FAIL $1 (request)"; exit 1; }
    printf '%s' "$body" | grep -q "$2" || { echo "FAIL $1 (missing '$2')"; exit 1; }
    echo "ok   $1"
}
check /healthz '^ok'
check / '<div id="root"'
check "/data/users/$SLUG/repositories.json" '"repositories"'
check /data/status.json '"schema_version"'
code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/data/.releases/")"
[ "$code" = 404 ] && echo "ok   /data/.releases hidden" || { echo "FAIL /data/.releases served ($code)"; exit 1; }
check /api/health '"ok"'
# The API must refuse unauthenticated reads and writes.
for path in /api/sources /api/connections /api/repositories; do
    code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE$path")"
    [ "$code" = 401 ] && echo "ok   $path requires sign-in" || { echo "FAIL $path answered $code without sign-in"; exit 1; }
done
echo "smoke passed"
