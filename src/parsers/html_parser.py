"""Парсер HTML экспорта Telegram Desktop."""

from pathlib import Path
from typing import List, Optional
import re
from datetime import datetime

from bs4 import BeautifulSoup
import logging

from .base import BaseParser
from ..models.video import VideoData

logger = logging.getLogger(__name__)


class HTMLParser(BaseParser):
    """Парсер для HTML формата экспорта Telegram.
    
    Обрабатывает HTML файлы с сообщениями и ищет прикрепленные
    видеофайлы в папке files/.
    """
    
    def detect_format(self) -> bool:
        """Определить, является ли экспорт HTML форматом.
        
        Returns:
            True, если найдены HTML файлы в экспорте.
        """
        html_files = list(self.export_path.glob("*.html"))
        return len(html_files) > 0
    
    def parse(self) -> List[VideoData]:
        """Парсить HTML экспорт и извлечь данные о видео.
        
        Returns:
            Список объектов VideoData с информацией о видео.
        """
        html_files = list(self.export_path.glob("*.html"))
        if not html_files:
            logger.warning(f"HTML файлы не найдены в {self.export_path}")
            return []
        
        videos = []
        files_dir = self.export_path / "files"
        
        for html_file in html_files:
            logger.info(f"Парсинг файла: {html_file.name}")
            videos.extend(self._parse_html_file(html_file, files_dir))
        
        logger.info(f"Найдено видео: {len(videos)}")
        return videos
    
    def _parse_html_file(
        self, html_file: Path, files_dir: Path
    ) -> List[VideoData]:
        """Парсить один HTML файл.
        
        Args:
            html_file: Путь к HTML файлу.
            files_dir: Путь к папке с файлами.
            
        Returns:
            Список VideoData из этого файла.
        """
        with open(html_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "lxml")
        
        videos = []
        messages = soup.find_all("div", class_="message")
        
        for message in messages:
            video_data = self._extract_video_from_message(message, files_dir)
            if video_data:
                videos.append(video_data)
        
        return videos
    
    def _extract_video_from_message(
        self, message_element, files_dir: Path
    ) -> Optional[VideoData]:
        """Извлечь информацию о видео из элемента сообщения.
        
        Args:
            message_element: BeautifulSoup элемент сообщения.
            files_dir: Путь к папке с файлами.
            
        Returns:
            VideoData или None, если видео не найдено.
        """
        # Поиск видеофайлов в сообщении
        video_links = message_element.find_all("a", href=re.compile(r"\.(mp4|webm)$", re.I))
        
        if not video_links:
            return None
        
        # Извлечение текста сообщения
        text_elem = message_element.find("div", class_="text")
        description = text_elem.get_text(strip=True) if text_elem else ""
        
        # Извлечение даты
        date_elem = message_element.find("div", class_="date")
        date = self._parse_date(date_elem.get_text(strip=True)) if date_elem else None
        
        # Обработка всех найденных видео
        for video_link in video_links:
            video_path = self._resolve_video_path(video_link.get("href"), files_dir)
            if video_path and video_path.exists():
                return VideoData(
                    file_path=video_path,
                    title="",  # Будет сгенерирован позже
                    description=description,
                    date=date
                )
        
        return None
    
    def _resolve_video_path(self, href: str, files_dir: Path) -> Optional[Path]:
        """Разрешить путь к видеофайлу.
        
        Args:
            href: Ссылка из HTML (может быть относительной или абсолютной).
            files_dir: Базовая папка с файлами.
            
        Returns:
            Полный путь к файлу или None, если не найден.
        """
        if not href:
            return None
        
        # Убрать начальный слеш и ../ если есть
        href = href.lstrip("/").replace("../", "")
        
        # Попробовать найти файл в files_dir
        video_path = files_dir / href
        if video_path.exists():
            return video_path
        
        # Попробовать найти по имени файла
        filename = Path(href).name
        video_path = files_dir / filename
        if video_path.exists():
            return video_path
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Парсить дату из строки.
        
        Args:
            date_str: Строка с датой из HTML.
            
        Returns:
            Объект datetime или None при ошибке парсинга.
        """
        # TODO: Реализовать парсинг даты из формата Telegram
        # Формат может быть разным, нужно проанализировать примеры
        try:
            # Временная заглушка
            from dateutil import parser
            return parser.parse(date_str)
        except Exception as e:
            logger.warning(f"Не удалось распарсить дату '{date_str}': {e}")
            return None
