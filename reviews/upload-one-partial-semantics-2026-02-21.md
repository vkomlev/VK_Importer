# Review: upload-one — семантика EXIT_PARTIAL при ошибке публикации

**Дата:** 2026-02-21  
**Контекст:** Семантика кода выхода для upload-one при неудаче publisher.publish (возврат None): трактовать как операционную неудачу шага → EXIT_PARTIAL (2), а не как фатальную ошибку конфига/инициализации → EXIT_FATAL (1).

## Изменения

- Введена константа `UPLOAD_ERROR_PUBLISH_FAILED = "Ошибка загрузки"`; в `_upload_video` при `publish` → None возвращается эта строка.
- В `upload_one`: при `not ok and err` — если `err == UPLOAD_ERROR_PUBLISH_FAILED`, выходим с **EXIT_PARTIAL** и пишем summary с кодом 2; иначе (ошибка окружения/инициализации) — **EXIT_FATAL** и код 1.
- В batch-загрузке и в `_upload_video` для записи в БД используется та же константа.

## Diff

Полный diff: [upload-one-partial-semantics-2026-02-21.diff](upload-one-partial-semantics-2026-02-21.diff).
