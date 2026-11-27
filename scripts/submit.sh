#!/usr/bin/env bash
set -uo pipefail

usage() { echo "Usage: $0 <base_url> <input.csv> <output.json>" >&2; exit 2; }

if [ "$#" -ne 3 ]; then usage; fi
BASE_URL="${1%/}"
INPUT="$2"
OUTPUT="$3"

if [ ! -f "$INPUT" ] || [ ! -r "$INPUT" ]; then
    echo "Ошибка: входной файл не найден или не читается: $INPUT" >&2
    exit 1
fi

OUT_DIR="$(dirname -- "$OUTPUT")"
if [ ! -d "$OUT_DIR" ]; then
    echo "Ошибка: каталог выходного файла не существует: $OUT_DIR" >&2
    exit 1
fi

TMP="$(mktemp -- "$OUT_DIR/.submit.XXXXXX")" || {
    echo "Ошибка: не удалось создать временный файл в $OUT_DIR" >&2
    exit 1
}
cleanup() { rm -f -- "$TMP"; }
trap cleanup EXIT INT TERM

URL="$BASE_URL/reports"

http_code="$(curl -sS \
    --max-time 10 \
    --request POST \
    --form "file=@${INPUT};type=text/csv" \
    --output "$TMP" \
    --write-out '%{http_code}' \
    --url "$URL")"
curl_rc=$?

if [ "$curl_rc" -ne 0 ]; then
    echo "Ошибка: запрос не удался (curl rc=$curl_rc): $URL" >&2
    exit 1
fi
if [ "$http_code" != "201" ]; then
    echo "Ошибка: ожидался HTTP 201, получен $http_code: $URL" >&2
    exit 1
fi

if ! mv -f -- "$TMP" "$OUTPUT"; then
    echo "Ошибка: не удалось записать выходной файл: $OUTPUT" >&2
    exit 1
fi
exit 0