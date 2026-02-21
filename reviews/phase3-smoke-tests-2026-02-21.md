# Review: Phase 3 — смоук-тесты

**Дата:** 2026-02-21  
**Контекст:** Минимальный набор смоук-тестов для Phase 3: проверка, что существующий флоу не сломан и адаптеры работают; проверка summary после команд.

## Изменения

### 1. Документация
- **docs/PHASE3-SMOKE-TESTS.md** (новый): чеклист из 7 тестов (CLI, scan, upload-one not found, upload-next, upload-one partial, py_compile, summary); описание теста 5 (partial = exit 2) и вариантов A/B; блок проверки summary; ссылка на скрипт и ручной запуск в PowerShell.

### 2. Скрипт автоматического прогона
- **scripts/smoke-phase3.ps1** (новый): запуск тестов 1–4 и 6 из корня репозитория; опционально тест 5 через `-UploadOneId <id>`. Использует `Start-Process -Wait -PassThru` для корректного exit code; проверка summary через `Assert-Summary` (путь к `logs/last_summary.json`, UTF8). Все 6 прогонов успешны при текущем состоянии репозитория.

## Начало diff

```diff
diff --git a/docs/PHASE3-SMOKE-TESTS.md b/docs/PHASE3-SMOKE-TESTS.md
new file mode 100644
...
diff --git a/scripts/smoke-phase3.ps1 b/scripts/smoke-phase3.ps1
new file mode 100644
...
```

## Diff

Полный diff: [phase3-smoke-tests-2026-02-21.diff](phase3-smoke-tests-2026-02-21.diff).
