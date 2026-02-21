# Review: Усиление правила review-changes

**Дата:** 2026-02-21  
**Контекст:** Правка `.cursor/rules/review-changes.mdc`: чтобы AI не забывал сохранять ревью после изменений кода, добавлены явный запрет завершать ответ без сохранения, обязательный чеклист и уточнения по сбору diff.

## Изменения

- В начало правила добавлен блок **«Критично: не завершай ответ без сохранения ревью»** — последний шаг перед ответом пользователю всегда сохранение review; не писать «Готово»/«Итог», пока не выполнены пункты.
- Добавлен **обязательный чеклист перед завершением ответа**: собрать diff (для новых файлов — `git add` + `git diff --cached`), сохранить .diff в reviews/, создать .md с заголовком, контекстом и ссылкой на .diff. Завершать ответ только после этого.
- В разделе «Как получить diff» явно указано: только изменённые — `git diff`; с новыми файлами — сначала `git add`, затем `git diff --cached`.
- Уточнены имена примеров (phase3-upload-partial-fix, phase1-exit-codes-summary) и формулировка «когда сохранять» (обязательно перед завершением ответа).

## Начало diff

```diff
diff --git a/.cursor/rules/review-changes.mdc b/.cursor/rules/review-changes.mdc
index 3c87247..abe7a2b 100644
--- a/.cursor/rules/review-changes.mdc
+++ b/.cursor/rules/review-changes.mdc
@@ -5,18 +5,36 @@ alwaysApply: true
...
```

## Diff

Полный diff: [review-changes-rule-update-2026-02-21.diff](review-changes-rule-update-2026-02-21.diff).
