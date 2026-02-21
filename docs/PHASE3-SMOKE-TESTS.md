# Phase 3: смоук-тесты

Минимальный набор проверок, что Phase 3 не сломал существующий флоу и адаптеры работают.

## Чеклист

| # | Тест | Команда / действие | Ожидание |
|---|------|-------------------|----------|
| 1 | Базовый CLI | `python main.py --help` | Команда отрабатывает, есть все subcommands. |
| 2 | Регресс scan | `python main.py scan --source "Z:\not-exists"` | `exit 1`, summary с `command=scan`, `ok=false`. |
| 3 | Регресс upload-one (not found) | `python main.py upload-one 999999999` | `exit 1`, `command=upload-one`, `ok=false`. |
| 4 | Регресс upload-next (пустая очередь) | `python main.py upload-next` | `exit 0` (при пустой очереди), summary корректный. |
| 5 | Ошибка публикации = partial | `python main.py upload-one <id>` при сценарии fail publish | `exit 2`, не `1`; в `errors` код/текст публикации (PUBLISH_FAILED / NO_VIDEO). |
| 6 | Импорт/синтаксис адаптеров | `python -m py_compile main.py src/models/content.py src/adapters/base.py src/adapters/destinations/vk.py src/adapters/sources/export_fs.py` | Успешная компиляция (exit 0). |
| 7 | Summary после команд | После каждого теста читать `logs/last_summary.json` | Поля `command`, `exit_code`, `ok`, `stats`, `errors` заполнены согласованно. |

## Скрипт: автоматический прогон

Из корня репозитория:

```powershell
.\scripts\smoke-phase3.ps1
```

Проверяет тесты 1–4 и 6 (тест 5 — опционально: `.\scripts\smoke-phase3.ps1 -UploadOneId <id>` при сценарии fail publish). Использует `Start-Process -Wait -PassThru` для корректного получения exit code.

## PowerShell: ручной запуск тестов 1–4 и 6

```powershell
$ErrorActionPreference = "Stop"
cd d:\Work\VK_Importer

# 1. CLI
python main.py --help
if ($LASTEXITCODE -ne 0) { throw "Test 1 failed" }

# 2. scan
python main.py scan --source "Z:\not-exists"
if ($LASTEXITCODE -ne 1) { throw "Test 2: expected exit 1" }
$s = Get-Content logs/last_summary.json -Raw | ConvertFrom-Json
if ($s.command -ne "scan" -or $s.ok -ne $false) { throw "Test 2: bad summary" }

# 3. upload-one not found
python main.py upload-one 999999999
if ($LASTEXITCODE -ne 1) { throw "Test 3: expected exit 1" }
$s = Get-Content logs/last_summary.json -Raw | ConvertFrom-Json
if ($s.command -ne "upload-one" -or $s.ok -ne $false) { throw "Test 3: bad summary" }

# 4. upload-next (пустая очередь или успех одного — оба дают exit 0)
python main.py upload-next
if ($LASTEXITCODE -ne 0) { throw "Test 4: expected exit 0" }
$s = Get-Content logs/last_summary.json -Raw | ConvertFrom-Json
if ($s.command -ne "upload-next") { throw "Test 4: bad summary" }

# 6. py_compile
python -m py_compile main.py src/models/content.py src/adapters/base.py src/adapters/destinations/vk.py src/adapters/sources/export_fs.py
if ($LASTEXITCODE -ne 0) { throw "Test 6 failed" }

Write-Host "Tests 1,2,3,4,6 OK"
```

## Тест 5 (partial = exit 2)

Требуется сценарий, когда публикация одного элемента не удаётся (не фатальная ошибка конфига):

- **Вариант A:** запись есть, но файл отсутствует (удалён/переименован) → адаптер вернёт `NO_VIDEO` → `upload-one` должен дать **exit 2** и в summary `errors` — код/текст.
- **Вариант B:** запись есть, файл есть, но VK API возвращает ошибку (сеть отключена, неверный токен после старта и т.п.) → `PUBLISH_FAILED` → **exit 2**.

Проверка после теста 5: `logs/last_summary.json` содержит `exit_code: 2`, `ok: false`, в `errors` — непусто.

## Проверка summary (тест 7)

После любой команды, пишущей summary:

```powershell
$s = Get-Content logs/last_summary.json -Raw | ConvertFrom-Json
$s | Select-Object command, exit_code, ok, stats, errors
```

Ожидание: `command` совпадает с выполненной командой, `exit_code` — 0/1/2, `ok` = (exit_code == 0), `stats` — объект, `errors` — массив (может быть пустым).
