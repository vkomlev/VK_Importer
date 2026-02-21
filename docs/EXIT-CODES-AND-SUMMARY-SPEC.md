# Спецификация: коды выхода и summary JSON (Phase 1)

Дата: 2026-02-21  
Связано с: `docs/AUDIT-ARCHITECTURE-SCALABILITY-2026-02-21.md`, раздел 7–8.

---

## 1. Матрица кодов выхода

| Код | Значение | Когда использовать |
|-----|----------|---------------------|
| **0** | Success | Команда выполнена успешно. |
| **1** | Fatal error | Конфиг/окружение (нет .env, нет токена), аргументы (неверный формат даты, путь не существует при обязательном пути), инициализация API, прерывание из-за отсутствия данных для работы (нет экспортов для scan при обязательном шаге и т.п.). |
| **2** | Partial failure | Часть операций выполнена, часть — нет (например upload-all: часть загружена, часть с ошибкой). |
| **130** | Interrupted | Пользователь прервал выполнение (Ctrl+C). Обрабатывать в `if __name__ == "__main__"` через `sys.exit(130)` при `KeyboardInterrupt`. |

**Правило:** при любом фатальном сбое (невозможность выполнить команду) — `sys.exit(1)`. При «ничего не сделано, но это не ошибка» (например `upload-next` при пустой очереди) — допустимо `return` с кодом 0; при «сделано частично» — `sys.exit(2)` в конце команды, если это важно для оркестратора.

**Policy: «Нет данных» для шагов, которые обязаны что-то обработать:** если команда по смыслу пайплайна должна что-то найти и обработать (например `scan` — найти экспорты и отсканировать), то отсутствие данных трактуется как **fail шага** и даёт **exit 1**. Это не «пустое окно данных», а неуспех шага. Исключения: команды «выдать следующее / все» при пустой очереди (`upload-next`, `upload-all` без записей) — 0, т.к. «ничего к загрузке не было» считается нормальным исходом.

---

## 2. Где какой код ставить в main.py

### 2.1 Общие хелперы / вызываемые из нескольких мест

| Место | Текущее поведение | Рекомендация |
|-------|-------------------|--------------|
| `get_export_paths(source_filter)` при несуществующем пути | `click.echo(..., err=True); return []` | Оставить: возвращает пустой список, вызывающий код (scan) сам решает exit. |
| `_upload_video` — нет VK_ACCESS_TOKEN / VK_GROUP_ID / неверный VK_GROUP_ID / VKPublisherError | `click.echo(..., err=True); return` | Не менять здесь: хелпер не должен вызывать sys.exit. Вызывающие команды (upload_one, _upload_batch) должны проверять env/publisher до входа в цикл и там вызывать sys.exit(1). Либо _upload_video возвращает bool/результат, а команда решает exit. |
| `_upload_batch` — нет VK_ACCESS_TOKEN / VK_GROUP_ID / VKPublisherError | `click.echo(..., err=True); return` | Перед каждым `return` добавить `sys.exit(1)`, т.к. это фатальная ошибка для команды. |
| `_delete_from_vk_by_urls` | Нет exit, только echo | Не вызывать exit из хелпера; команды delete-from-vk / delete-skipped-from-vk в конце по факту (ok < len(parsed)) могут вызвать sys.exit(2). |

### 2.2 Команды по одной

