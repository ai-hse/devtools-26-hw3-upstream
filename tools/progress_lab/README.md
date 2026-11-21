# Одна задача: polling, WebSocket и gRPC

Это готовые инструменты для дополнительных исследований 4 и 5. Менять их код не требуется. Сервер имитирует пять этапов обработки CSV. Он не использует расчёты и данные основного приложения. Все три интерфейса читают одно состояние задачи в одном процессе.

Все команды выполняйте **на одной Linux-машине, из корня проекта**. Понадобятся несколько терминалов. Проверьте, что порты `8020`, `8021` и `8022` свободны. Не останавливайте чужие процессы.

## Подготовка

У дополнительных клиентов своё окружение. Оно лежит в `work/` и не входит в образ основного приложения:

```bash
python3 -m venv work/progress-venv
work/progress-venv/bin/python -m pip install -r tools/progress_lab/requirements.txt
```

Посмотреть интерфейс готовых программ:

```bash
work/progress-venv/bin/python tools/progress_lab/server.py --help
work/progress-venv/bin/python tools/progress_lab/client.py --help
work/progress-venv/bin/python tools/progress_lab/client.py poll --help
```

## Запуск опыта

**Терминал 1.** Запустите сервер и дождитесь строки с `"ready": true`:

```bash
work/progress-venv/bin/python tools/progress_lab/server.py
```

Она содержит фактические порты HTTP, WebSocket и gRPC. По умолчанию это `8020`, `8021` и `8022`. Сервер доступен только через `127.0.0.1` этой машины.

**Терминал 2.** Создайте ожидающую задачу:

```bash
TASK_ID=$(work/progress-venv/bin/python tools/progress_lab/client.py create)
printf '%s\n' "$TASK_ID"
work/progress-venv/bin/python tools/progress_lab/client.py state "$TASK_ID"
```

Команда `create` печатает только ID. Задача ещё не обрабатывается. Скопируйте полученный ID в следующие терминалы: переменные оболочки между терминалами не передаются.

**Терминал 3.** Замените `ID_ИЗ_CREATE` реальным значением и запустите polling:

```bash
TASK_ID='ID_ИЗ_CREATE'
work/progress-venv/bin/python tools/progress_lab/client.py poll "$TASK_ID" --interval 2
```

**Терминал 4.** Укажите тот же ID и подключите WebSocket:

```bash
TASK_ID='ID_ИЗ_CREATE'
work/progress-venv/bin/python tools/progress_lab/client.py ws "$TASK_ID"
```

Оба клиента должны вывести строку `"type": "ready"`. После этого **в терминале 2** запустите обработку:

```bash
work/progress-venv/bin/python tools/progress_lab/client.py start "$TASK_ID"
```

Клиенты выводят события с `sequence`, `stage`, `created_at` и `latency_ms`, затем сводку `summary`. Номер события относится к задаче, а не к отдельному клиенту. `http_requests` у polling включает все запросы истории. У WebSocket учитывается один HTTP-запрос для установки соединения. Сообщения внутри WebSocket не считаются отдельными HTTP-запросами.

Для следующего опыта создайте новую задачу и повторите подключения. Чтобы изменить частоту polling, задайте другое значение `--interval`. Чтобы изменить задержку между этапами, перезапустите сервер с параметром `--step-delay`. Он задаёт секунды между этапами и по умолчанию равен `1`. Сравнивайте задержки на одной машине. Это учебный опыт, а не тест производительности протоколов.

## Тот же опыт через gRPC

Создайте новую ожидающую задачу. Прочитайте её состояние и подключите третий клиент **до команды `start`**:

```bash
TASK_ID='ID_НОВОЙ_ЗАДАЧИ'
work/progress-venv/bin/python tools/progress_lab/client.py grpc-state "$TASK_ID"
work/progress-venv/bin/python tools/progress_lab/client.py grpc-stream "$TASK_ID"
```

Дождитесь `"type": "ready"`, запустите обработку из управляющего терминала и сравните события. Контракт методов описан в [progress.proto](progress.proto). Сгенерированные Python-файлы `progress_pb2.py` и `progress_pb2_grpc.py` уже включены в комплект.

Для запросов по несуществующему ID используйте, например, `missing` вместо `"$TASK_ID"`. Для опыта с остановкой сервера сначала создайте ещё одну задачу, подключите клиентов, начните обработку, затем остановите сервер в терминале 1. Перед сравнением обычного HTTP/1.1 с gRPC сервер нужно запустить снова.

## Интерфейсы и ограничения

| Интерфейс | Адрес или метод | Результат |
|---|---|---|
| HTTP | `POST /tasks` | Создать задачу `waiting`. Ответ: HTTP 201 и ID задачи. |
| HTTP | `POST /tasks/ID/start` | Начать обработку. Ответ: HTTP 202. При повторном запуске ответ HTTP 409. |
| HTTP | `GET /tasks/ID` | Текущее состояние и вся история. Для неизвестного ID ответ HTTP 404. |
| WebSocket | `ws://127.0.0.1:8021/tasks/ID` | Подтверждение подписки, новые события, завершение |
| gRPC | `Progress.GetState` | Текущее состояние и вся история. Для неизвестного ID возвращается `NOT_FOUND`. |
| gRPC | `Progress.Watch` | Подтверждение подписки в metadata и поток новых событий |

HTTP и `GetState` возвращают историю. Потоки передают только события, созданные после подписки. Поэтому подключите клиентов до начала обработки. Готовые клиенты не переподключаются автоматически. Состояние хранится в памяти. После перезапуска сервера создавайте новые задачи. Одновременно в процессе можно создать до 100 задач.

Клиенты ждут не больше 120 секунд. При необходимости увеличьте общий предел: `client.py --timeout 300 poll ID`. Ответ с ошибкой, разрыв соединения или истечение этого предела дают ненулевой код завершения и сообщение в stderr.

Если стандартные порты заняты, у сервера есть `--http-port`, `--ws-port` и `--grpc-port`. Клиентам передайте соответствующие `--http http://127.0.0.1:PORT`, `--ws ws://127.0.0.1:PORT` и `--grpc 127.0.0.1:PORT` **перед названием команды**. Например:

```bash
work/progress-venv/bin/python tools/progress_lab/client.py --http http://127.0.0.1:18020 create
```

После опыта завершите свои клиенты и сервер через `Ctrl+C`. Другие сервисы и данные основного задания затрагивать не нужно.

## Проверка готовых инструментов

```bash
work/progress-venv/bin/python tools/progress_lab/selftest.py
```

Проверка выбирает свободные loopback-порты, сравнивает события трёх интерфейсов, проверяет ошибки и остановку сервера, затем завершает только собственные процессы. Она не оценивает ваше решение ДЗ.

Документация библиотек: [gRPC Python](https://grpc.io/docs/languages/python/basics/), [WebSocket-клиенты и серверы](https://websockets.readthedocs.io/en/stable/reference/sync/server.html).
