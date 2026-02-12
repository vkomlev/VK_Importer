# Быстрый старт

## Установка и настройка

1. **Активируйте виртуальное окружение:**

   Windows (PowerShell):
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

   Windows (CMD):
   ```cmd
   venv\Scripts\activate.bat
   ```

   Linux/Mac:
   ```bash
   source venv/bin/activate
   ```

2. **Установите зависимости:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Настройте конфигурацию:**

   ```bash
   cp config/config.example.yaml config/config.yaml
   ```

   Отредактируйте `config/config.yaml`:
   - Укажите токен доступа VK API
   - Настройте генератор заголовков
   - Укажите пути к экспортам Telegram

4. **Запустите приложение:**

   ```bash
   python main.py --help
   ```

## Структура экспорта Telegram

Проект ожидает следующую структуру экспорта Telegram Desktop:

### HTML формат:
```
telegram_export/
├── messages.html (или другие .html файлы)
└── files/
    ├── video1.mp4
    ├── video2.webm
    └── ...
```

### JSON формат:
```
telegram_export/
├── messages.json (или другие .json файлы)
└── files/
    ├── video1.mp4
    ├── video2.webm
    └── ...
```

## Получение токена VK API

1. Перейдите на https://vk.com/apps?act=manage
2. Создайте новое приложение типа "Веб-сайт"
3. Получите токен доступа с правами:
   - `video` - для загрузки видео
   - `groups` - если публикуете в группу

## Пример использования

```bash
# Публикация из указанного экспорта
python main.py --export-path telegram_exports/channel1

# Тестовый запуск без публикации
python main.py --export-path telegram_exports/channel1 --dry-run
```
