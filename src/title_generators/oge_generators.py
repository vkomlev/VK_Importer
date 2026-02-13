"""Генераторы заголовков для канала ОГЭ по информатике."""

import re
from typing import Optional

from .base import BaseTitleGenerator
from ..models.video import VideoData

PREFIX = "Курс ОГЭ по информатике"


class OGETopicTitleGenerator(BaseTitleGenerator):
    """Генератор заголовков для разбора тем ОГЭ."""

    def generate(self, video: VideoData) -> str:
        description = video.description.strip()
        if not description:
            return video.file_path.stem

        first_line = description.split("\n")[0].strip()
        first_line_lower = first_line.lower()

        lesson_match = re.search(r"урок\s+(\d+[._]\d+)\.\s*(.+?)(?:\.|$)", first_line, re.IGNORECASE)
        if lesson_match:
            lesson_num = lesson_match.group(1).replace(".", "_")
            topic = lesson_match.group(2).strip()
            if topic and len(topic) > 3:
                return f'{PREFIX}. Урок {lesson_num}. Разбираем тему "{topic}"'

        lesson_match = re.search(r"урок\s+(\d+)\.\s*(.+?)(?:\.|$)", first_line, re.IGNORECASE)
        if lesson_match:
            lesson_num = lesson_match.group(1)
            topic = lesson_match.group(2).strip()
            if topic and len(topic) > 3:
                return f'{PREFIX}. Урок {lesson_num}. Разбираем тему "{topic}"'

        task_topic_match = re.search(
            r"разбор\s+задани[ий]\s+\d+\.\s*(.+?)(?:\.|$)", first_line, re.IGNORECASE
        )
        if task_topic_match:
            topic = task_topic_match.group(1).strip()
            if topic and len(topic) > 3:
                return f'{PREFIX}. Разбираем тему "{topic}"'

        task_match = re.search(
            r"задание\s+\d+\.\s*(.+?)(?:\.|$)", first_line, re.IGNORECASE
        )
        if task_match:
            topic = task_match.group(1).strip()
            if topic and len(topic) > 3:
                return f'{PREFIX}. Разбираем тему "{topic}"'

        if "термин" in first_line_lower and "теори" in first_line_lower:
            topic_match = re.search(
                r"термин[ы]?\s+и\s+теори[ия]\s+задани[яе]\s+\d+\.\s*(.+?)(?:\.|$)",
                first_line,
                re.IGNORECASE,
            )
            if topic_match:
                topic = topic_match.group(1).strip()
                if topic and len(topic) > 3:
                    return f'{PREFIX}. Разбираем тему "{topic}"'

        return f"{PREFIX}. {video.file_path.stem}"

    def get_name(self) -> str:
        return "oge_topic"


class OGETaskTitleGenerator(BaseTitleGenerator):
    """Генератор заголовков для разбора заданий ОГЭ."""

    def _extract_resource(self, text: str) -> Optional[str]:
        resource_patterns = [
            r"\(Решу\s+ОГЭ\)",
            r"\(РешуОГЭ\)",
            r"\(КОГЭ\)",
            r"\(Поляков\)",
            r"\(Комп\s+ОГЭ\)",
        ]
        for pattern in resource_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip("()")
        if re.search(r"\s+Поляков\s*$", text, re.IGNORECASE):
            return "Поляков"
        return None

    def generate(self, video: VideoData) -> str:
        description = video.description.strip()
        if not description:
            return f"{PREFIX}. {video.file_path.stem}"

        first_line = description.split("\n")[0].strip()

        patterns = [
            r"тип\s+(\d+)[_\d]",
            r"разбор\s+(\d+)[_\d]",
            r"решение\s+(\d+)[_\d]",
            r"^(\d+)[_\d]",
            r"разбор\s+задани[ий]\s+(\d+)$",
            r"разбор\s+задани[ий]\s+(\d+)\s*\.",
            r"задани[яе]\s*[№#]?\s*(\d+)",
            r"задани[ея]\s+(\d+)",
            r"задач[аи]\s+(\d+)",
            r"разбор\s+задани[яе]\s+(\d+)",
            r"разбор\s+задани[ий]\s+(\d+)",
            r"решение\s+задани[яе]\s*[№#]?\s*(\d+)",
            r"решение\s+задани[ий]\s+(\d+)",
            r"видео\s+решения?\s+задани[ея]\s+(\d+)",
            r"видеоразбор\s+задани[яе]\s+(\d+)",
        ]

        task_number = None
        task_type = None
        task_range = None

        range_match = re.search(
            r"задани[ий]\s+(\d+)[-_](\d+)", first_line, re.IGNORECASE
        )
        if range_match:
            task_number = int(range_match.group(1))
            task_range = f"{range_match.group(1)}-{range_match.group(2)}"
        else:
            for pattern in patterns:
                match = re.search(pattern, first_line, re.IGNORECASE)
                if match:
                    task_number = int(match.group(1))
                    break

        if not task_number:
            return f"{PREFIX}. {video.file_path.stem}"

        subtype_match = re.search(r"(\d+)[_](\d+)", first_line)
        if subtype_match and not task_range:
            num1, num2 = int(subtype_match.group(1)), int(subtype_match.group(2))
            if abs(num1 - num2) > 5:
                task_type = f"{subtype_match.group(1)}_{subtype_match.group(2)}"

        resource = self._extract_resource(first_line)
        if not resource and re.search(r"решуогэ", first_line, re.IGNORECASE):
            resource = "Решу ОГЭ"

        if task_range:
            parts = [f"{PREFIX}. Разбираем задание №{task_range}"]
        else:
            parts = [f"{PREFIX}. Разбираем задание №{task_number}"]

        if task_type:
            parts.append(f"({task_type})")
        if resource:
            parts.append(f"({resource})")

        return " ".join(parts)

    def get_name(self) -> str:
        return "oge_task"


