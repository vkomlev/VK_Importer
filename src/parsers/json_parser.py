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
        # Проверяем наличие файла и его тип
        file_path_str = message.get("file")
        if not file_path_str:
            return None
        
        # Проверяем mime_type для фильтрации видео
        mime_type = message.get("mime_type", "")
        if mime_type and not mime_type.startswith("video/"):
            return None
        
        # Проверяем расширение файла
        file_name = message.get("file_name", file_path_str)
        if not any(file_name.lower().endswith(ext) for ext in [".mp4", ".webm"]):
            return None
        
        # Разрешаем путь к файлу
        # MP4 файлы находятся в папке video_files, WEBM - в папке files
        file_ext = Path(file_name).suffix.lower()
        
        # Определяем папку в зависимости от расширения
        if file_ext == ".mp4":
            target_dir = self.export_path / "video_files"
        elif file_ext == ".webm":
            target_dir = self.export_path / "files"
        else:
            # Для других форматов пробуем обе папки
            target_dir = self.export_path / "files"
        
        # Убираем префикс папки из пути, если есть
        if file_path_str.startswith("files/"):
            file_path_str = file_path_str[len("files/"):]
        elif file_path_str.startswith("video_files/"):
            file_path_str = file_path_str[len("video_files/"):]
        
        # Пробуем найти файл в целевой папке
        file_path = target_dir / file_path_str
        
        # Если файл не найден по полному пути, пробуем найти по имени
        if not file_path.exists():
            file_path = target_dir / file_name
        
        # Если все еще не найден, пробуем другую папку (на случай ошибки в определении)
        if not file_path.exists():
            alternative_dir = self.export_path / "video_files" if file_ext == ".webm" else self.export_path / "files"
            file_path = alternative_dir / file_name
        
        if not file_path.exists():
            logger.debug(f"Видеофайл не найден: {file_path}")
            return None
        
        # Извлечение текста сообщения
        description = self._extract_text_from_message(message)
        
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
    
    def _extract_text_from_message(self, message: Dict[str, Any]) -> str:
        """Извлечь текст из сообщения.
        
        Текст может быть строкой или массивом, содержащим строки и объекты
        с типами (например, text_link).
        
        Args:
            message: Словарь с данными сообщения.
            
        Returns:
            Извлеченный текст сообщения.
        """
        text = message.get("text", "")
        
        if isinstance(text, str):
            return text
        
        if isinstance(text, list):
            text_parts = []
            for item in text:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict):
                    # Объекты могут быть разных типов: plain, text_link и т.д.
                    item_text = item.get("text", "")
                    if item_text:
                        text_parts.append(item_text)
            return " ".join(text_parts)
        
        return str(text) if text else ""
    
    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """Парсить дату из значения.
        
        Формат даты из Telegram JSON: "2025-04-01T21:58:59" (ISO format)
        Также может быть unix timestamp в поле date_unixtime.
        
        Args:
            date_value: Значение даты (может быть строкой ISO формата).
            
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
                # Парсим ISO формат даты
                return parser.parse(date_value)
            except Exception as e:
                logger.warning(f"Не удалось распарсить дату '{date_value}': {e}")
                return None
        
        return None
