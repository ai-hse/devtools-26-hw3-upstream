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
  entry=$(git -C "$root" ls-tree HEAD -- "$file")
  case "${entry%% *}" in
    100644|100755) ;;
    *) fail "в последнем коммите нет обычного файла $file." ;;
  esac
done

for path in .env .venv/check-ready work/check-ready check-ready.tar.gz; do
  git -C "$root" check-ignore --no-index -q -- "$path" || fail "добавьте '$path' в .gitignore."
done
while IFS= read -r -d '' file; do
  case "$file" in
    .env|.venv|.venv/*|work|work/*|*.tar.gz) fail "в Git отслеживается рабочий файл: $file." ;;
  esac
done < <(git -C "$root" ls-files -z)
[[ -z "$(git -C "$root" status --porcelain)" ]] || fail 'остались незакоммиченные или неотслеживаемые файлы. Проверьте git status.'
(cd -- "$root" && docker compose config --quiet) || fail 'конфигурация Compose содержит ошибку.'
printf 'Ветка, файлы и конфигурация Compose проверены. Можно отправлять solution.\n'
