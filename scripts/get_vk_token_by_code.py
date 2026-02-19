# -*- coding: utf-8 -*-
"""
Первое получение access_token (и при возможности refresh_token) по коду авторизации VK.

Поддерживаются:
- Классический OAuth (oauth.vk.com) — для приложений, зарегистрированных в VK (рекомендуется).
- VK ID (id.vk.ru) — для приложений в VK ID; требует PKCE и настройки redirect_uri в VK ID.

Открывает браузер, после редиректа нужно вставить в терминал полный URL из адресной строки.

В .env: VK_CLIENT_ID, VK_CLIENT_SECRET, VK_REDIRECT_URI (например https://oauth.vk.com/blank.html).
Опционально: VK_OAUTH_ENDPOINT=classic (по умолчанию) или id; VK_SCOPE (например video,offline или groups,wall,video).

Запуск: python scripts/get_vk_token_by_code.py
"""

import hashlib
import base64
import os
import random
import string
import sys
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qs

# Корень проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.vk_token_refresh import exchange_code_for_tokens, exchange_code_for_tokens_oauth

ENV_PATH = PROJECT_ROOT / ".env"
VK_OAUTH_AUTHORIZE_URL = "https://oauth.vk.com/authorize"
VK_ID_AUTHORIZE_URL = "https://id.vk.ru/authorize"


def _params_from_url(url_or_fragment: str) -> dict:
    """Извлечь query/fragment параметры из строки (полный URL или только fragment)."""
    s = url_or_fragment.strip()
    if not s:
        return {}
    if s.startswith("http://") or s.startswith("https://"):
        parsed = urlparse(s)
        q = parse_qs(parsed.query)
        f = parse_qs(parsed.fragment) if parsed.fragment else {}
        return {k: (v[0] if v else "") for k, v in {**q, **f}.items()}
    if "?" in s:
        s = s.split("?", 1)[1]
    if "#" in s:
        s = s.split("#", 1)[1]
    return {k: (v[0] if v else "") for k, v in parse_qs(s).items()}


def load_env() -> dict[str, str]:
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


def get_stripped(env: dict[str, str], key: str) -> str:
    v = env.get(key, "").strip()
    if v.startswith('"') and v.endswith('"'):
        v = v[1:-1]
    elif v.startswith("'") and v.endswith("'"):
        v = v[1:-1]
    return v


def save_env(env: dict[str, str]) -> None:
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
    for key in ["VK_REFRESH_TOKEN", "VK_USER_TOKEN_EXPIRES_AT", "VK_USER_ID", "VK_ACCESS_TOKEN", "VK_GROUP_ID"]:
        if key in env and key not in written:
            val = env[key]
            if "\n" in val or "\r" in val:
                val = val.replace("\r", "").replace("\n", " ")
            new_lines.append(f"{key}={val}\n")
            written.add(key)
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def pkce_code_verifier(length: int = 64) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits + "_-", k=length))


def pkce_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")


def main():
    env = load_env()
    # Чтобы vk_token_refresh видел VK_SSL_VERIFY (для отключения проверки SSL)
    if "VK_SSL_VERIFY" in env:
        os.environ["VK_SSL_VERIFY"] = get_stripped(env, "VK_SSL_VERIFY")

    client_id = get_stripped(env, "VK_CLIENT_ID")
    client_secret = get_stripped(env, "VK_CLIENT_SECRET")
    redirect_uri = get_stripped(env, "VK_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        print("В .env задайте VK_CLIENT_ID, VK_CLIENT_SECRET и VK_REDIRECT_URI (например https://oauth.vk.com/blank.html).", file=sys.stderr)
        sys.exit(1)

    use_classic = (get_stripped(env, "VK_OAUTH_ENDPOINT") or "classic").strip().lower() == "classic"
    state = "".join(random.choices(string.ascii_letters + string.digits, k=32))
    scope = get_stripped(env, "VK_SCOPE") or ("groups,wall,video" if use_classic else "video,offline")

    if use_classic:
        # Классический OAuth (oauth.vk.com): без PKCE, с display и v
        auth_params = {
            "client_id": client_id,
            "display": "page",
            "redirect_uri": redirect_uri,
            "scope": scope,
            "response_type": "code",
            "v": "5.199",
            "state": state,
        }
        auth_url = VK_OAUTH_AUTHORIZE_URL + "?" + urlencode(auth_params)
        oauth_label = "VK OAuth (oauth.vk.com)"
    else:
        # VK ID (id.vk.ru): с PKCE
        code_verifier = pkce_code_verifier()
        code_challenge = pkce_code_challenge(code_verifier)
        auth_params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        auth_url = VK_ID_AUTHORIZE_URL + "?" + urlencode(auth_params)
        oauth_label = "VK ID (id.vk.ru)"

    import webbrowser
    print(f"Открываю браузер для авторизации ({oauth_label})...")
    webbrowser.open(auth_url)
    print()
    print("После входа вас перенаправит на страницу с пустым адресом (например oauth.vk.com/blank.html).")
    print("Скопируйте ПОЛНЫЙ URL из адресной строки браузера и вставьте сюда.")
    print()
    try:
        pasted = input("Вставьте URL редиректа: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("Прервано.", file=sys.stderr)
        sys.exit(1)

    params = _params_from_url(pasted)
    code = params.get("code") or ""
    state_back = params.get("state") or ""
    if not code:
        print("В вставленной строке не найден параметр code. Убедитесь, что копируете полный URL после редиректа.", file=sys.stderr)
        sys.exit(1)
    if state_back != state:
        print("state в ответе не совпал. Возможна подмена.", file=sys.stderr)
        sys.exit(1)

    try:
        if use_classic:
            data = exchange_code_for_tokens_oauth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                code=code,
            )
        else:
            device_id = params.get("device_id") or ""
            data = exchange_code_for_tokens(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                code=code,
                code_verifier=code_verifier,
                device_id=device_id,
                state=state_back,
            )
    except Exception as e:
        print(f"Ошибка обмена кода на токены: {e}", file=sys.stderr)
        sys.exit(1)

    if data.get("error"):
        print(f"Ошибка VK: {data.get('error_description', data.get('error', 'unknown'))}", file=sys.stderr)
        sys.exit(1)

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    if not access_token:
        print("В ответе VK нет access_token.", file=sys.stderr)
        sys.exit(1)

    import time
    expires_in = data.get("expires_in", 3600)
    if isinstance(expires_in, str):
        try:
            expires_in = int(expires_in)
        except ValueError:
            expires_in = 3600
    env["VK_ACCESS_TOKEN"] = access_token
    env["VK_USER_TOKEN_EXPIRES_AT"] = str(int(time.time()) + int(expires_in))
    env["VK_USER_ID"] = str(data.get("user_id") or "")
    if refresh_token:
        env["VK_REFRESH_TOKEN"] = refresh_token
    save_env(env)
    print("Токены записаны в .env: VK_ACCESS_TOKEN, VK_USER_TOKEN_EXPIRES_AT, VK_USER_ID, VK_REFRESH_TOKEN.")


if __name__ == "__main__":
    main()
