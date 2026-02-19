# -*- coding: utf-8 -*-
"""Обмен кода на токены и обновление access_token. Поддерживаются VK ID (id.vk.ru) и классический OAuth (oauth.vk.com)."""

import json
import os
import ssl
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

VK_ID_TOKEN_URL = "https://id.vk.ru/oauth2/auth"
VK_OAUTH_ACCESS_TOKEN_URL = "https://oauth.vk.com/access_token"


def _ssl_context():
    """Контекст SSL для urlopen. При VK_SSL_VERIFY=0 отключает проверку (корпоративный прокси/антивирус)."""
    v = os.getenv("VK_SSL_VERIFY", "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


def exchange_code_for_tokens_oauth(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> dict:
    """Обмен code на токены через классический VK OAuth (oauth.vk.com). Без PKCE."""
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    url = VK_OAUTH_ACCESS_TOKEN_URL + "?" + urlencode(params)
    req = Request(url, method="GET")
    kwargs = {"timeout": 30}
    ctx = _ssl_context()
    if ctx is not None:
        kwargs["context"] = ctx
    with urlopen(req, **kwargs) as resp:
        return json.loads(resp.read().decode("utf-8"))


def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
    device_id: str,
    state: str,
) -> dict:
    """Обмен authorization code на токены (access_token, refresh_token)."""
    body = urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
        "device_id": device_id,
        "state": state,
    }).encode("utf-8")
    req = Request(
        VK_ID_TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    kwargs = {"timeout": 30}
    ctx = _ssl_context()
    if ctx is not None:
        kwargs["context"] = ctx
    with urlopen(req, **kwargs) as resp:
        return json.loads(resp.read().decode("utf-8"))


def refresh_token_request(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict:
    """Обмен refresh_token на новую пару access_token и refresh_token."""
    body = urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    req = Request(
        VK_ID_TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    kwargs = {"timeout": 30}
    ctx = _ssl_context()
    if ctx is not None:
        kwargs["context"] = ctx
    with urlopen(req, **kwargs) as resp:
        return json.loads(resp.read().decode("utf-8"))
