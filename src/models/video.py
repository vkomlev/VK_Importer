"""Модель данных для видео."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class VideoData:
    """Данные о видео для публикации.
    
    Attributes:
        file_path: Путь к видеофайлу.
        title: Заголовок видео (будет сгенерирован).
        description: Описание видео (текст сообщения).
        date: Дата видео.
        channel: Название канала (опционально).
    """
    
    file_path: Path
    title: str
    description: str
    date: Optional[datetime] = None
    channel: Optional[str] = None
    
    def __post_init__(self):
        """Валидация данных после инициализации."""
        if not isinstance(self.file_path, Path):
            self.file_path = Path(self.file_path)
        
        if not self.file_path.exists():
            raise ValueError(f"Видеофайл не существует: {self.file_path}")