| Команда | Ситуация | Текущее | Нужный код |
|---------|----------|---------|------------|
| **folders list** | Пустой маппинг | `return` | 0 (информация, не ошибка). |
| **folders set** | — | Нет выхода по ошибке | 0 при успехе. |
| **folders remove** | Маппинг не найден | `click.echo(..., err=True)` без exit | `sys.exit(1)` — «ресурс не найден» считаем фатальной ошибкой команды. |
| **scan** | Нет экспортов для сканирования | `click.echo(...); return` | `sys.exit(1)` — без экспортов команда не выполнила задачу. |
| **scan** | Неверный --since/--until | Уже `sys.exit(1)` | Оставить. |
| **stats** | — | Нет выхода по ошибке | 0. |
| **skip** | Нет --id/--file/--file-from | `click.echo(...); return` | `sys.exit(1)`. |
| **unskip** | Нет --id/--file/--file-from | `click.echo(...); return` | `sys.exit(1)`. |
| **delete-skipped-from-vk** | Нет записей с skip и URL | echo, return | 0 (не ошибка). |
| **delete-skipped-from-vk** | Нет VK_ACCESS_TOKEN / VKPublisherError | echo, return | `sys.exit(1)`. |
| **clear-skip-upload-state** | — | return | 0. |
| **delete-from-vk** | Нет --url/--urls-file | echo, return | `sys.exit(1)`. |
| **delete-from-vk** | Нет VK_ACCESS_TOKEN / VKPublisherError | echo, return | `sys.exit(1)`. |
| **upload-one** | Видео не найдено | echo, return | `sys.exit(1)`. |
| **upload-one** | Уже загружено / skip | echo, return | 0 (информация). |
| **upload-one** | Нет токена/группы/ошибка publisher | в _upload_video return | В upload_one после вызова _upload_video не проверяем результат; при переносе проверок в команду — при ошибке env/publisher `sys.exit(1)`. |
| **upload-next** | Нет не загруженных | echo, return | 0 (пустая очередь — не ошибка). |
| **upload-range** | Нет записей в диапазоне | echo, return | 0. |
| **upload-many** | Нет не загруженных | echo, return | 0. |
| **upload-all** | Нет не загруженных | echo, return | 0. |
| **recalc-titles** | Нет записей для пересчёта | echo, return | 0. |
| **update-vk-titles** | Нет VK_ACCESS_TOKEN / файл не найден | `sys.exit(1)` | Оставить. |
| **update-vk-titles** | Список ID пуст / нет загруженных в VK | return | 0 или 1: «нет загруженных» — разумно 0. |
| **update-vk-titles** | VKPublisherError | echo, return | `sys.exit(1)`. |

### 2.3 Partial failure (код 2)

- **upload-one**: если после вызова _upload_video загрузка не удалась (publisher.publish вернул None) — можно трактовать как partial и выходить с 2; текущая реализация не возвращает код из _upload_video. Предлагается: в upload_one не менять; в batch-командах — в конце, если `failed > 0`, вызывать `sys.exit(2)`.
- **upload_range / upload_many / upload_all**: в конце `_upload_batch` вывести summary; если `failed > 0`, то `sys.exit(2)`.
- **delete-from-vk / delete-skipped-from-vk**: если удалено меньше, чем запрошено (ошибки API), в конце `sys.exit(2)`.
- **update-vk-titles**: если обновлено меньше, чем количество записей с URL, в конце `sys.exit(2)`.

### 2.4 Interrupted (130)

В `if __name__ == "__main__":` обернуть вызов `cli()` в try/except: при `KeyboardInterrupt` вывести сообщение и `sys.exit(130)`.

---

## 3. Формат summary JSON

### 3.1 Назначение

- Единый машиночитаемый результат команды для логов пайплайна, алертов и последующего разбора.
- Один файл на запуск команды (или один объект в stdout при опции `--json`).

### 3.2 Схема (минимум)

```json
{
  "command": "scan",
  "exit_code": 0,
  "ts_end": "2026-02-21T12:00:00",
  "duration_sec": 12.3,
  "ok": true,
  "stats": {},
  "warnings": [],
  "errors": []
}
```

- **command** — имя команды (scan, upload-all, delete-from-vk, …).
- **exit_code** — итоговый код выхода (0, 1, 2, 130).
- **ts_end** — время завершения в ISO 8601.
- **duration_sec** — длительность выполнения в секундах (опционально, но полезно).
- **ok** — true только при exit_code === 0.
- **stats** — объект с метриками команды (см. ниже по командам).
- **warnings** — массив строк (некритичные предупреждения).
- **errors** — массив строк (сообщения об ошибках при partial/fatal).

### 3.3 stats по командам

