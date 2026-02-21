# Review: Phase 1 — исправления по коду ревью

**Дата:** 2026-02-21  
**Контекст:** Исправления по замечаниям ревью Phase 1 (exit codes + summary): upload-one не должен выходить 0 при фатальной ошибке окружения/API; batch-upload при фатальной ошибке должен писать summary перед выходом; Ctrl+C — ловить также click.Abort; update-vk-titles — обрабатывать битый формат ID; delete-from-vk/delete-skipped-from-vk при нуле разобранных URL — EXIT_FATAL.

## Основные изменения

- **upload-one**: `_upload_video` возвращает `(bool, Optional[str])`; при ошибке окружения/API в `upload_one` пишется summary с EXIT_FATAL и `sys.exit(EXIT_FATAL)`.
- **batch-upload**: введён `FatalUploadError`; `_upload_batch` при ошибке окружения выбрасывает исключение; в upload-next/range/many/all — `try/except FatalUploadError` с записью summary и exit 1.
- **Ctrl+C**: в `__main__` перехват `(KeyboardInterrupt, click.Abort)` и выход 130 с summary.
- **update-vk-titles**: парсинг ID в `try/except ValueError`; при ошибке — EXIT_FATAL и summary.
- **delete-from-vk / delete-skipped-from-vk**: при `requested == 0` и непустом списке URL — EXIT_FATAL и сообщение «Ни один URL не удалось разобрать».

## Diff

Полный вывод `git diff` сохранён в [phase1-review-fixes-2026-02-21.diff](phase1-review-fixes-2026-02-21.diff).

Начало diff (структура):

```diff
diff --git a/docs/USAGE.md b/docs/USAGE.md
diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -49,6 +51,49 @@
+EXIT_SUCCESS = 0
+...
+class FatalUploadError(Exception):
+def write_summary(...):
...
```

Применить: `git apply reviews/phase1-review-fixes-2026-02-21.diff` (из корня репозитория).
