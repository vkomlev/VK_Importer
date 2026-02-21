# Phase 4: Очередь задач (SQLite)

Минимальная рабочая очередь внутри монолита: таблица `jobs` в SQLite, контракт API, один воркер. Без выноса в отдельные сервисы.

## Контракт API (код)

Интерфейс в `src/storage/job_queue.py`, класс `JobQueue`:

| Метод | Описание |
|-------|----------|
| `enqueue(job_type, payload, run_after=None)` | Поставить задачу в очередь. Возвращает `job_id`. |
| `claim_next(job_types=None)` | Атомарно взять следующую задачу (транзакция BEGIN IMMEDIATE: SELECT → UPDATE → возврат строки после UPDATE, status=running, attempt уже увеличен). |
| `complete(job_id, result=None)` | Отметить задачу выполненной (status=done). При переданном `result` сохраняет его в колонку `result_json`. |
| `fail_retry(job_id, error, run_after=None)` | Неудача с повтором: status=pending, задать run_after. |
| `fail(job_id, error)` | Окончательная неудача (status=failed). |

Типы задач задаются строкой (`job_type`). Payload — произвольный JSON-объект.

## Схема таблицы `jobs`

В той же БД, что и видео (по умолчанию `videos.db`):

| Колонка | Тип | Описание |
|---------|-----|----------|
| id | INTEGER PK | Идентификатор задачи. |
| type | TEXT | Тип задачи (например `upload_video`). |
| payload_json | TEXT | JSON с параметрами задачи. |
| status | TEXT | `pending` \| `running` \| `done` \| `failed`. |
| attempt | INTEGER | Номер попытки (увеличивается при claim_next). |
| run_after | TEXT (ISO datetime) | Не раньше какого времени брать задачу (для отложенного повтора). |
| error | TEXT | Сообщение об ошибке (при fail/fail_retry). |
| result_json | TEXT | JSON результата (при complete(job_id, result=...)). |
| created_at | TEXT | Время создания. |
| updated_at | TEXT | Время последнего обновления. |

Индексы: `(status, type)`, `run_after`. Атомарность `claim_next`: одна транзакция с `BEGIN IMMEDIATE`, чтобы при нескольких воркерах одна и та же задача не забиралась дважды.

## CLI воркер

```bash
python main.py worker --once          # Взять одну задачу и выйти
python main.py worker --loop          # Цикл с паузой между опросами
python main.py worker --loop -i 5     # Пауза 5 сек
python main.py worker --once -t upload_video   # Только тип upload_video
```

Реализованный тип задач:

- **upload_video** — payload `{"video_id": int}`. Воркер забирает запись из БД, вызывает загрузку через VKDestinationAdapter; при успехе — `complete`, при операционной ошибке (partial) — `fail_retry` с run_after через 5 мин, при фатальной — `fail`.

## Постановка задач в очередь

Через API (из кода или скрипта):

```python
from pathlib import Path
from src.storage.job_queue import JobQueue

queue = JobQueue(Path("videos.db"))
job_id = queue.enqueue("upload_video", {"video_id": 123})
```

Из CLI постановка не добавлена (можно вызывать `upload-one` как раньше или добавить команду `enqueue-upload`).

## Миграция на Redis (будущее)

При росте нагрузки тот же контракт можно реализовать поверх Redis:

- **enqueue** → LPUSH в список по типу + сохранение payload в hash по job_id.
- **claim_next** → атомарно (Lua или BRPOPLPUSH) перенести задачу из pending в running, вернуть payload.
- **complete** / **fail** / **fail_retry** → обновить статус в hash, при fail_retry — снова в pending с run_after (sorted set по времени).

Правила миграции:

1. Интерфейс `JobQueue` оставить тем же: те же методы и семантика (enqueue, claim_next, complete, fail_retry, fail).
2. Вызывающий код (worker, CLI) не меняется; подменяется только реализация (SQLite → Redis).
3. Формат payload и типы задач не меняются.
4. При переходе: доразобрать оставшиеся задачи в SQLite или перенести вручную (экспорт pending в Redis).

Итого: контракт зафиксирован в коде; замена backend на Redis — без изменения контракта.

## Смоук-тесты очереди

Запуск: из корня репозитория `python scripts/smoke-phase4-job-queue.py`. Ожидание: 3/3 passed.

1. **Конкурентный claim** — два процесса одновременно вызывают `claim_next()` при одной pending-задаче; ровно один получает задачу, второй — `None`.
2. **Retry run_after** — после `fail_retry(..., run_after=now+2s)` задача не забирается до истечения времени; после sleep 2.5 сек забирается.
3. **Состояние после fail_retry** — после claim и `fail_retry(job_id, "PUBLISH_FAILED", run_after=now+5m)` у задачи: `status=pending`, `attempt=1`, `error` заполнен, `run_after` в будущем.

Дополнительно (ручная проверка): `worker --once` с задачей `upload_video` и записью, по которой публикация даёт partial (например отсутствующий файл → NO_VIDEO): в БД задача снова в pending, attempt+1, error и run_after заполнены.
