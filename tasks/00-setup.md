# Подготовка и общие правила

Здесь вы настроите окружение, получите первый отчёт и прочитаете правила, общие для всех частей.

## Окружение

Нужна Linux-машина или учебная ВМ, на которой есть:

- Bash, `curl`, `tar`, `ss` и `ps`;
- Python 3.12 с модулем `venv`;
- Docker Engine и плагин Docker Compose с поддержкой `up --wait`.

<details>
<summary><b>Mac и Windows</b></summary>

Всё задание делается в Ubuntu 24.04. Docker Desktop не подойдёт: часть опытов сравнивает контейнер с Linux-хостом.

**Mac.** Установите [Multipass](https://documentation.ubuntu.com/multipass/latest/how-to-guides/install-multipass/install-multipass-on-macos/) и создайте Ubuntu:

```bash
multipass launch 24.04 --name devtools --cpus 2 --memory 4G --disk 20G
multipass shell devtools
```

**Windows.** В PowerShell от администратора установите [WSL 2](https://learn.microsoft.com/windows/wsl/install/) с Ubuntu: `wsl --install -d Ubuntu-24.04`. Если стоит Docker Desktop, отключите в нём интеграцию с WSL.

Дальше в терминале Ubuntu установите Python с `venv` и Docker и разрешите запуск `docker` без `sudo`:

```bash
sudo apt update && sudo apt install -y python3.12-venv
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

В WSL установщик Docker посоветует Docker Desktop и подождёт 20 секунд, не прерывайте его. Затем перезапустите Ubuntu: `multipass restart devtools` на Mac или `wsl --shutdown` в PowerShell.

Репозиторий клонируйте в домашний каталог Ubuntu, а не в каталог, общий с Mac или Windows.

</details>

### Проверить окружение

```bash
python3 --version          # должен быть Python 3.12
docker info                # без sudo и без ошибок
docker compose version
```

Если чего-то не хватает, установите по инструкциям: [Python](https://docs.python.org/3.12/using/unix.html), [Docker Engine](https://docs.docker.com/engine/install/), [Compose](https://docs.docker.com/compose/install/linux/).

## Первый отчёт

Здесь и во всех частях команды выполняются **на этой Linux-машине из корня проекта**, если шаг не говорит другого.

1. Склонируйте свой репозиторий и создайте ветку `solution` от `main`.

2. Создайте виртуальное окружение и установите зависимости:

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```

3. Прочитайте справку анализатора и сервера:

   ```bash
   .venv/bin/python app/analyzer.py --help
   .venv/bin/python app/server.py --help
   ```

   Формат CSV и пример отчёта описаны в [справке](../interfaces.md).

4. Создайте каталоги для результатов и обработайте первый файл:

   ```bash
   mkdir -p work/reports work/logs
   .venv/bin/python app/analyzer.py samples/clean.csv --output work/reports/clean.json
   ```

5. Откройте `samples/clean.csv` и `work/reports/clean.json` рядом. Каждая строка CSV описывает один эксперимент, в числовых столбцах лежат его метрики. Сверьте число строк и хотя бы одну статистику с исходными данными. Позже такие отчёты будут создавать ваши скрипты.

6. Заполните `.gitignore`. В Git не должны попасть виртуальное окружение, рабочие данные, логи, архивы, локальный `.env` и кэш Python (`__pycache__`, `*.pyc`). Примеры из `samples/` остаются в Git.

## Что можно менять

**Можно:** заготовки `scripts/start.sh`, `batch.sh`, `submit.sh`, `probe.sh` и `backup.sh`, а также `app/settings.py`, `compose.yaml`, `gateway/nginx.conf` и ignore-файлы. `Dockerfile` и `.dockerignore` вы создадите в части 4.

**Нельзя:** остальной код в `app/`, примеры в `samples/`, `scripts/run-container.sh`, `gateway/Dockerfile`, программы в `tools/` и `.env.example`.

Одно исключение: в опыте с кэшем в части 4 вы временно измените Python-код и `requirements.txt`. После опыта верните их как было.

## Общие правила

### Скрипты

- Скрипты пишутся на Bash и запускаются через `bash`, как в примерах.
- Скрипт работает, из какого бы каталога его ни вызвали. Путь к проекту он определяет сам.
- Относительные пути в аргументах отсчитываются от каталога, из которого вызвали скрипт.
- Пути могут содержать пробелы.
- При неверном числе аргументов скрипт пишет сообщение в stderr и завершается с ненулевым кодом. Точные коды указаны в частях.
- Настройки скрипты получают через переменные окружения. Читать `.env` не нужно: он понадобится только Compose в части 6.

### Что не проверяется

Проверки используют небольшие CSV и архивы. Параллельные запуски скриптов не проверяются, как и одновременная запись в каталог резервной копии или смена прав во время работы. Веб-сервер работает одним процессом, менять его устройство не нужно.

### Опыты

В каждой части есть опыты. Они не оцениваются. Опыт перед требованиями показывает проблему, которую требование решает. Опыт после требований проверяет ваше решение. Проводите опыт так: сделайте прогноз, измените одно условие, сравните результат и объясните себе, почему поведение изменилось.

Если порт из примера занят чужим процессом, возьмите любой свободный и используйте его до конца части. Чужие процессы не останавливайте.

---

Подготовка закончена, если виртуальное окружение создано, а анализатор выдал первый отчёт. Переходите к [части 1](01-start.md). Удачи!
