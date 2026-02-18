"""Парсер кастомного формата выгрузки (export.json + channel_info + media_files).

Формат описан в docs/output-formats.md: один файл export.json в корне каталога
с полями channel_info, messages[].media_files (type, path относительно корня).
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import logging

from .base import BaseParser
from ..models.video import VideoData

logger = logging.getLogger(__name__)


class CustomExportParser(BaseParser):
    """Парсер формата кастомной выгрузки TG Parser (export.json)."""

    EXPORT_FILENAME = "export.json"

    def detect_format(self) -> bool:
        """Определить, является ли экспорт кастомным форматом (export.json с channel_info)."""
        export_file = self.export_path / self.EXPORT_FILENAME
        if not export_file.exists():
            return False
        try:
            with open(export_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False
        return isinstance(data, dict) and "channel_info" in data and "messages" in data

    def parse(self) -> List[VideoData]:
        """Парсить export.json и извлечь видео из messages[].media_files."""
        export_file = self.export_path / self.EXPORT_FILENAME
        try:
            with open(export_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Ошибка чтения {export_file}: {e}")
            return []

        messages = data.get("messages", [])
        if not isinstance(messages, list):
            return []

        seen_ids: set[int] = set()
        videos: List[VideoData] = []

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            msg_id = msg.get("id")
            if msg_id is not None and msg_id in seen_ids:
                continue
            if msg_id is not None:
                seen_ids.add(msg_id)

            for video in self._extract_videos_from_message(msg):
                videos.append(video)

        logger.info(f"Кастомный экспорт: найдено {len(videos)} видео")
        return videos

    def _extract_videos_from_message(self, message: Dict[str, Any]) -> List[VideoData]:
        """Извлечь VideoData из сообщения по media_files с type=video."""
        result: List[VideoData] = []
        media_files = message.get("media_files") or []
        if not isinstance(media_files, list):
            return result

        description = (message.get("text") or "").strip()
        date = self._parse_date(message.get("date"))

        for m in media_files:
            if not isinstance(m, dict):
                continue
            if m.get("type") != "video":
                continue
            path_rel = m.get("path")
            if not path_rel:
                continue
            file_path = self.export_path / path_rel
            if not file_path.exists():
                logger.debug(f"Файл не найден: {file_path}")
                continue
            try:
                result.append(
                    VideoData(
                        file_path=file_path,
                        title="",
                        description=description,
                        date=date,
                    )
                )
            except ValueError as e:
                logger.debug(f"Пропуск записи: {e}")
        return result

    def _parse_date(self, value: Any) -> Optional[datetime]:
        """Парсить дату ISO UTC (YYYY-MM-DDTHH:mm:ssZ)."""
        if not value or not isinstance(value, str):
            return None
        try:
            s = value.replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except ValueError:
            return None
