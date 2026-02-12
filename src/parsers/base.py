"""Базовый класс для парсеров экспорта Telegram."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from ..models.video import VideoData


class BaseParser(ABC):
    """Базовый класс для парсеров экспорта Telegram.
    
    Определяет интерфейс для парсинга экспортов и извлечения
    информации о видео из сообщений.
    """
    
    def __init__(self, export_path: Path):
        """Инициализировать парсер.
        
        Args:
            export_path: Путь к директории экспорта Telegram.
        """
        self.export_path = Path(export_path)
        if not self.export_path.exists():
            raise ValueError(f"Путь экспорта не существует: {export_path}")
    
    @abstractmethod
    def parse(self) -> List[VideoData]:
        """Парсить экспорт и извлечь данные о видео.
        
        Returns:
            Список объектов VideoData с информацией о видео.
            
        Raises:
            ParseError: При ошибке парсинга экспорта.
        """
        pass
    
    @abstractmethod
    def detect_format(self) -> bool:
        """Определить, подходит ли этот парсер для данного экспорта.
        
        Returns:
            True, если формат экспорта поддерживается парсером.
        """
        pass