| Команда | Пример stats |
|---------|----------------|
| scan | `{"added": 5, "duplicates": 2, "updated": 1, "skipped_date": 0, "export_paths": 3}` |
| stats | Текущий вывод get_statistics() как объект (total, uploaded, not_uploaded, skipped, channels, source_folders). |
| skip / unskip | `{"marked": 3}` (количество затронутых записей). |
| clear-skip-upload-state | `{"cleared": 15}`. |
| delete-from-vk / delete-skipped-from-vk | `{"requested": 5, "deleted": 4, "failed": 1}`. |
| upload-one | `{"uploaded": true/false, "video_id": 123, "video_url": "..." или null}`. |
| upload-next / upload-range / upload-many / upload-all | `{"total": 10, "successful": 8, "failed": 1, "skipped": 1}`. |
| recalc-titles | `{"processed": 100, "updated": 95, "skipped": 5}`. |
| update-vk-titles | `{"total": 20, "updated": 18, "failed": 2}`. |
| folders list/set/remove | Минимум: `{"action": "list"|"set"|"remove", "count": N}`. |

### 3.4 Места вывода summary

**Вариант A (рекомендуемый для Phase 1):**  
- В конце каждой команды писать один JSON-объект в файл `logs/summary_<command>_<timestamp>.json` (или проще: `logs/last_summary.json`, перезаписывать при каждом запуске).  
- Плюс: не меняется stdout, пайплайн может читать файл после вызова.  
- Минус: нужно знать путь к файлу (фиксированный, например `logs/last_summary.json`).

**Вариант B:**  
- Опция `--summary-file` (путь к файлу). Если задана — писать summary JSON в этот файл по завершении команды.  
- Без опции — не писать (обратная совместимость).

**Вариант C:**  
- Опция `--json`: при её наличии в конце команды выводить только summary JSON в stdout (без человекочитаемого вывода в stdout). Для пайплайнов: `python main.py scan --json > summary.json`.

**Рекомендация:**  
- Phase 1: **Вариант A** — всегда писать summary в `logs/last_summary.json` по завершении любой команды. Формат — один JSON-объект (как выше). Так оркестратор может единообразно читать результат без смены интерфейса CLI.  
- При желании позже добавить `--summary-file` или `--json` поверх того же формата.

### 3.5 Когда писать summary

- В конце обработки каждой команды (успех, partial, fatal).  
- При выходе через `sys.exit(1)` или `sys.exit(2)` — по возможности записать summary перед exit (например в atexit или явно в блоке except/перед sys.exit).  
- При `KeyboardInterrupt` — записать краткий summary с exit_code 130 и затем sys.exit(130).

---

## 4. Итоговый чеклист внедрения (Phase 1)

1. **Exit codes**  
   - Добавить константы: `EXIT_SUCCESS = 0`, `EXIT_FATAL = 1`, `EXIT_PARTIAL = 2`, `EXIT_INTERRUPTED = 130`.  
   - Во всех местах из таблицы 2.2 заменить «return после ошибки» на `sys.exit(1)` где указано.  
   - В _upload_batch в конце при `failed > 0` вызывать `sys.exit(2)`.  
   - В delete-from-vk/delete-skipped-from-vk при частичном успехе — `sys.exit(2)`.  
   - В update-vk-titles при частичном успехе — `sys.exit(2)`.  
   - В точке входа обработать KeyboardInterrupt и вызвать `sys.exit(130)`.

2. **Summary JSON**  
   - Ввести функцию `write_summary(command, exit_code, stats, warnings, errors, duration_sec=None)`, пишущую в `logs/last_summary.json`.  
   - В конце каждой команды формировать словарь stats и вызывать write_summary (при успехе exit_code=0, при partial=2, при fatal=1).  
   - Перед каждым sys.exit(1)/sys.exit(2) по возможности вызывать write_summary с соответствующим exit_code и затем exit.

3. **Документация**  
   - В USAGE.md добавить короткий раздел «Коды выхода» и «Summary JSON» со ссылкой на этот документ.

После подтверждения можно переходить к правкам в `main.py` и добавлению записи в `logs/last_summary.json` по этой спецификации.

---

## 4. Смоук-тесты (PowerShell)

Для проверки exit codes и summary см. чеклист в ревью (например `reviews/phase1-review-fixes-2026-02-21.md`). При генерации тестовых файлов (например `bad_ids.txt`) используйте **UTF-8 без BOM**, чтобы избежать ошибок парсинга:

```powershell
Set-Content logs\bad_ids.txt "1,abc,3" -Encoding utf8NoBOM
```

**Known unverified path:** сценарий `upload-one` → publish failed → EXIT_PARTIAL (2) проверяется при наличии незагруженного ID и настроенного VK env; при появлении подходящего ID — один тест для верификации.
