"""Публикатор видео в VK Video."""

from pathlib import Path
from typing import Optional
import logging

import vk_api
from vk_api.upload import VkUpload

from ..models.video import VideoData

logger = logging.getLogger(__name__)


class VKPublisher:
    """Публикатор видео в VK Video через VK API."""
    
    def __init__(self, access_token: str, group_id: Optional[int] = None):
        """Инициализировать публикатор.
        
        Args:
            access_token: Токен доступа VK API.
            group_id: ID группы для публикации (опционально).
        """
        self.access_token = access_token
        self.group_id = group_id
        
        # Инициализация VK API
        self.vk_session = vk_api.VkApi(token=access_token)
        self.vk = self.vk_session.get_api()
        self.upload = VkUpload(self.vk_session)
    
    def publish(self, video: VideoData) -> Optional[str]:
        """Опубликовать видео в VK Video.
        
        Args:
            video: Данные видео для публикации.
            
        Returns:
            URL опубликованного видео или None при ошибке.
        """
        try:
            logger.info(f"Начало загрузки видео: {video.file_path.name}")
            
            # Загрузка видео
            video_response = self.upload.video(
                video_file=str(video.file_path),
                name=video.title,
                description=video.description,
                group_id=self.group_id,
            )
            
            video_id = video_response.get("video_id")
            owner_id = video_response.get("owner_id")
            
            if video_id and owner_id:
                video_url = f"https://vk.com/video{owner_id}_{video_id}"
                logger.info(f"Видео успешно опубликовано: {video_url}")
                return video_url
            else:
                logger.error(f"Не удалось получить ID видео из ответа: {video_response}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при публикации видео {video.file_path}: {e}")
            return None
    
    def publish_batch(self, videos: list[VideoData]) -> dict[str, Optional[str]]:
        """Опубликовать несколько видео.
        
        Args:
            videos: Список видео для публикации.
            
        Returns:
            Словарь {file_path: video_url} с результатами публикации.
        """
        results = {}
        
        for video in videos:
            video_url = self.publish(video)
            results[str(video.file_path)] = video_url
        
        return results
