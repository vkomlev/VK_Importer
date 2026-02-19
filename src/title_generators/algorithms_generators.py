# -*- coding: utf-8 -*-
"""Генераторы заголовков для курса «Алгоритмы и структуры данных»."""

import re
from .base import BaseTitleGenerator
from ..models.video import VideoData

PREFIX = "Алгоритмы и структуры данных. "
MAX_TITLE_LEN = 100


class AlgorithmsAutoTitleGenerator(BaseTitleGenerator):
    """Генератор заголовков для курса «Алгоритмы и структуры данных».

    Использует первую строку описания; для «Задание X.Y» — форматирует отдельно.
    """

    def generate(self, video: VideoData) -> str:
        description = (video.description or "").strip()
        first_line = description.split("\n")[0].strip() if description else ""

        if first_line:
            # Задание N или Задание N.M (темы/блока Z)
            m = re.match(
                r"Задание\s+(\d+(?:\.\d+)?)(?:\s+темы\s+(.+?))?(?:\.|$)",
                first_line,
                re.IGNORECASE,
            )
            if not m:
                m = re.match(
                    r"Задание\s+(\d+(?:\.\d+)?)\s+блока\s+[«\"]?(.+?)[»\"]?(?:\.|$)",
                    first_line,
                    re.IGNORECASE,
                )
            if m:
                num, theme = m.group(1), (m.group(2) or "").strip()
                if theme:
                    return f"{PREFIX}Задание {num} ({theme})"
                return f"{PREFIX}Задание {num}"

            # Обычная тема: первая строка как заголовок
            title = first_line
            if len(title) > MAX_TITLE_LEN - len(PREFIX):
                title = title[: MAX_TITLE_LEN - len(PREFIX) - 3].rsplit(" ", 1)[0] + "..."
            return PREFIX + title

        # Нет описания — заголовок из stem
        stem = video.file_path.stem
        # Формат "2.4" или "2.4 a7edf3" (номер с хешем) — просто "Задание 2.4"
        m = re.match(r"^(\d+\.\d+)\s*[a-fA-F0-9]*$", stem)
        if m:
            return f"{PREFIX}Задание {m.group(1)}"
        m = re.match(r"^\d+_?(.+)$", stem)
        if m:
            rest = m.group(1)
            if "_" in rest and re.search(r"\d{2}_\d{2}_\d{2}", rest):
                return f"{PREFIX}Урок (запись)"
            if len(rest) <= 50:
                return PREFIX + rest.replace("_", " ")
        if len(stem) > 50:
            return f"{PREFIX}Урок (запись)"
        return PREFIX + stem.replace("_", " ")

    def get_name(self) -> str:
        return "algorithms_auto"
