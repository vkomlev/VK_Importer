"""Парсер JSON экспорта Telegram Desktop."""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import logging

from .base import BaseParser
from ..models.video import VideoData

logger = logging.getLogger(__name__)


class JSONParser(BaseParser):
    """Парсер для JSON формата экспорта Telegram.
    
    Обрабатывает JSON файлы с сообщениями и ищет прикрепленные
    видеофайлы в структуре данных.
    """
    
    def detect_format(self) -> bool:
        """Определить, является ли экспорт JSON форматом.
        
        Returns:
            True, если найдены JSON файлы в экспорте.
        """
        json_files = list(self.export_path.glob("*.json"))
        return len(json_files) > 0
    
    def parse(self) -> List[VideoData]:
        """Парсить JSON экспорт и извлечь данные о видео.
        
        Returns:
            Список объектов VideoData с информацией о видео.
        """
        json_files = list(self.export_path.glob("*.json"))
        if not json_files:
            logger.warning(f"JSON файлы не найдены в {self.export_path}")
            return []
        
        videos = []
        
        for json_file in json_files:
            logger.info(f"Парсинг файла: {json_file.name}")
            videos.extend(self._parse_json_file(json_file))
        
        logger.info(f"Найдено видео: {len(videos)}")
        return videos
    
    def _parse_json_file(self, json_file: Path) -> List[VideoData]:
        """Парсить один JSON файл.
        
        Args:
            json_file: Путь к JSON файлу.
            
        Returns:
            Список VideoData из этого файла.
        """
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON файла {json_file}: {e}")
            return []
        
        videos = []
        
        # Структура JSON может быть разной, нужно адаптировать под реальный формат
        messages = self._extract_messages(data)
        
        for message in messages:
            video_data = self._extract_video_from_message(message)
            if video_data:
                videos.append(video_data)
        
        return videos
    
    def _extract_messages(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Извлечь список сообщений из JSON структуры.
        
        Args:
            data: Загруженные данные JSON.
            
        Returns:
            Список сообщений.
        """
        # TODO: Адаптировать под реальную структуру JSON экспорта Telegram
        # Возможные варианты:
        # - data["messages"]
        # - data["chats"][0]["messages"]
        # - и т.д.
        
        if isinstance(data, list):
            return data
        
        if isinstance(data, dict):
            if "messages" in data:
                return data["messages"]
            if "chats" in data:
                messages = []
                for chat in data["chats"]:
                    if "messages" in chat:
                        messages.extend(chat["messages"])
                return messages
        
        return []
    
    def _extract_video_from_message(
        self, message: Dict[str, Any]
    ) -> Optional[VideoData]:
        """Извлечь информацию о видео из сообщения.
        
        Args:
            message: Словарь с данными сообщения.
            
        Returns:
            VideoData или None, если видео не найдено.
        """
        # Поиск видео в attachments/media
        media = message.get("media", {})
        file_path = None
        
        # Проверка различных возможных путей к файлу
        if "file" in media:
            file_path = self.export_path / "files" / media["file"]
        elif "path" in media:
            file_path = self.export_path / media["path"]
        elif "video" in media:
            video_info = media["video"]
            if "file" in video_info:
                file_path = self.export_path / "files" / video_info["file"]
        
        if not file_path or not file_path.exists():
            return None
        
        # Проверка расширения файла
        if file_path.suffix.lower() not in [".mp4", ".webm"]:
            return None
        
        # Извлечение текста сообщения
        description = message.get("text", "")
        if isinstance(description, list):
            # Текст может быть массивом объектов с форматированием
            description = " ".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in description
            )
        
        # Извлечение даты
        date = None
        if "date" in message:
            date = self._parse_date(message["date"])
        
        return VideoData(
            file_path=file_path,
            title="",  # Будет сгенерирован позже
            description=description,
            date=date
        )
    
    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """Парсить дату из значения.
        
        Args:
            date_value: Значение даты (может быть строкой, timestamp и т.д.).
            
        Returns:
            Объект datetime или None при ошибке парсинга.
        """
        if isinstance(date_value, (int, float)):
            # Unix timestamp
            try:
                return datetime.fromtimestamp(date_value)
            except (ValueError, OSError) as e:
                logger.warning(f"Не удалось преобразовать timestamp {date_value}: {e}")
                return None
        
        if isinstance(date_value, str):
            try:
                from dateutil import parser
                return parser.parse(date_value)
            except Exception as e:
                logger.warning(f"Не удалось распарсить дату '{date_value}': {e}")
                return None
        
        return None
