#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 0 ]; then
    echo "Usage: $0" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VENV_PY="$PROJECT_ROOT/.venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
    echo "Ошибка: не найден .venv ($VENV_PY). Создайте виртуальное окружение." >&2
    exit 1
fi

if [ -n "${DATA_DIR:-}" ]; then
    mkdir -p -- "$DATA_DIR" 2>/dev/null || {
        echo "Ошибка: не могу создать DATA_DIR=$DATA_DIR" >&2
        exit 1
    }
    [ -w "$DATA_DIR" ] || {
        echo "Ошибка: нет прав на запись в DATA_DIR=$DATA_DIR" >&2
        exit 1
    }
fi

cd "$PROJECT_ROOT"
exec "$VENV_PY" "app/server.py"