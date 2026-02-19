# -*- coding: utf-8 -*-
"""
Обновление VK access token по refresh_token (VK ID, id.vk.ru).

Требуется в .env:
  VK_CLIENT_ID, VK_CLIENT_SECRET — из настроек приложения VK ID.
  VK_REFRESH_TOKEN — получить один раз через OAuth (authorization code flow),
    затем скрипт будет обновлять его вместе с access_token.
  VK_ACCESS_TOKEN, VK_USER_TOKEN_EXPIRES_AT, VK_USER_ID — заполняются скриптом.

Если токен ещё действителен и до истечения больше порога (по умолчанию 1 час),
обновление не выполняется. Иначе запрос к id.vk.ru/oauth2/auth (grant_type=refresh_token),
запись новых значений в .env.

Запуск: python scripts/refresh_vk_token.py [--force] [--expires-within 60]
"""

import argparse
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError

# Корень проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))
from src.utils.vk_token_refresh import refresh_token_request

ENV_PATH = PROJECT_ROOT / ".env"

# Порог: обновлять, если до истечения меньше N минут
DEFAULT_EXPIRES_WITHIN_MINUTES = 60


def load_env() -> dict[str, str]:
    """Загрузить .env в словарь (без изменений значений)."""
    env = {}
    if not ENV_PATH.exists():
        return env
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.rstrip("\n")
    return env


def save_env(env: dict[str, str]) -> None:
    """Обновить значения в .env по словарю env, дописать ключи, которых нет в файле."""
    written = set()
    new_lines = []
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    key = line.split("=", 1)[0].strip()
                    if key in env:
                        val = env[key]
                        if "\n" in val or "\r" in val:
                            val = val.replace("\r", "").replace("\n", " ")
                        new_lines.append(f"{key}={val}\n")
                        written.add(key)
                        continue
                new_lines.append(line)
    append_order = [
        "VK_REFRESH_TOKEN", "VK_USER_TOKEN_EXPIRES_AT", "VK_USER_ID",
        "VK_ACCESS_TOKEN", "VK_GROUP_ID",
    ]
    for key in append_order:
        if key in env and key not in written:
            val = env[key]
            if "\n" in val or "\r" in val:
                val = val.replace("\r", "").replace("\n", " ")
            new_lines.append(f"{key}={val}\n")
            written.add(key)
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def get_stripped(env: dict[str, str], key: str) -> str:
    v = env.get(key, "").strip()
    if v.startswith('"') and v.endswith('"'):
        v = v[1:-1]
    elif v.startswith("'") and v.endswith("'"):
        v = v[1:-1]
    return v




def is_token_expiring_soon(expires_at_str: str, within_minutes: int) -> bool:
    """True, если токен истекает в течение within_minutes минут или уже истёк."""
    if not expires_at_str or not expires_at_str.strip():
        return True  # неизвестно — считаем, что пора обновить
    try:
        ts = int(expires_at_str.strip())
    except ValueError:
        return True
    return time.time() >= ts - within_minutes * 60


def main():
    parser = argparse.ArgumentParser(description="Обновление VK access token по refresh_token")
    parser.add_argument("--force", action="store_true", help="Обновить токен в любом случае")
    parser.add_argument(
        "--expires-within",
        type=int,
        default=DEFAULT_EXPIRES_WITHIN_MINUTES,
        metavar="MINUTES",
        help=f"Обновлять, если до истечения меньше N минут (по умолчанию {DEFAULT_EXPIRES_WITHIN_MINUTES})",
    )
    args = parser.parse_args()

    env = load_env()
    if "VK_SSL_VERIFY" in env:
        os.environ["VK_SSL_VERIFY"] = get_stripped(env, "VK_SSL_VERIFY")

    client_id = get_stripped(env, "VK_CLIENT_ID")
    client_secret = get_stripped(env, "VK_CLIENT_SECRET")
    refresh_tok = get_stripped(env, "VK_REFRESH_TOKEN")
    expires_at = get_stripped(env, "VK_USER_TOKEN_EXPIRES_AT")

    if not client_id or not client_secret:
        print("Ошибка: в .env должны быть заданы VK_CLIENT_ID и VK_CLIENT_SECRET.", file=sys.stderr)
        sys.exit(1)

    if not refresh_tok:
        print(
            "VK_REFRESH_TOKEN не задан. Получите refresh_token один раз через OAuth VK ID\n"
            "(authorization code flow), затем добавьте в .env строку VK_REFRESH_TOKEN=...\n"
            "После этого скрипт сможет автоматически обновлять access_token.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.force and not is_token_expiring_soon(expires_at, args.expires_within):
        print("Токен ещё действителен, обновление не требуется.")
        return

    try:
        data = refresh_token_request(client_id, client_secret, refresh_tok)
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Ошибка VK ID: {e.code} — {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Ошибка запроса: {e}", file=sys.stderr)
        sys.exit(1)

    access_token = data.get("access_token")
    new_refresh = data.get("refresh_token")
    expires_in = data.get("expires_in", 3600)
    user_id = data.get("user_id", "")

    if not access_token:
        print("В ответе VK нет access_token.", file=sys.stderr)
        sys.exit(1)

    expires_at_new = str(int(time.time()) + int(expires_in))
    env["VK_ACCESS_TOKEN"] = access_token
    env["VK_USER_TOKEN_EXPIRES_AT"] = expires_at_new
    env["VK_USER_ID"] = str(user_id) if user_id else env.get("VK_USER_ID", "")
    if new_refresh:
        env["VK_REFRESH_TOKEN"] = new_refresh

    save_env(env)
    print("Токен обновлён и записан в .env (VK_ACCESS_TOKEN, VK_USER_TOKEN_EXPIRES_AT, VK_USER_ID).")


if __name__ == "__main__":
    main()
