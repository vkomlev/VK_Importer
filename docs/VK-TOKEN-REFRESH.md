# Автообновление VK access token

Токен пользователя VK истекает (например, раз в сутки или через 1 час при использовании VK ID). Скрипт `scripts/refresh_vk_token.py` обновляет токен по **refresh_token** и записывает новый `VK_ACCESS_TOKEN` в `.env`.

## Условия

- Обновление идёт через **VK ID** (id.vk.ru), метод `oauth2/auth` с `grant_type=refresh_token`.
- В `.env` должны быть:
  - **VK_CLIENT_ID**, **VK_CLIENT_SECRET** — из настроек приложения VK ID (у вас уже есть).
  - **VK_REFRESH_TOKEN** — выдан один раз при авторизации через VK ID (authorization code flow). Без него автообновление невозможно.

## Как получить токены один раз

Скрипт поддерживает **два варианта** OAuth:

- **Классический VK OAuth (oauth.vk.com)** — по умолчанию. Подходит для приложений, созданных в [VK для разработчиков](https://dev.vk.com/). Redirect URI в настройках приложения: `https://oauth.vk.com/blank.html`.
- **VK ID (id.vk.ru)** — для приложений, созданных в VK ID. В `.env` укажите `VK_OAUTH_ENDPOINT=id`.

### Шаги (классический OAuth, по умолчанию)

1. В [настройках приложения VK](https://dev.vk.com/apps?act=manage) укажите **Redirect URI**: `https://oauth.vk.com/blank.html`.
2. В `.env`: `VK_CLIENT_ID`, `VK_CLIENT_SECRET`, `VK_REDIRECT_URI=https://oauth.vk.com/blank.html`. При необходимости задайте `VK_SCOPE` (по умолчанию `groups,wall,video`).
3. Запустите:
   ```bash
   python scripts/get_vk_token_by_code.py
   ```
   Откроется браузер (ссылка вида `https://oauth.vk.com/authorize?client_id=...&display=page&redirect_uri=...&scope=...&response_type=code&v=5.199&state=...`). После входа вас перенаправит на пустую страницу — **скопируйте полный URL из адресной строки** и вставьте в терминал.
4. Скрипт обменяет код на токены и запишет в `.env`: **VK_ACCESS_TOKEN**, **VK_USER_TOKEN_EXPIRES_AT**, **VK_USER_ID**. Если в ответе будет **refresh_token** (зависит от типа приложения), он тоже сохранится.

**Примечание:** Токен, полученный через классический OAuth, может не поддерживать обновление через `refresh_vk_token.py` (он рассчитан на VK ID). Тогда при истечении токена нужно снова запустить `get_vk_token_by_code.py`.

**Ошибка SSL (CERTIFICATE_VERIFY_FAILED, self-signed certificate):** часто из-за корпоративного прокси или антивируса. Можно отключить проверку SSL для запросов к VK: в `.env` добавьте `VK_SSL_VERIFY=0` или перед запуском `set VK_SSL_VERIFY=0` (Windows) / `export VK_SSL_VERIFY=0` (Linux/macOS). Используйте только в доверенной сети.

## Использование скрипта

```bash
# Проверить, истекает ли токен в течение часа; если да — обновить и записать в .env
python scripts/refresh_vk_token.py

# Обновить, если до истечения меньше 30 минут
python scripts/refresh_vk_token.py --expires-within 30

# Обновить принудительно
python scripts/refresh_vk_token.py --force
```

Скрипт обновляет в `.env`:

- **VK_ACCESS_TOKEN** — новый access token
- **VK_USER_TOKEN_EXPIRES_AT** — Unix-время истечения (текущее время + expires_in из ответа)
- **VK_USER_ID** — идентификатор пользователя (если пришёл в ответе)
- **VK_REFRESH_TOKEN** — новый refresh token (если пришёл в ответе; старый после обмена недействителен)

## Пайплайны

Перед шагами, которые вызывают VK API (загрузка видео, обновление заголовков в VK), можно вызывать:

```bash
python scripts/refresh_vk_token.py
```

Если токен ещё действителен (до истечения больше порога), скрипт ничего не меняет и завершается с кодом 0.
