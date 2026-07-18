# VK Video Publisher

Публикатор видео из экспорта Telegram Desktop (Windows) в VK Video.

## Описание

Проект предназначен для автоматизации публикации видео из экспортированных данных Telegram Desktop в VK Video. Поддерживает экспорты в форматах HTML и JSON, позволяет настраивать правила формирования заголовков и обрабатывает множественные экспорты одного канала.

## Возможности

- 📁 Парсинг экспортов Telegram (HTML и JSON форматы)
- 🎬 Автоматическое сопоставление сообщений и видеофайлов
- 📝 Настраиваемые генераторы заголовков
- 📅 Извлечение дат и описаний из сообщений
- 🚀 Публикация в VK Video через VK API
- 📊 Логирование и отчеты о процессе

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd VK_Importer
```

2. Создайте виртуальное окружение:
```bash
python -m venv venv
```

3. Активируйте виртуальное окружение:
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

4. Установите зависимости:
```bash
pip install -r requirements.txt
```

## Конфигурация

### Настройка переменных окружения

Создайте файл `.env` в корне проекта и укажите:

```env
VK_ACCESS_TOKEN=ваш_токен_доступа_vk_api
VK_GROUP_ID=id_вашей_группы
```

**Важно:** для загрузки видео в группу нужен пользовательский токен с правами `video`/`groups`, а не токен группы. Подробный разбор способов получения токена, ID группы и автообновления — в [docs/QUICKSTART.md](docs/QUICKSTART.md) и [docs/VK-TOKEN-REFRESH.md](docs/VK-TOKEN-REFRESH.md).

### Конфигурационный файл (опционально)

Для дополнительных настроек можно использовать `config/config.yaml`:
```bash
cp config/config.example.yaml config/config.yaml
```

## Использование

Система использует SQLite базу данных для отслеживания видео и их статуса загрузки.

### Быстрый старт

1. **Сканирование экспортов:**
   ```bash
   python main.py scan
   ```

2. **Проверка статистики:**
   ```bash
   python main.py stats
   ```

3. **Загрузка следующего видео:**
   ```bash
   python main.py upload-next
   ```

### Основные команды

- `scan` — сканировать экспорты и добавить видео в БД (`-s mapped` — все папки из маппинга, `--since`/`--until` — фильтр по дате)
- `stats` — статистика по видео в БД
- `folders list` / `folders set <путь> <курс>` / `folders remove <путь>` — маппинг папка → курс (без изменения кода)
- `recalc-titles` — пересчёт заголовков по правилам курса (`--channel` — только один канал)
- `update-vk-titles` — обновить заголовки в VK у уже загруженных видео (по списку ID)
- `upload-one <id>` — загрузить видео по ID
- `upload-next` — загрузить следующее не загруженное видео
- `upload-range <start_id>` — загрузить диапазон по ID
- `upload-many` — загрузить несколько не загруженных видео
- `upload-all` — загрузить все не загруженные видео

### Примеры

```bash
# Сканировать только экспорты ЕГЭ
python main.py scan --source ege

# Загрузить следующее видео из канала ЕГЭ
python main.py upload-next --channel ЕГЭ

# Загрузить 10 видео начиная с ID 100
python main.py upload-range 100 --count 10

# Загрузить все видео с задержкой 10 секунд
python main.py upload-all --delay 10
```

Подробное руководство: [docs/USAGE.md](docs/USAGE.md)

## Структура проекта

- `src/parsers/` - Парсеры экспортов Telegram (HTML, JSON)
- `src/title_generators/` - Генераторы заголовков для видео
- `src/models/` - Модели данных
- `src/publisher/` - Публикация в VK Video
- `src/adapters/` - Source/Destination адаптеры (унифицированный `ContentItem`, публикация через `VKDestinationAdapter`)
- `src/storage/` - Очередь задач (`JobQueue` поверх SQLite)
- `src/integrations/content_hub/` - канонический writepath: запись результата публикации в `content_hub.publication`/`link_map` только через `content_hub_client` (ContentBackbone), см. [TECH-SPEC-CURSOR-P0-VK-IMPORTER-CANONICAL-WRITEPATH-v1.md](docs/TECH-SPEC-CURSOR-P0-VK-IMPORTER-CANONICAL-WRITEPATH-v1.md) и [docs/CONTENT-HUB-RUNBOOK.md](docs/CONTENT-HUB-RUNBOOK.md)
- `src/utils/` - Вспомогательные утилиты
- `config/` - Конфигурационные файлы
- `tests/` - Тесты

## Разработка

Проект находится в активной разработке. См. [docs/PLAN.md](docs/PLAN.md) для плана внедрения.

## Документация

- [Быстрый старт](docs/QUICKSTART.md) — установка и настройка
- [Использование](docs/USAGE.md) — команды, фильтры, БД
- [Пайплайны (OpenClaw)](docs/PIPELINES.md) — запуск в скриптах и пайплайнах
- [Аудит пайплайнов и CLI](docs/AUDIT-PIPELINES-CLI.md) — полнота документации, логирование, коды выхода
- [План внедрения](docs/PLAN.md) — этапы разработки
- [Структура проекта](docs/PROJECT_STRUCTURE.md) — архитектура
- [Устранение неполадок](docs/troubleshooting.md) — типовые ошибки VK API и canonical write

## Лицензия

[Указать лицензию]
