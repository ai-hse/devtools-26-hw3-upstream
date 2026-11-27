#!/usr/bin/env bash
set -uo pipefail

usage() {
    echo "Usage: $0 <input_dir> <reports_dir> <logs_dir>" >&2
    exit 2
}

if [ "$#" -ne 3 ]; then
    usage
fi
INPUT_DIR="$1"
REPORTS_DIR="$2"
LOGS_DIR="$3"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ANALYZER="$PROJECT_ROOT/app/analyzer.py"
VENV_PY="$PROJECT_ROOT/.venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "Ошибка: не найден .venv ($VENV_PY)" >&2
    exit 2
fi

if [ ! -d "$INPUT_DIR" ]; then
    echo "Ошибка: входной каталог не найден: $INPUT_DIR" >&2
    exit 2
fi

mkdir -p -- "$REPORTS_DIR" 2>/dev/null || {
    echo "Ошибка: не могу создать каталог отчётов: $REPORTS_DIR" >&2
    exit 2
}
mkdir -p -- "$LOGS_DIR" 2>/dev/null || {
    echo "Ошибка: не могу создать каталог логов: $LOGS_DIR" >&2
    exit 2
}
[ -w "$REPORTS_DIR" ] || { echo "Ошибка: нет прав на запись в $REPORTS_DIR" >&2; exit 2; }
[ -w "$LOGS_DIR" ]    || { echo "Ошибка: нет прав на запись в $LOGS_DIR" >&2; exit 2; }

shopt -s nullglob
csv_files=()
for f in "$INPUT_DIR"/*.csv; do
    if [ -f "$f" ] && [ ! -L "$f" ]; then
        csv_files+=("$f")
    fi
done
shopt -u nullglob

if [ "${#csv_files[@]}" -eq 0 ]; then
    echo "Ошибка: во входном каталоге нет .csv-файлов: $INPUT_DIR" >&2
    exit 2
fi

processed=0
failed=0

for csv in "${csv_files[@]}"; do
    base="$(basename -- "$csv")"
    stem="${base%.csv}"
    report="$REPORTS_DIR/$stem.json"
    log="$LOGS_DIR/$stem.log"

    # ВАЖНО: --output обязателен, родительский каталог уже создан
    if "$VENV_PY" "$ANALYZER" "$csv" --output "$report" 2>"$log"; then
        processed=$((processed + 1))
    else
        failed=$((failed + 1))
        rm -f -- "$report"
    fi
done

echo "processed=$processed failed=$failed"

if [ "$failed" -gt 0 ]; then
    exit 1
fi
exit 0