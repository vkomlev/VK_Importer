# Review: Пайплайн — путь к БД и preflight для шага «Select eligible IDs by policy»

**Дата:** 2026-02-21  
**Контекст:** P1: при запуске из OpenClaw шаг падал с `no such table: videos`, т.к. inline Python подключался к `videos.db` без учёта cwd и создавал пустой файл в директории раннера. Требовалось: фиксировать путь к БД, не создавать пустую БД, preflight схемы, логирование.

## Изменения (scripts/run_tg_vk_video_pipeline.ps1)

### 1. Подключение к БД
- **Вариант A:** перед inline Python выполняется `Push-Location $vkRoot`, после шага — `Pop-Location` в `finally`.
- **Вариант B:** абсолютный путь к БД передаётся в Python через `$env:VK_IMPORTER_DB` (формируется из `$vkRoot\videos.db`). Python читает `os.environ.get('VK_IMPORTER_DB')` и открывает именно этот путь.

### 2. Отсутствие silent-создания пустой БД
- Подключение к БД в Python переведено на URI: `sqlite3.connect(uri, uri=True)` с `uri = 'file:' + path + '?mode=rw'`. Режим `mode=rw` не создаёт файл; при неверном/отсутствующем пути — явная ошибка «DB path invalid or cannot open in rw mode» (в stderr с путём и cwd), без `no such table`.

### 3. Preflight-проверка схемы
- Перед SELECT выполняется `SELECT name FROM sqlite_master WHERE type='table' AND name='videos'`. Если таблицы нет — в stderr выводится сообщение с `db_path` и `cwd`, затем `sys.exit(1)`.

### 4. Логирование шага
- В лог перед запуском Python пишутся: `pwd`, абсолютный путь к БД (`db_path`), факт существования файла (`db_exists`). В логе пайплайна явно виден путь вида `D:\work\VK_Importer\videos.db`.

## Критерии приёмки

1. Пайплайн из OpenClaw проходит шаг «Select eligible IDs by policy» без `no such table`.
2. В логе явно виден путь к БД (например `D:\work\VK_Importer\videos.db`).
3. При намеренно неверном пути шаг падает с понятной ошибкой (DB path invalid / cannot open in rw mode), а не с `no such table`.
4. Повторный прогон не создаёт «левые» `videos.db` в сторонних рабочих директориях (cwd фиксирован через Push-Location, путь к БД — абсолютный).

## Diff

[pipeline-db-path-and-preflight-2026-02-21.diff](pipeline-db-path-and-preflight-2026-02-21.diff)
