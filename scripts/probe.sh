#!/usr/bin/env bash
set -uo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <url>" >&2
    exit 2
fi
URL="$1"

http_code="$(curl -sS \
    --max-time 3 \
    --request GET \
    --output /dev/null \
    --write-out '%{http_code}' \
    --url "$URL")"
curl_rc=$?

if [ "$curl_rc" -ne 0 ]; then
    echo "Ошибка: запрос не удался (curl rc=$curl_rc): $URL" >&2
    exit 1
fi
if [ "$http_code" != "200" ]; then
    echo "Ошибка: ожидался HTTP 200, получен $http_code: $URL" >&2
    exit 1
fi
exit 0