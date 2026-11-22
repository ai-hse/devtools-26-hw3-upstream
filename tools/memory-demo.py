#!/usr/bin/env python3
"""Запускайте только в одноразовом контейнере с лимитом памяти."""

import time


def main():
    chunks = []
    for size in range(1, 129):
        # Ненулевой байт заставляет ОС выделять физические страницы.
        chunks.append(bytearray(b"x" * (1024 * 1024)))
        if size % 8 == 0:
            print(f"Выделено и заполнено {size} MiB", flush=True)
        time.sleep(0.025)
    print("Достигнуто 128 MiB", flush=True)


if __name__ == "__main__":
    main()
