"""Готовый анализатор: одинаковые расчёты для CLI и HTTP API."""

import argparse
import csv
import io
import json
import math
import statistics
from pathlib import Path
import sys

HEADER = ["experiment", "accuracy", "latency_ms"]


class CSVError(ValueError):
    pass


def analyze_bytes(data: bytes) -> dict:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVError("CSV должен иметь кодировку UTF-8") from exc
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    values = {name: [] for name in HEADER[1:]}
    rows = 0
    try:
        if next(reader, None) != HEADER:
            raise CSVError("Ожидается заголовок experiment,accuracy,latency_ms")
        for row in reader:
            if len(row) != len(HEADER):
                raise CSVError(f"Строка {reader.line_num}: ожидаются 3 поля")
            if not row[0].strip():
                raise CSVError(f"Строка {reader.line_num}: experiment не может быть пустым")
            rows += 1
            for name, raw in zip(HEADER[1:], row[1:]):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    number = float(raw)
                except ValueError as exc:
                    raise CSVError(f"Строка {reader.line_num}: {name} должен быть числом") from exc
                if not math.isfinite(number):
                    raise CSVError(f"Строка {reader.line_num}: {name} должен быть конечным числом")
                values[name].append(number)
    except csv.Error as exc:
        raise CSVError(f"Некорректный CSV: {exc}") from exc
    if not rows:
        raise CSVError("После заголовка должна быть хотя бы одна строка данных")
    columns = {}
    for name, numbers in values.items():
        count = len(numbers)
        # mean суммирует float через точные дроби, избегая переполнения суммы.
        mean = round(statistics.mean(numbers), 6) if count else None
        columns[name] = {
            "count": count,
            "missing": rows - count,
            "min": min(numbers) if count else None,
            "max": max(numbers) if count else None,
            "mean": mean,
        }
    return {"row_count": rows, "columns": columns}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Анализ UTF-8 CSV: experiment,accuracy,latency_ms; минимум одна строка. "
        "experiment обязателен, пустые метрики считаются пропусками. "
        "Ошибки CSV/чтения/записи: код 1; неверные аргументы: код 2."
    )
    parser.add_argument("input", type=Path, help="Путь к CSV")
    parser.add_argument("--output", required=True, type=Path, help="Путь к JSON; родительский каталог должен существовать")
    args = parser.parse_args()
    try:
        report = analyze_bytes(args.input.read_bytes())
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
