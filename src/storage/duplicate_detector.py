"""Определение дубликатов видео."""

import hashlib
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Определение дубликатов видео по хешу файла."""
    
    @staticmethod
    def calculate_file_hash(file_path: Path, chunk_size: int = 8192) -> str:
        """Вычислить хеш файла.
        
        Args:
            file_path: Путь к файлу.
            chunk_size: Размер блока для чтения.
            
        Returns:
            SHA256 хеш файла в hex формате.
        """
        sha256 = hashlib.sha256()
        
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Ошибка вычисления хеша файла {file_path}: {e}")
            raise
    
    @staticmethod
    def is_duplicate(file_path: Path, existing_hash: str) -> bool:
        """Проверить, является ли файл дубликатом.
        
        Args:
            file_path: Путь к файлу для проверки.
            existing_hash: Хеш существующего файла.
            
        Returns:
            True если файл является дубликатом.
        """
        try:
            current_hash = DuplicateDetector.calculate_file_hash(file_path)
            return current_hash == existing_hash
        except Exception:
            return False