class OGEAutoTitleGenerator(BaseTitleGenerator):
    """Автоматический генератор заголовков для ОГЭ по информатике."""

    def __init__(self):
        self.topic_generator = OGETopicTitleGenerator()
        self.task_generator = OGETaskTitleGenerator()

    def generate(self, video: VideoData) -> str:
        description = video.description.strip()
        if not description:
            filename_stem = video.file_path.stem
            if "Встреча" in filename_stem or "встреча" in filename_stem.lower():
                return f"{PREFIX}. Запись встречи"
            if filename_stem.isdigit():
                return f"{PREFIX}. Разбираем задание №{filename_stem} (Решу ОГЭ)"
            match = re.match(r"^(\d+)[_\d]", filename_stem)
            if match:
                return f"{PREFIX}. Разбираем задание №{match.group(1)}"
            match = re.match(r"^(\d+)\s*\(", filename_stem)
            if match:
                return f"{PREFIX}. Разбираем задание №{match.group(1)}"
            return f"{PREFIX}. {filename_stem}"

        first_line = description.split("\n")[0].strip()
        first_line_lower = first_line.lower()
        filename_stem = video.file_path.stem

        # Запись встречи в Телемосте
        if "Встреча_в_Телемосте" in filename_stem or (
            "встреча" in filename_stem.lower() and "телемост" in filename_stem.lower()
        ):
            return f"{PREFIX}. Запись встречи"

        # videoXXXXX.mp4 — тема из первой строки
        if filename_stem.startswith("video") and len(filename_stem) > 5 and filename_stem[5:].isdigit():
            topic = first_line.split(".")[0].strip() or first_line.strip()
            topic = " ".join(topic.split())
            if len(topic) > 3:
                return f'{PREFIX}. Разбираем тему "{topic}"'

        # Одна фраза-название темы (короткое предложение с точкой в конце или без)
        if len(first_line) < 90 and first_line[0].isupper():
            if first_line.endswith("."):
                topic = first_line[:-1].strip()
            else:
                topic = first_line.strip()
            if 5 < len(topic) < 85 and not re.search(
                r"^(разбор|решение)\s+задани[яе]\s+\d+\s*\.?\s*$", first_line_lower
            ):
                return f'{PREFIX}. Разбираем тему "{topic}"'

        # "Разбор решения заданий N с помощью...", "Решение усложненных заданий N с помощью..." — тема
        if re.search(
            r"^(разбор\s+решения|решение\s+усложненных)\s+задани[ий]\s+\d+\s+с\s+помощью",
            first_line_lower,
        ):
            topic = first_line.split(".")[0].strip() or first_line.strip()
            topic = " ".join(topic.split())
            if len(topic) > 10:
                return f'{PREFIX}. Разбираем тему "{topic}"'

        if "видео" in first_line_lower and "задани" in first_line_lower:
            for pattern in [
                r"видео\s+решения?\s+задани[ея]\s+(\d+)",
                r"видеоразбор\s+задани[яе]\s+(\d+)",
            ]:
                match = re.search(pattern, first_line, re.IGNORECASE)
                if match:
                    return f'{PREFIX}. Разбираем задание №{match.group(1)}'

        if "пример" in first_line_lower and "задани" in first_line_lower:
            if "в файле" in first_line_lower or "для задани" in first_line_lower:
                topic = first_line.split(".")[0].strip()
                if len(topic) > 5:
                    return f'{PREFIX}. Разбираем тему "{topic}"'

        if re.search(r"урок\s+\d+[._]\d+\.", first_line_lower) or re.search(
            r"урок\s+\d+\.", first_line_lower
        ):
            return self.topic_generator.generate(video)

        if not re.search(
            r"видео\s+решения?\s+задани[яе]|видеоразбор\s+задани[яе]",
            first_line_lower,
        ):
            topic_match = re.search(
                r"разбор\s+задани[ий]\s+(\d+)\.\s+(.+?)(?:\.|$)",
                first_line,
                re.IGNORECASE,
            )
            if topic_match:
                topic_text = topic_match.group(2).strip()
                if topic_text and len(topic_text) > 5:
                    return self.topic_generator.generate(video)

        topic_theme_match = re.search(
            r"разбор\s+задани[ий]\s+по\s+теме\s+\d+\.\s*(.+?)(?:\.|$)",
            first_line,
            re.IGNORECASE,
        )
        if topic_theme_match:
            topic = topic_theme_match.group(1).strip()
            if topic and len(topic) > 3:
                return f'{PREFIX}. Разбираем тему "{topic}"'

        if (
            re.search(r"задани[ея]\s+\d+\.\s+[А-Яа-я]", first_line)
            and not re.search(r"разбор|решение", first_line_lower)
        ):
            return self.topic_generator.generate(video)

        if "термин" in first_line_lower and "теори" in first_line_lower and "задани" in first_line_lower:
            topic_match = re.search(
                r"термин[ы]?\s+и\s+теори[ия]\s+задани[яе]\s+\d+\.\s*(.+?)(?:\.|$)",
                first_line,
                re.IGNORECASE,
            )
            if topic_match:
                topic = topic_match.group(1).strip()
                if len(topic) > 5:
                    return f'{PREFIX}. Разбираем тему "{topic}"'
            topic = first_line.split(".")[0].strip()
            topic = " ".join(topic.split())
            if len(topic) > 5:
                return f'{PREFIX}. Разбираем тему "{topic}"'

        if re.search(
            r"^(как|еще|немного|некоторые)", first_line_lower
        ):
            topic_match = re.search(r"^(.+?)(?:\.|$)", first_line)
            if topic_match:
                topic = topic_match.group(1).strip()
                if len(topic) > 80:
                    truncated = topic[:80].rsplit(" ", 1)[0]
                    topic = truncated if len(truncated) > 50 else topic[:77] + "..."
                if len(topic) > 10:
                    return f'{PREFIX}. Разбираем тему "{topic}"'

        if re.search(
            r"разбор\s+задани[ий]\s+по\s+теме\s+\d+", first_line_lower
        ):
            return self.topic_generator.generate(video)

        if re.search(
            r"задани[ея]\s+\d+|задач[аи]\s+\d+", first_line_lower
        ) and not (
            first_line_lower.startswith("пример") and "в файле" in first_line_lower
        ):
            return self.task_generator.generate(video)

        result = self.task_generator.generate(video)
        # Если получили имя файла в заголовке — пробуем взять тему из первой строки или из имени файла
        if result and filename_stem in result:
            topic = first_line.split(".")[0].strip() or first_line.strip()
            topic = " ".join(topic.split())
            if 5 < len(topic) <= 100:
                return f'{PREFIX}. Разбираем тему "{topic}"'
            # Длинная первая строка: берём тему из имени файла (подчёркивания → пробелы)
            if "_" in filename_stem:
                topic = filename_stem.replace("_", " ").strip()
                if len(topic) > 3:
                    return f'{PREFIX}. Разбираем тему "{topic}"'
        return result

    def get_name(self) -> str:
        return "oge_auto"
