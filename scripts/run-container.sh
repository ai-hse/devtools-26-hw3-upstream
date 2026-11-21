#!/usr/bin/env bash
# Готовый инструмент. Студент не изменяет этот файл.
set -eu
if [[ $# != 4 ]]; then
    printf 'Usage: bash run-container.sh IMAGE NAME PORT VOLUME\n' >&2
    exit 2
fi
root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
image=$1 name=$2 port=$3 volume=$4
if [[ ! $port =~ ^[0-9]+$ ]] || ((port < 1024 || port > 65535)); then
    printf 'Порт должен быть целым числом от 1024 до 65535.\n' >&2
    exit 2
fi
if [[ ! -x "$root/.venv/bin/python" ]]; then
    printf 'Нет .venv: выполните подготовку проекта.\n' >&2
    exit 2
fi
if docker container inspect "$name" >/dev/null 2>&1; then
    printf 'Имя контейнера уже занято: %s\n' "$name" >&2
    exit 1
fi
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT
docker volume create "$volume" >/dev/null
if ! docker run --detach --name "$name" --cidfile "$temporary/cid" \
    --cpus 1 --memory 256m --publish "127.0.0.1:$port:8080" \
    --mount "type=volume,src=$volume,dst=/data" "$image"; then
    printf 'Контейнер не запущен. Существующие ресурсы не удалены.\n' >&2
    if [[ -s "$temporary/cid" ]]; then
        docker logs "$(cat "$temporary/cid")" >&2 || true
    fi
    exit 1
fi
cid=$(cat "$temporary/cid")
"$root/.venv/bin/python" - "$root" "$cid" "$port" <<'PY'
import os
import signal
import subprocess
import sys
import time

root, cid, port = sys.argv[1:]
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    remaining = deadline - time.monotonic()
    try:
        state = subprocess.run(
            ['docker', 'inspect', '--format', '{{.State.Running}}', cid],
            capture_output=True, text=True, timeout=min(remaining, 2),
        )
        if state.returncode or state.stdout.strip() != 'true':
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        probe = subprocess.Popen(
            ['bash', root + '/scripts/probe.sh', f'http://127.0.0.1:{port}/health'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            result = probe.wait(timeout=min(remaining, 3.5))
        finally:
            # Ошибочная студенческая probe может оставить дочерние процессы.
            try:
                os.killpg(probe.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            probe.wait()
        if result == 0:
            print(f'Готово: http://127.0.0.1:{port}')
            sys.exit(0)
    except subprocess.TimeoutExpired:
        pass
    time.sleep(min(.2, max(0, deadline - time.monotonic())))
print('Сервис не готов; контейнер оставлен для диагностики.', file=sys.stderr)
subprocess.run(['docker', 'logs', cid], stdout=sys.stderr, timeout=5)
sys.exit(1)
PY
