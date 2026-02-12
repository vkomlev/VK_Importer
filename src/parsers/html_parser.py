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
    видеофайлы в папке video_files/.
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
        
        for html_file in html_files:
            logger.info(f"Парсинг файла: {html_file.name}")
            videos.extend(self._parse_html_file(html_file))
        
        logger.info(f"Найдено видео: {len(videos)}")
        return videos
    
    def _parse_html_file(self, html_file: Path) -> List[VideoData]:
        """Парсить один HTML файл.
        
        Args:
            html_file: Путь к HTML файлу.
            
        Returns:
            Список VideoData из этого файла.
        """
        with open(html_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        
        videos = []
        # Ищем только обычные сообщения (не service)
        messages = soup.find_all("div", class_=re.compile(r"message default"))
        
        for message in messages:
            video_data = self._extract_video_from_message(message)
            if video_data:
                videos.append(video_data)
        
        return videos
    
    def _extract_video_from_message(
        self, message_element
    ) -> Optional[VideoData]:
        """Извлечь информацию о видео из элемента сообщения.
        
        Args:
            message_element: BeautifulSoup элемент сообщения.
            
        Returns:
            VideoData или None, если видео не найдено.
        """
        # Поиск видеофайлов в сообщении
        # MP4 файлы обычно в элементах с классом video_file_wrap
        # WEBM файлы могут быть в элементах с классом media_file
        video_wrap = message_element.find("a", class_="video_file_wrap")
        
        if not video_wrap:
            # Пробуем найти WEBM файлы в media_file элементах
            media_link = message_element.find("a", class_="media_file")
            if media_link:
                href = media_link.get("href", "")
                if href and (href.endswith(".webm") or href.endswith(".mp4")):
                    video_wrap = media_link
        
        if not video_wrap:
            return None
        
        # Получаем путь к видео из атрибута href
        video_href = video_wrap.get("href")
        if not video_href:
            return None
        
        # Определяем расширение файла для выбора правильной папки
        # MP4 файлы в video_files/, WEBM в files/
        file_ext = Path(video_href).suffix.lower()
        
        # Разрешаем путь к видеофайлу
        video_path = self._resolve_video_path(video_href, file_ext)
        if not video_path or not video_path.exists():
            return None
        
        # Извлечение текста сообщения
        text_elem = message_element.find("div", class_="text")
        description = text_elem.get_text(separator=" ", strip=True) if text_elem else ""
        
        # Извлечение даты из атрибута title элемента date
        # Ищем элемент с классом "date" и атрибутом "details"
        date_elem = message_element.find("div", class_=re.compile(r"date.*details"))
        date = None
        if date_elem:
            date_title = date_elem.get("title")
            if date_title:
                date = self._parse_date(date_title)
        
        return VideoData(
            file_path=video_path,
            title="",  # Будет сгенерирован позже
            description=description,
            date=date
        )
    
    def _resolve_video_path(self, href: str, file_ext: str) -> Optional[Path]:
        """Разрешить путь к видеофайлу.
        
        MP4 файлы ищутся в папке video_files/, WEBM - в папке files/.
        
        Args:
            href: Ссылка из HTML (например "video_files/ЕГЭ_Задание1.mp4").
            file_ext: Расширение файла (.mp4 или .webm).
            
        Returns:
            Полный путь к файлу или None, если не найден.
        """
        if not href:
            return None
        
        # Убрать начальный слеш и ../ если есть
        href = href.lstrip("/").replace("../", "")
        
        # Определяем целевую папку в зависимости от расширения
        if file_ext == ".mp4":
            target_dir = self.export_path / "video_files"
        elif file_ext == ".webm":
            target_dir = self.export_path / "files"
        else:
            # Для других форматов пробуем video_files (по умолчанию для HTML)
            target_dir = self.export_path / "video_files"
        
        # Убрать префикс папки из href, если есть
        if href.startswith("video_files/"):
            href = href[len("video_files/"):]
        elif href.startswith("files/"):
            href = href[len("files/"):]
        
        # Попробовать найти файл в целевой папке
        video_path = target_dir / href
        if video_path.exists():
            return video_path
        
        # Попробовать найти по имени файла
        filename = Path(href).name
        video_path = target_dir / filename
        if video_path.exists():
            return video_path
        
        # Если не найден, пробуем альтернативную папку (на случай ошибки в определении)
        alternative_dir = self.export_path / "files" if file_ext == ".mp4" else self.export_path / "video_files"
        video_path = alternative_dir / filename
        if video_path.exists():
            return video_path
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Парсить дату из строки.
        
        Формат даты из Telegram HTML: "08.02.2023 13:47:10 UTC+05:00"
        
        Args:
            date_str: Строка с датой из атрибута title элемента date.
            
        Returns:
            Объект datetime или None при ошибке парсинга.
        """
        try:
            from dateutil import parser
            # Парсим дату, dateutil умеет обрабатывать формат с UTC
            return parser.parse(date_str)
        except Exception as e:
            logger.warning(f"Не удалось распарсить дату '{date_str}': {e}")
            return None
