# -*- coding: utf-8 -*-
"""Общие вспомогательные функции для генераторов заголовков."""

import re


def first_two_sentences(text: str, max_length: int = 120) -> str:
    """Взять первые два предложения из текста (разделитель — точка с пробелом)."""
    text = text.strip()
    if not text:
        return ""
    parts = re.split(r"\.\s+", text)
    if len(parts) == 1:
        s = parts[0].strip()
        return (s + ".") if not s.endswith(".") else s
    two = (parts[0].strip() + ". " + parts[1].strip()).strip()
    if not two.endswith("."):
        two += "."
    if len(two) > max_length:
        two = two[: max_length - 3].rsplit(" ", 1)[0] + "..."
    return two
