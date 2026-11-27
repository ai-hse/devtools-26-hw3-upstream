#!/usr/bin/env bash
set -uo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <data_dir> <archive.tar.gz>" >&2
    exit 2
fi
DATA_DIR="$1"
ARCHIVE="$2"

if [ ! -d "$DATA_DIR" ]; then
    echo "Ошибка: каталог данных не найден: $DATA_DIR" >&2
    exit 1
fi
if [ ! -r "$DATA_DIR" ]; then
    echo "Ошибка: каталог данных не читается: $DATA_DIR" >&2
    exit 1
fi

if [ -e "$ARCHIVE" ]; then
    echo "Ошибка: архив уже существует: $ARCHIVE" >&2
    exit 1
fi

ARCHIVE_DIR="$(dirname -- "$ARCHIVE")"
if [ ! -d "$ARCHIVE_DIR" ]; then
    echo "Ошибка: каталог для архива не существует: $ARCHIVE_DIR" >&2
    exit 1
fi

TMP="$(mktemp -- "$ARCHIVE_DIR/.backup.XXXXXX")" || {
    echo "Ошибка: не удалось создать временный файл в $ARCHIVE_DIR" >&2
    exit 1
}
cleanup() { rm -f -- "$TMP"; }
trap cleanup EXIT INT TERM

if ! tar -czf "$TMP" -C "$DATA_DIR" . ; then
    echo "Ошибка: не удалось создать архив из $DATA_DIR" >&2
    exit 1
fi

if ! mv -f -- "$TMP" "$ARCHIVE"; then
    echo "Ошибка: не удалось записать архив: $ARCHIVE" >&2
    exit 1
fi
exit 0