"""Реализации генераторов заголовков."""

from datetime import datetime
from typing import Optional

from .base import BaseTitleGenerator
from ..models.video import VideoData


class SimpleTitleGenerator(BaseTitleGenerator):
    """Простой генератор заголовков на основе имени файла."""
    
    def generate(self, video: VideoData) -> str:
        """Сгенерировать заголовок из имени файла.
        
        Args:
            video: Данные видео.
            
        Returns:
            Заголовок на основе имени файла без расширения.
        """
        return video.file_path.stem
    
    def get_name(self) -> str:
        """Получить имя генератора."""
        return "simple"


class DateTitleGenerator(BaseTitleGenerator):
    """Генератор заголовков с датой."""
    
    def __init__(self, date_format: str = "%Y-%m-%d"):
        """Инициализировать генератор.
        
        Args:
            date_format: Формат даты для заголовка.
        """
        self.date_format = date_format
    
    def generate(self, video: VideoData) -> str:
        """Сгенерировать заголовок с датой.
        
        Args:
            video: Данные видео.
            
        Returns:
            Заголовок с датой или имя файла, если дата отсутствует.
        """
        if video.date:
            date_str = video.date.strftime(self.date_format)
            return f"{date_str} - {video.file_path.stem}"
        return video.file_path.stem
    
    def get_name(self) -> str:
        """Получить имя генератора."""
        return "date"


class DescriptionTitleGenerator(BaseTitleGenerator):
    """Генератор заголовков на основе описания."""
    
    def __init__(self, max_length: int = 100):
        """Инициализировать генератор.
        
        Args:
            max_length: Максимальная длина заголовка.
        """
        self.max_length = max_length
    
    def generate(self, video: VideoData) -> str:
        """Сгенерировать заголовок из описания.
        
        Args:
            video: Данные видео.
            
        Returns:
            Заголовок из описания (обрезанный) или имя файла.
        """
        if video.description:
            title = video.description.strip()
            if len(title) > self.max_length:
                title = title[:self.max_length].rsplit(" ", 1)[0] + "..."
            return title
        return video.file_path.stem
    
    def get_name(self) -> str:
        """Получить имя генератора."""
        return "description"


class CompositeTitleGenerator(BaseTitleGenerator):
    """Композитный генератор, объединяющий несколько генераторов."""
    
    def __init__(self, generators: list[BaseTitleGenerator], separator: str = " | "):
        """Инициализировать композитный генератор.
        
        Args:
            generators: Список генераторов для объединения.
            separator: Разделитель между частями заголовка.
        """
        self.generators = generators
        self.separator = separator
    
    def generate(self, video: VideoData) -> str:
        """Сгенерировать заголовок, объединив результаты генераторов.
        
        Args:
            video: Данные видео.
            
        Returns:
            Объединенный заголовок.
        """
        parts = []
        for generator in self.generators:
            part = generator.generate(video)
            if part:
                parts.append(part)
        
        if parts:
            return self.separator.join(parts)
        return video.file_path.stem
    
    def get_name(self) -> str:
        """Получить имя генератора."""
        return "composite"
