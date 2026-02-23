# Review: VK preflight и fail-fast по 1051

**Дата:** 2026-02-21  
**Контекст:** P1: при VK API 1051 (метод недоступен для профиля/токена) пайплайн не должен молотить все ID; нужны preflight до batch, fail-fast при 1051 в цикле, безопасное логирование конфига.

## Изменения

### 1. Preflight VK перед этапом «Publish eligible IDs»
- **main.py**: команда `vk-preflight` — создаёт publisher (group_id_required=True), вызывает `publisher.check_video_access()` (video.get в контексте группы). При FatalUploadError или VKApi1051Error — вывод в stderr, summary, exit 1.
- **src/publisher/vk_publisher.py**: метод `check_video_access()` — вызов `vk.video.get(owner_id=-group_id, count=1)`; при ApiError 1051 бросает `VKApi1051Error`.
- **scripts/run_tg_vk_video_pipeline.ps1**: шаг «Preflight VK video» перед «Publish eligible IDs» — `Run-Cmd $vkPy main.py vk-preflight $vkRoot`. При неуспехе пайплайн падает до цикла загрузки.

### 2. Fail-fast по 1051 в публикации
- **src/publisher/vk_publisher.py**: класс `VKApi1051Error`; в `publish()` при ApiError 1051 — сразу `raise VKApi1051Error` (без ретраев).
- **src/adapters/destinations/vk.py**: в `publish()` перехват `VKApi1051Error`, возврат `PublicationResult(ok=False, error_code="VK_API_1051")`.
- **main.py**: константа `EXIT_VK_CONTEXT = 3`; в `upload_one` при `err == "VK_API_1051"` — `write_summary(..., EXIT_VK_CONTEXT)` и `sys.exit(3)`.
- **Пайплайн**: в цикле «Publish eligible IDs» после каждого `upload-one` проверка `$LASTEXITCODE -eq 3`; при 3 — лог «VK API 1051: stop batch», throw с сообщением о перевыпуске токена (user OAuth, право video). Цикл больше не продолжается.

### 3. Валидация/логирование конфига токена
- **src/app_context.py**: при создании publisher (если задан group_id) логируется строка: `group_id=... (токен — user OAuth с правом video, не сервисный ключ)` — без вывода самого токена.

### 4. Документация
- **docs/EXIT-CODES-AND-SUMMARY-SPEC.md**: в матрицу кодов добавлен код **3** — VK context (1051), использование в upload-one для fail-fast в пайплайне.

## Критерии приёмки

1. Пайплайн выполняет шаг «Preflight VK video» до цикла; при 1051 пайплайн завершается с ошибкой до загрузки.
2. При 1051 на первом же `upload-one` цикл прерывается (exit 3 → throw в пайплайне), остальные ID не обрабатываются.
3. В логах виден group_id и напоминание про user OAuth/video (без токена).
4. Операционный фикс: перевыпуск токена в нужном приложении/потоке и повторный прогон preflight — на стороне оператора.

## Diff

[vk-preflight-and-failfast-1051-2026-02-21.diff](vk-preflight-and-failfast-1051-2026-02-21.diff)
