#!/usr/bin/env bash
set -uo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
fail() { printf 'Не готово к отправке: %s\n' "$1" >&2; exit 1; }
repo=$(git -C "$root" rev-parse --show-toplevel 2>/dev/null) || fail 'проект не находится в Git-репозитории.'
[[ "$(cd -- "$repo" && pwd -P)" == "$root" ]] || fail 'корень проекта должен быть корнем Git-репозитория.'
[[ "$(git -C "$root" branch --show-current)" == solution ]] || fail 'нужна ветка solution.'
git -C "$root" rev-parse --verify HEAD >/dev/null 2>&1 || fail 'сначала создайте коммит.'

for file in scripts/start.sh scripts/batch.sh scripts/submit.sh scripts/probe.sh scripts/backup.sh \
  scripts/run-container.sh app/analyzer.py app/server.py app/settings.py app/templates/index.html \
  samples/clean.csv samples/batch/broken.csv "samples/batch/run 01.csv" "samples/batch/пропуски.csv" \
  requirements.txt Dockerfile .dockerignore compose.yaml gateway/Dockerfile gateway/nginx.conf \
  gateway/service.example.yaml tools/http-fixture.py tools/check-ready.sh .env.example .gitignore; do
  entry=$(git -C "$root" ls-tree HEAD -- "$file") || fail "не удалось проверить файл $file в Git."
  case "${entry%% *}" in
    100644|100755) ;;
    *) fail "в последнем коммите нет обычного файла $file." ;;
  esac
done

for path in .env .venv/check-ready work/check-ready check-ready.tar.gz check-ready.log \
  app/__pycache__/check-ready app/check-ready.pyc; do
  git -C "$root" check-ignore --no-index -q -- "$path" || fail "добавьте '$path' в .gitignore."
done

tracked_list=$(mktemp "${TMPDIR:-/tmp}/hw3-ready.XXXXXX") || fail 'не удалось создать временный файл.'
trap 'rm -f -- "$tracked_list"' EXIT
git -C "$root" ls-files -z > "$tracked_list" || fail 'не удалось получить список файлов Git.'
while IFS= read -r -d '' file; do
  case "$file" in
    .env|.venv|.venv/*|work|work/*|*.tar.gz|*.log|*.pyc|__pycache__/*|*/__pycache__/*)
      fail "в Git отслеживается рабочий файл: $file." ;;
  esac
done < "$tracked_list"
status=$(git -C "$root" status --porcelain) || fail 'не удалось проверить состояние Git.'
[[ -z "$status" ]] || fail 'остались незакоммиченные или неотслеживаемые файлы. Проверьте git status.'
(cd -- "$root" && docker compose config --quiet) || fail 'конфигурация Compose содержит ошибку.'
printf 'Ветка, файлы и конфигурация Compose проверены. Можно отправлять solution.\n'
