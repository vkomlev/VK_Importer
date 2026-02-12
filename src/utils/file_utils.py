"""Утилиты для работы с файлами."""

from pathlib import Path
from typing import List

import logging

logger = logging.getLogger(__name__)


def validate_video_file(file_path: Path) -> bool:
    """Проверить, является ли файл валидным видеофайлом.
    
    Args:
        file_path: Путь к файлу.
        
    Returns:
        True, если файл существует и имеет поддерживаемое расширение.
    """
    if not file_path.exists():
        logger.warning(f"Файл не существует: {file_path}")
        return False
    
    valid_extensions = [".mp4", ".webm"]
    if file_path.suffix.lower() not in valid_extensions:
        logger.warning(
            f"Неподдерживаемое расширение файла {file_path.suffix}: {file_path}"
        )
        return False
    
    return True


def find_video_files(directory: Path) -> List[Path]:
    """Найти все видеофайлы в директории.
    
    Args:
        directory: Директория для поиска.
        
    Returns:
        Список путей к видеофайлам.
    """
    video_files = []
    
    for ext in ["*.mp4", "*.webm"]:
        video_files.extend(directory.glob(ext))
        video_files.extend(directory.rglob(ext))  # Рекурсивный поиск
    
    return sorted(video_files)
