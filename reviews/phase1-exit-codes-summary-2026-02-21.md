# Review: Phase 1 — коды выхода и summary JSON

**Дата:** 2026-02-21  
**Контекст:** Аудит архитектуры (docs/AUDIT-ARCHITECTURE-SCALABILITY-2026-02-21.md), Phase 1: единая матрица exit codes, фатальные ошибки → non-zero exit, единый summary JSON на команду.

## Diff

```diff
diff --git a/docs/USAGE.md b/docs/USAGE.md
index 1cb18c1..0b7bda9 100644
--- a/docs/USAGE.md
+++ b/docs/USAGE.md
@@ -317,3 +317,18 @@ python main.py update-vk-titles --ids-file logs/titles_recalc_affected_ids.txt -
 ## Повторное сканирование
 
 Можно безопасно запускать сканирование повторно. Существующие видео будут обновлены (заголовок, описание), но статус загрузки сохранится.
+
+## Коды выхода и Summary JSON (для пайплайнов)
+
+CLI возвращает следующие коды выхода:
+
+| Код | Значение | Когда |
+|-----|----------|--------|
+| **0** | Успех | Команда выполнена успешно. |
+| **1** | Фатальная ошибка | Нет конфига/токена, неверные аргументы, нет данных для обязательного шага (например `scan` без экспортов). |
+| **2** | Частичный сбой | Часть операций выполнена, часть — нет (например загрузка: часть успешна, часть с ошибкой). |
+| **130** | Прервано | Пользователь нажал Ctrl+C. |
+
+Подробная матрица по командам и политика («нет данных» как fail шага) описаны в [docs/EXIT-CODES-AND-SUMMARY-SPEC.md](EXIT-CODES-AND-SUMMARY-SPEC.md).
+
+**Summary JSON** — после каждой команды результат записывается в `logs/last_summary.json`: код выхода, метрики (stats), предупреждения и ошибки. Формат и поля по командам см. в [EXIT-CODES-AND-SUMMARY-SPEC.md](EXIT-CODES-AND-SUMMARY-SPEC.md).
diff --git a/main.py b/main.py
index ce1cef6..79c3331 100644
--- a/main.py
+++ b/main.py
@@ -1,12 +1,14 @@
 """Точка входа CLI приложения."""
 
+import json
 import subprocess
 import sys
 import io
 import time
+from datetime import datetime, timezone
 from pathlib import Path
 import logging
-from typing import Optional
+from typing import Any, Optional
 
 import click
 
@@ -49,6 +51,41 @@ _PROJECT_ROOT = Path(__file__).resolve().parent
 # Рекомендуемая задержка между загрузками (VK API: лимит частоты, антибот). См. docs/USAGE.md
 DEFAULT_UPLOAD_DELAY = 15.0
 
+# Коды выхода (docs/EXIT-CODES-AND-SUMMARY-SPEC.md)
+EXIT_SUCCESS = 0
+EXIT_FATAL = 1
+EXIT_PARTIAL = 2
+EXIT_INTERRUPTED = 130
+
+SUMMARY_FILE = Path("logs/last_summary.json")
+
+
+def write_summary(
+    command: str,
+    exit_code: int,
+    stats: dict[str, Any],
+    warnings: list[str],
+    errors: list[str],
+    duration_sec: Optional[float] = None,
+) -> None:
+    """Записать итог команды в logs/last_summary.json для пайплайнов."""
+    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
+    payload = {
+        "command": command,
+        "exit_code": exit_code,
+        "ts_end": datetime.now(timezone.utc).isoformat(),
+        "ok": exit_code == EXIT_SUCCESS,
+        "stats": stats,
+        "warnings": warnings,
+        "errors": errors,
+    }
+    if duration_sec is not None:
+        payload["duration_sec"] = round(duration_sec, 2)
+    try:
+        SUMMARY_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
+    except Exception as e:
+        logger.warning("Не удалось записать summary: %s", e)
+
 
 def _refresh_vk_token_callback() -> Optional[str]:
```

Полный diff также сохранён в [phase1-exit-codes-summary.diff](phase1-exit-codes-summary.diff).